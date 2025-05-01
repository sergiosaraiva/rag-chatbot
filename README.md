# RAG Chatbot Backend

This is a FastAPI backend service for a RAG (Retrieval-Augmented Generation) chatbot. It retrieves relevant context from a Chroma vector database and uses OpenAI's models to generate contextually-aware responses.

## Setup

1. Copy the environment file:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_actual_openai_api_key
   ```

3. Build the Docker image:
   ```
   docker build -t rag-backend .
   ```

4. Run the container:
   ```
   docker run -d -p 8000:8000 --name rag-backend \
     --network=rag_default \
     -v $(pwd)/kb_files:/app/kb_files \
     -e OPENAI_API_KEY=your_actual_openai_api_key \
     rag-backend
   ```
   
   Note: This assumes you're running the Chroma DB service from the `/rag/` directory on the same Docker network.

## Usage

### Loading Knowledge Base Files

Upload text files to be indexed:

```bash
curl -X POST http://localhost:8000/api/kb/load \
  -F "files=@/path/to/your/document1.txt" \
  -F "files=@/path/to/your/document2.md"
```

### Querying the Chatbot

Send a chat query:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{
    "query": "What information can you tell me about this topic?",
    "session_id": "optional-session-id"
  }'
```

Response structure:

```json
{
  "answer": "This is the answer to your question based on the retrieved context...",
  "sources": ["document1.txt", "document2.md"],
  "session_id": "session-id-for-continuation"
}
```

## API Endpoints

- `GET /`: Health check endpoint
- `POST /api/kb/load`: Upload and index knowledge base files (accepts .txt and .md)
- `POST /api/chat`: Query the chatbot with RAG

## Environment Variables

All configuration is managed through environment variables:

- `OPENAI_API_KEY`: Your OpenAI API key
- `CHROMA_SERVER_URL`: URL of the Chroma vector DB server
- `COLLECTION_NAME`: Name of the Chroma collection to use
- `EMBED_MODEL_NAME`: OpenAI embedding model name
- `MODEL_NAME`: OpenAI chat model name
- `TEMPERATURE`: Temperature parameter (creativity)
- `MAX_TOKENS`: Maximum response length
- `TOP_P`: Top-p parameter for sampling
- `FREQUENCY_PENALTY`: Repetition penalty
- `PRESENCE_PENALTY`: Topic repetition penalty
- `TOP_K`: Number of similar chunks to retrieve
- `SYSTEM_PROMPT`: Template for the system prompt