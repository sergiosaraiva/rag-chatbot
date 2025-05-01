import { useState, useEffect, FormEvent } from 'react';
import './App.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
}

interface ChatResponse {
  answer: string;
  sources: string[];
  session_id: string;
}

function App() {
  const [sessionId, setSessionId] = useState<string | null>(localStorage.getItem('sessionId'));
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Load messages from localStorage
  useEffect(() => {
    const storedMessages = localStorage.getItem('chatMessages');
    if (storedMessages) {
      setMessages(JSON.parse(storedMessages));
    }
  }, []);

  // Save messages to localStorage
  useEffect(() => {
    localStorage.setItem('chatMessages', JSON.stringify(messages));
  }, [messages]);

  // Save sessionId to localStorage
  useEffect(() => {
    if (sessionId) {
      localStorage.setItem('sessionId', sessionId);
    }
  }, [sessionId]);

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Add user message to chat
    const userMessage: Message = {
      role: 'user',
      content: input
    };
    setMessages([...messages, userMessage]);
    setInput('');
    setIsLoading(true);

    try {
      // Send request to backend
      const response = await fetch('/api/chat', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: input,
          session_id: sessionId
        }),
      });

      if (!response.ok) {
        throw new Error('Error communicating with chatbot');
      }

      const data: ChatResponse = await response.json();
      
      // Update session ID
      setSessionId(data.session_id);
      
      // Add assistant message to chat
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources
      };
      setMessages(prevMessages => [...prevMessages, assistantMessage]);
    } catch (error) {
      console.error('Error:', error);
      // Add error message
      setMessages(prevMessages => [
        ...prevMessages, 
        { role: 'assistant', content: 'Sorry, an error occurred. Please try again.' }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    setMessages([]);
    localStorage.removeItem('chatMessages');
  };

  return (
    <div className="app-container">
      <h1>RAG Chatbot</h1>
      
      <div className="chat-container">
        {messages.length === 0 ? (
          <div className="empty-chat">
            <p>Ask me anything! I'll search the knowledge base for answers.</p>
          </div>
        ) : (
          messages.map((message, index) => (
            <div 
              key={index} 
              className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
            >
              <div className="message-content">
                <div className="message-role">{message.role === 'user' ? 'You' : 'Assistant'}</div>
                <div className="message-text">{message.content}</div>
                {message.sources && message.sources.length > 0 && (
                  <div className="message-sources">
                    <p className="sources-label">Sources:</p>
                    <ul>
                      {message.sources.map((source, idx) => (
                        <li key={idx}>{source}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            </div>
          ))
        )}
        {isLoading && (
          <div className="loading-indicator">
            <p>Thinking...</p>
          </div>
        )}
      </div>
      
      <form onSubmit={handleSubmit} className="input-form">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={isLoading}
        />
        <button type="submit" disabled={isLoading || !input.trim()}>
          Send
        </button>
        <button 
          type="button" 
          onClick={handleClearChat} 
          className="clear-button"
          disabled={isLoading || messages.length === 0}
        >
          Clear Chat
        </button>
      </form>
      
      {sessionId && (
        <div className="session-info">
          <p>Session ID: {sessionId}</p>
        </div>
      )}
    </div>
  );
}

export default App;