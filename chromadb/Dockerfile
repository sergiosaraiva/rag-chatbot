FROM chromadb/chroma:latest

# No additional modifications needed as the base image has everything we need
# Environment variables should be set in Railway

EXPOSE 8000
CMD ["uvicorn", "chromadb.app:app", "--workers", "1", "--host", "::", "--port", "8000", "--proxy-headers", "--log-config", "chromadb/log_config.yml", "--timeout-keep-alive", "30"]
