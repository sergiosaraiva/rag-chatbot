# Immigration Chatbot Frontend

A React + TypeScript frontend for the Immigration chatbot system.

## Setup and Run

1. Build the Docker image:
   ```
   docker build -t rag-frontend .
   ```

2. Run the container:
   ```
   docker run -d -p 3000:3000 --name rag-frontend --network=rag_default rag-frontend
   ```

   Note: This assumes you're running the backend and Chroma DB services on the same Docker network.

## Usage

1. Open your browser and navigate to [http://localhost:3000](http://localhost:3000)
2. Type a question in the input box and press Send
3. The chatbot will respond with an answer based on the knowledge base
4. Sources used to generate the answer will be displayed below each response
5. Your session continues across page refreshes through localStorage
6. The session ID is preserved to maintain conversation context with the backend

## Features

- Persistent chat history using localStorage
- Session tracking for conversational context
- Display of source documents used for answers
- Responsive design for desktop and mobile use
- Loading indicator during API calls
- Clear chat button to start a new conversation
