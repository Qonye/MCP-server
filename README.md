# Model Context Protocol (MCP) Server

A lightweight, efficient server implementation for handling context operations with large language models.

## Overview

The Model Context Protocol (MCP) server provides a robust API for managing documents and contexts used by language models. It features automatic task queuing, rate limiting, and error handling to ensure reliable operation even under high load or when encountering errors.

## Features

- **Document Management**: Create, retrieve, and delete document objects
- **Context Management**: Create, update, retrieve, and delete context collections
- **Async Task Processing**: Background processing of tasks with error isolation
- **Rate Limiting**: Built-in request throttling to prevent overload
- **Error Handling**: Failed tasks are stored for later review and retry
- **API Documentation**: Auto-generated Swagger UI documentation
- **Simple Authentication**: API key-based security

## Quick Start

### Prerequisites

- Python 3.7+
- pip package manager

### Installation

```bash
# Clone the repository
git clone https://github.com/your-username/mcp-server.git
cd mcp-server

# Create a virtual environment
python -m venv venv

# Activate the virtual environment
# For Windows:
venv\Scripts\activate
# For macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install fastapi uvicorn pydantic
```

### Running the Server

```bash
python app.py
```

The server will start on http://localhost:8000 by default. You can change the port by setting the PORT environment variable.

### API Documentation

Once the server is running, visit http://localhost:8000/docs to access the interactive API documentation.

## API Usage

### Authentication

Most endpoints require an API key, which should be provided in the `X-API-Key` header. The default API key is `test-api-key`, but this can be changed by setting the `MCP_API_KEY` environment variable.

### Basic Operations

#### 1. Create a Document

```http
POST /documents
X-API-Key: test-api-key

{
  "content": "This is a sample document.",
  "metadata": {
    "source": "example.com",
    "author": "John Doe"
  }
}
```

#### 2. Create a Context

```http
POST /contexts
X-API-Key: test-api-key

{
  "name": "Sample Context",
  "description": "A collection of related documents",
  "documents": ["document-id-1", "document-id-2"]
}
```

#### 3. Retrieve Context Content

```http
GET /contexts/{context_id}/content
X-API-Key: test-api-key
```

### Managing Tasks

#### View Failed Tasks

```http
GET /tasks/failed
X-API-Key: test-api-key
```

#### Retry Failed Tasks

```http
POST /tasks/retry
X-API-Key: test-api-key
```

## Setting Up in VS Code

1. Open the project folder in VS Code
2. Ensure the Python extension is installed
3. Select your Python interpreter (the one in your virtual environment)
4. Open a terminal and run `python app.py`
5. Debug by setting breakpoints and pressing F5

## Environment Variables

- `PORT`: Server port (default: 8000)
- `MCP_API_KEY`: API key for authentication (default: test-api-key)

## Error Handling

The server is designed to continue processing tasks even if individual operations fail. Failed tasks are stored in a separate queue and can be inspected and retried via dedicated endpoints.

## Limitations

- This implementation uses in-memory storage and is not suitable for production environments requiring data persistence
- The rate limiter is basic and may need adjustment for specific use cases

## Future Improvements

- Database integration for persistent storage
- Advanced authentication mechanisms
- More sophisticated rate limiting
- Streaming responses for large contexts
- Vector embedding support for semantic search

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
