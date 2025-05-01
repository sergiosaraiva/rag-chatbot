#!/usr/bin/env python3
import os
import chromadb
from chromadb.config import Settings
from dotenv import load_dotenv

def main():
    # Load environment variables from .env file
    load_dotenv()
    
    # Get configuration from environment variables
    chroma_server_url = os.getenv("CHROMA_SERVER_URL")
    collection_name = os.getenv("COLLECTION_NAME")
    
    if not chroma_server_url or not collection_name:
        print("Error: CHROMA_SERVER_URL or COLLECTION_NAME not found in .env file")
        exit(1)
    
    # Connect to Chroma server
    print(f"Connecting to Chroma server at {chroma_server_url}...")
    # Parse URL correctly for connection
    if chroma_server_url.startswith("http://"):
        host = chroma_server_url.replace("http://", "").split(":")[0]
        if host == "0.0.0.0":
            host = "localhost"  # Replace 0.0.0.0 with localhost for client connection
        port = int(chroma_server_url.split(":")[-1])
    else:
        host = chroma_server_url.split(":")[0]
        port = int(chroma_server_url.split(":")[-1])
    
    print(f"Using host: {host}, port: {port}")
    client = chromadb.HttpClient(host=host, port=port)
    
    # Check if collection exists
    collection_names = [col.name for col in client.list_collections()]
    
    if collection_name in collection_names:
        print(f"Collection '{collection_name}' already exists")
    else:
        # Create collection
        client.create_collection(name=collection_name)
        print(f"Collection '{collection_name}' has been created successfully")

if __name__ == "__main__":
    main()