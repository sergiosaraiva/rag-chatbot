#!/usr/bin/env python3
import os
import numpy as np
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
    
    # Get or create collection
    collection = client.get_or_create_collection(name=collection_name)
    
    # Generate a dummy embedding (vector of zeros)
    test_doc_id = "test_document_001"
    embedding_dim = 384  # ChromaDB default dimension
    zero_vector = [0.0] * embedding_dim
    
    # Add the test embedding to the collection
    print(f"Adding test embedding with ID '{test_doc_id}'...")
    collection.add(
        embeddings=[zero_vector],
        documents=["This is a test document"],
        metadatas=[{"source": "smoke_test"}],
        ids=[test_doc_id]
    )
    
    # Query the collection to fetch back the embedding
    print("Querying to verify round-trip...")
    query_result = collection.get(ids=[test_doc_id])
    
    # Assert the round trip
    if test_doc_id in query_result['ids']:
        print("OK - Test document successfully added and retrieved")
    else:
        print("FAILED - Test document not retrieved correctly")
        exit(1)
    
    # Clean up - remove test document
    collection.delete(ids=[test_doc_id])
    print("Test document removed")

if __name__ == "__main__":
    main()