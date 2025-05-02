import os
import re
import uuid
from typing import List, Dict, Any
import chromadb
from openai import OpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# OpenAI API configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
EMBED_MODEL_NAME = os.getenv("EMBED_MODEL_NAME", "text-embedding-ada-002")

# Chroma configuration
CHROMA_SERVER_URL = os.getenv("CHROMA_SERVER_URL", "http://chroma:8000")
COLLECTION_NAME = os.getenv("COLLECTION_NAME", "kb_default")

# Configure OpenAI client
client = OpenAI(api_key=OPENAI_API_KEY)

def get_chroma_client():
    """
    Get a connection to the Chroma server
    """
    try:
        url = CHROMA_SERVER_URL
        print(f"Attempting to connect to ChromaDB using URL: {url}")
        
        # Parse the URL
        from urllib.parse import urlparse
        parsed_url = urlparse(url)
        protocol = parsed_url.scheme or "http"
        host = parsed_url.netloc
        if ':' in host:
            host, port_str = host.split(':')
            port = int(port_str)
        else:
            port = 443 if protocol == 'https' else 8000
        
        print(f"Connecting to ChromaDB at {protocol}://{host}:{port}")
        
        # Create client
        return chromadb.HttpClient(host=host, port=port, ssl=(protocol == 'https'))
    except Exception as e:
        import traceback
        print(f"ChromaDB connection error: {str(e)}")
        print(f"Stack trace: {traceback.format_exc()}")
        raise

def chunk_text(text: str, chunk_size: int = 2000, chunk_overlap: int = 200) -> List[str]:
    """
    Split text into chunks with overlap
    
    Args:
        text: The text to split
        chunk_size: Maximum size of each chunk
        chunk_overlap: Overlap between chunks
        
    Returns:
        List of text chunks
    """
    # Clean text - remove excessive newlines and spaces
    text = re.sub(r'\n+', '\n', text)
    text = re.sub(r' +', ' ', text)
    
    if len(text) <= chunk_size:
        return [text]
    
    chunks = []
    start = 0
    
    while start < len(text):
        end = min(start + chunk_size, len(text))
        
        # If we're not at the end and can find a good break point
        if end < len(text):
            # Try to find a period or newline to break on
            last_period = text.rfind(".", start, end)
            last_newline = text.rfind("\n", start, end)
            
            # Use the latest good break point that's not too close to the start
            good_end = max(
                last_period + 1 if last_period > start + chunk_size // 2 else 0,
                last_newline + 1 if last_newline > start + chunk_size // 2 else 0,
                start + chunk_size - chunk_overlap  # Fallback
            )
            
            end = good_end if good_end > 0 else end
        
        # Add the chunk
        chunks.append(text[start:end])
        
        # Move start position, accounting for overlap
        start = end - chunk_overlap if end < len(text) else end
    
    return chunks


def get_embeddings(texts: List[str]) -> List[List[float]]:
    """
    Generate embeddings for text chunks using OpenAI
    
    Args:
        texts: List of text chunks
        
    Returns:
        List of embedding vectors
    """
    if not texts:
        return []
    
    response = client.embeddings.create(
        input=texts,
        model=EMBED_MODEL_NAME
    )
    
    return [item.embedding for item in response.data]


def index_file(file_path: str) -> bool:
    """
    Process a file, chunk it, generate embeddings, and add to Chroma
    
    Args:
        file_path: Path to the file
        
    Returns:
        True if successful, False otherwise
    """
    try:
        # Read file content
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Extract filename for metadata
        file_name = os.path.basename(file_path)
        
        # Chunk the text
        chunks = chunk_text(content)
        
        # If no chunks, return
        if not chunks:
            print(f"No chunks generated for {file_path}")
            return False
        
        # Generate embeddings
        embeddings = get_embeddings(chunks)
        
        # Connect to Chroma and get or create collection
        chroma_client = get_chroma_client()
        collection = chroma_client.get_or_create_collection(name=COLLECTION_NAME)
        
        # Prepare document IDs and metadata
        ids = [str(uuid.uuid4()) for _ in chunks]
        metadatas = [
            {
                "source": file_name,
                "chunk_index": i,
                "total_chunks": len(chunks)
            } for i in range(len(chunks))
        ]
        
        # Add to Chroma
        collection.add(
            ids=ids,
            documents=chunks,
            embeddings=embeddings,
            metadatas=metadatas
        )
        
        print(f"Successfully indexed {file_path} with {len(chunks)} chunks")
        return True
        
    except Exception as e:
        print(f"Error indexing {file_path}: {str(e)}")
        return False


def index_directory(directory: str) -> Dict[str, bool]:
    """
    Index all .txt and .md files in a directory
    
    Args:
        directory: Directory path
        
    Returns:
        Dictionary of filenames and success status
    """
    results = {}
    
    if not os.path.exists(directory):
        os.makedirs(directory)
        print(f"Created directory {directory}")
        return results
    
    for filename in os.listdir(directory):
        if filename.endswith(('.txt', '.md')):
            file_path = os.path.join(directory, filename)
            results[filename] = index_file(file_path)
    
    return results


if __name__ == "__main__":
    # When run directly, index all files in kb_files directory
    results = index_directory("kb_files")
    print(f"Indexed {sum(results.values())} files successfully out of {len(results)}")
