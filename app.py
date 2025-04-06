import os
import time
import uuid
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict
from pydantic import BaseModel, Field
from fastapi import FastAPI, HTTPException, Depends, Header, Request, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger("mcp-server")

# Define data models
class Document(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    content: str
    metadata: Dict = Field(default_factory=dict)
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    
class Context(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    documents: List[str] = Field(default_factory=list)
    description: Optional[str] = None
    created_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now().isoformat())

class TaskQueue(BaseModel):
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    failed_tasks: List[Dict[str, Any]] = Field(default_factory=list)

class RateLimiter:
    def __init__(self, requests_per_minute=60):
        self.requests_per_minute = requests_per_minute
        self.request_times = []
    
    def is_rate_limited(self):
        current_time = time.time()
        # Remove request times older than 1 minute
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # Check if we've exceeded the rate limit
        if len(self.request_times) >= self.requests_per_minute:
            return True
        
        # Add current request time
        self.request_times.append(current_time)
        return False

# In-memory storage
documents_db = {}
contexts_db = {}
task_queue = TaskQueue()
rate_limiter = RateLimiter()

# Initialize FastAPI
app = FastAPI(title="Model Context Protocol Server")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper function for authentication
async def verify_api_key(api_key: str = Header(None, alias="X-API-Key")):
    expected_api_key = os.getenv("MCP_API_KEY", "test-api-key")
    if api_key != expected_api_key:
        raise HTTPException(status_code=401, detail="Invalid API key")
    return api_key

# Task processor
async def process_task_queue():
    while True:
        if task_queue.tasks:
            if rate_limiter.is_rate_limited():
                logger.warning("Rate limit reached, waiting before processing more tasks")
                await asyncio.sleep(5)
                continue
                
            task = task_queue.tasks.pop(0)
            try:
                task_type = task.get("type")
                if task_type == "create_document":
                    document = Document(**task.get("data"))
                    documents_db[document.id] = document
                    logger.info(f"Processed task: Created document {document.id}")
                elif task_type == "create_context":
                    context = Context(**task.get("data"))
                    contexts_db[context.id] = context
                    logger.info(f"Processed task: Created context {context.id}")
            except Exception as e:
                logger.error(f"Error processing task: {str(e)}")
                task["error"] = str(e)
                task_queue.failed_tasks.append(task)
                # Continue with next task instead of stopping
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(process_task_queue())

# Document endpoints
@app.post("/documents", response_model=Document)
async def create_document(document: Document, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    # Add to task queue for async processing
    task_queue.tasks.append({"type": "create_document", "data": document.dict()})
    return document

@app.get("/documents/{document_id}", response_model=Document)
async def get_document(document_id: str, api_key: str = Depends(verify_api_key)):
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    return documents_db[document_id]

@app.delete("/documents/{document_id}")
async def delete_document(document_id: str, api_key: str = Depends(verify_api_key)):
    if document_id not in documents_db:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Remove document from any contexts
    for context_id, context in contexts_db.items():
        if document_id in context.documents:
            context.documents.remove(document_id)
            context.updated_at = datetime.now().isoformat()
    
    del documents_db[document_id]
    return {"message": "Document deleted successfully"}

# Context endpoints
@app.post("/contexts", response_model=Context)
async def create_context(context: Context, background_tasks: BackgroundTasks, api_key: str = Depends(verify_api_key)):
    task_queue.tasks.append({"type": "create_context", "data": context.dict()})
    return context

@app.get("/contexts/{context_id}", response_model=Context)
async def get_context(context_id: str, api_key: str = Depends(verify_api_key)):
    if context_id not in contexts_db:
        raise HTTPException(status_code=404, detail="Context not found")
    return contexts_db[context_id]

@app.put("/contexts/{context_id}", response_model=Context)
async def update_context(context_id: str, updated_context: Context, api_key: str = Depends(verify_api_key)):
    if context_id not in contexts_db:
        raise HTTPException(status_code=404, detail="Context not found")
    
    # Validate that all documents exist
    for doc_id in updated_context.documents:
        if doc_id not in documents_db:
            task_queue.failed_tasks.append({
                "type": "update_context", 
                "context_id": context_id, 
                "error": f"Document {doc_id} does not exist"
            })
            # Skip the invalid document but continue with the others
            updated_context.documents.remove(doc_id)
    
    updated_context.updated_at = datetime.now().isoformat()
    contexts_db[context_id] = updated_context
    return updated_context

@app.delete("/contexts/{context_id}")
async def delete_context(context_id: str, api_key: str = Depends(verify_api_key)):
    if context_id not in contexts_db:
        raise HTTPException(status_code=404, detail="Context not found")
    
    del contexts_db[context_id]
    return {"message": "Context deleted successfully"}

@app.get("/contexts/{context_id}/content")
async def get_context_content(context_id: str, api_key: str = Depends(verify_api_key)):
    if context_id not in contexts_db:
        raise HTTPException(status_code=404, detail="Context not found")
    
    context = contexts_db[context_id]
    content = []
    
    for doc_id in context.documents:
        if doc_id in documents_db:
            content.append({
                "id": doc_id,
                "content": documents_db[doc_id].content,
                "metadata": documents_db[doc_id].metadata
            })
    
    return {"context_id": context_id, "name": context.name, "documents": content}

@app.get("/tasks/failed")
async def get_failed_tasks(api_key: str = Depends(verify_api_key)):
    return {"failed_tasks": task_queue.failed_tasks}

@app.post("/tasks/retry")
async def retry_failed_tasks(api_key: str = Depends(verify_api_key)):
    if not task_queue.failed_tasks:
        return {"message": "No failed tasks to retry"}
    
    # Move failed tasks back to the main queue
    task_queue.tasks.extend(task_queue.failed_tasks)
    task_queue.failed_tasks = []
    
    return {"message": f"Moved {len(task_queue.tasks)} tasks back to the queue"}

@app.get("/health")
async def health_check():
    return {
        "status": "healthy", 
        "timestamp": datetime.now().isoformat(),
        "queue_size": len(task_queue.tasks),
        "failed_tasks": len(task_queue.failed_tasks)
    }

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("app:app", host="0.0.0.0", port=port, reload=True)