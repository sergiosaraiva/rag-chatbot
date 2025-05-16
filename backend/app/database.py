# app/database.py
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Get database URL from environment or use a default SQLite URL
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./app/data/app.db")
db_path = "./app/data"
print(f"Creating directory at {os.path.abspath(db_path)}")
os.makedirs(db_path, exist_ok=True)
print(f"Directory exists: {os.path.exists(db_path)}")

# Create SQLAlchemy engine
engine = create_engine(DATABASE_URL)

# Create SessionLocal class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create Base class for declarative models
Base = declarative_base()

# Dependency to get DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def init_db():
    Base.metadata.create_all(bind=engine)