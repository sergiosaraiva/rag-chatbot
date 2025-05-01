#!/bin/bash

# Check if the chroma_data volume exists
if ! docker volume inspect chroma_data > /dev/null 2>&1; then
  echo "Creating chroma_data volume..."
  docker volume create chroma_data
else
  echo "chroma_data volume already exists."
fi

# Start the containers with docker-compose
echo "Starting docker containers..."
docker-compose up -d