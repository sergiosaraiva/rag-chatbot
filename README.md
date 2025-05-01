# RAG Chatbot

A Retrieval-Augmented Generation chatbot system that uses ChromaDB for vector storage and OpenAI for text generation.

## Setup Instructions

1. Copy the sample environment file:
   ```
   cp .env.example .env
   ```

2. Edit the `.env` file and add your OpenAI API key:
   ```
   OPENAI_API_KEY=your_actual_openai_api_key
   ```

3. Make the setup script executable:
   ```
   chmod +x setup_volume.sh
   ```

4. Run the setup script to create the required Docker volume and start services:
   ```
   ./setup_volume.sh
   ```

   This will:
   - Create the required `chroma_data` volume (if it doesn't exist)
   - Start all services defined in the docker-compose.yml file

## Accessing the Services

- Frontend: [http://localhost:3000](http://localhost:3000)
- Backend API: [http://localhost:8001](http://localhost:8001)
- ChromaDB (for development/debugging): [http://localhost:8005](http://localhost:8005)

## Adding Knowledge Base Files

Upload text files to be indexed:

```bash
curl -X POST http://localhost:8001/api/kb/load \
  -F "files=@/path/to/your/document1.txt" \
  -F "files=@/path/to/your/document2.md"
```

## Troubleshooting

If you encounter issues:

1. Check logs:
   ```
   docker-compose logs
   ```

2. To stop all services:
   ```
   docker-compose down
   ```

3. To reset the environment completely (⚠️ this will delete all data):
   ```
   docker-compose down
   docker volume rm chroma_data
   docker volume create chroma_data
   docker-compose up -d
   ```
