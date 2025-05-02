FROM chromadb/chroma:latest

# No additional modifications needed as the base image has everything we need
# Environment variables should be set in Railway

EXPOSE 8000
CMD ["uvicorn", "chromadb.app:app", "--host", "0.0.0.0", "--port", "8000"]