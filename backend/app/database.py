from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv
from app.database import ENABLE_DATABASE_STORAGE

# Load environment variables
load_dotenv()

# Check if database storage is enabled
ENABLE_DATABASE_STORAGE = os.getenv("ENABLE_DATABASE_STORAGE", "true").lower() == "true"

# Get database URL from environment or use a default SQLite URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:////app/app/data/app.db")

# Create engine and session only if database storage is enabled
if ENABLE_DATABASE_STORAGE:
    db_path = "./app/app/data"
    print(f"Creating directory at {os.path.abspath(db_path)}")
    os.makedirs(db_path, exist_ok=True)
    print(f"Directory exists: {os.path.exists(db_path)}")
    
    # Create SQLAlchemy engine
    engine = create_engine(DATABASE_URL)
    
    # Create SessionLocal class
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
else:
    print("Database storage disabled, using dummy database session")
    # Create dummy engine and session
    engine = None
    
    # Define a dummy session class that does nothing
    class DummySession:
        def __init__(self):
            pass
            
        def commit(self):
            pass
            
        def close(self):
            pass
            
        def add(self, obj):
            pass
            
        def refresh(self, obj):
            pass
            
        def query(self, *args, **kwargs):
            class DummyQuery:
                def filter(self, *args, **kwargs):
                    return self
                    
                def order_by(self, *args, **kwargs):
                    return self
                    
                def limit(self, n):
                    return self
                    
                def all(self):
                    return []
                    
                def first(self):
                    return None
            return DummyQuery()
    
    # Create a dummy SessionLocal that returns DummySession
    def SessionLocal():
        return DummySession()

# Create Base class for declarative models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    if ENABLE_DATABASE_STORAGE:
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()
    else:
        # Return a dummy session that does nothing
        yield SessionLocal()

def init_db():
    if ENABLE_DATABASE_STORAGE and engine is not None:
        Base.metadata.create_all(bind=engine)
    else:
        print("Database storage disabled, skipping database initialization")