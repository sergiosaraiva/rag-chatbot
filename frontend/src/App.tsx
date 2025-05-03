import { useState, useEffect, FormEvent } from 'react';
import './App.css';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  sessionId: string | null;
}

interface ChatResponse {
  answer: string;
  sources: string[];
  session_id: string;
}

// Maximum messages per conversation
const MAX_MESSAGES = 20;

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  // Load conversations from localStorage
  useEffect(() => {
    const storedConversations = localStorage.getItem('chatConversations');
    if (storedConversations) {
      const parsedConversations = JSON.parse(storedConversations);
      setConversations(parsedConversations);
      
      // Set active conversation to the last one if available
      if (parsedConversations.length > 0) {
        setActiveConversationId(parsedConversations[0].id);
      }
    } else {
      // Create a default conversation if none exists
      createNewConversation();
    }
  }, []);

  // Save conversations to localStorage
  useEffect(() => {
    if (conversations.length > 0) {
      localStorage.setItem('chatConversations', JSON.stringify(conversations));
    }
  }, [conversations]);

  // Get active conversation
  const activeConversation = conversations.find(conv => conv.id === activeConversationId) || null;

  const createNewConversation = () => {
    const newId = 'conv_' + Date.now();
    const timestamp = new Date().toLocaleString('en-US', {
      year: 'numeric',
      month: '2-digit', 
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false
    });
    const newConversation: Conversation = {
      id: newId,
      title: timestamp,  // Changed from "Conversation ${conversations.length + 1}"
      messages: [],
      sessionId: null
    };
    
    setConversations([newConversation, ...conversations]);
    setActiveConversationId(newId);
  };

  const deleteConversation = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    const updatedConversations = conversations.filter(conv => conv.id !== id);
    setConversations(updatedConversations);
    
    // If we deleted the active conversation, set active to the first one or null
    if (id === activeConversationId) {
      setActiveConversationId(updatedConversations.length > 0 ? updatedConversations[0].id : null);
    }
    
    // If no conversations left, create a new one
    if (updatedConversations.length === 0) {
      createNewConversation();
    }
  };

  const updateConversationTitle = (conversation: Conversation, userMessage: string) => {
    // Only update title if this is the first message
    if (conversation.messages.length === 0) {
      const timestamp = new Date().toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit',
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      });
      
      setConversations(prevConversations => 
        prevConversations.map(conv => 
          conv.id === conversation.id 
            ? { ...conv, title: timestamp } 
            : conv
        )
      );
    }
  };

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    if (!input.trim() || !activeConversation) return;
    
    // Check if we've reached the message limit
    if (activeConversation.messages.length >= MAX_MESSAGES) {
      alert(`This conversation has reached the limit of ${MAX_MESSAGES} messages. Please start a new one.`);
      return;
    }

    // Update the conversation title if this is the first message
    updateConversationTitle(activeConversation, input);

    // Add user message to chat
    const userMessage: Message = {
      role: 'user',
      content: input
    };
    
    const updatedConversations = conversations.map(conv => {
      if (conv.id === activeConversationId) {
        return {
          ...conv,
          messages: [...conv.messages, userMessage]
        };
      }
      return conv;
    });
    
    setConversations(updatedConversations);
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
          session_id: activeConversation.sessionId
        }),
      });

      if (!response.ok) {
        throw new Error('Error communicating with chatbot');
      }

      const data: ChatResponse = await response.json();
      
      // Add assistant message to chat
      const assistantMessage: Message = {
        role: 'assistant',
        content: data.answer,
        sources: data.sources
      };
      
      setConversations(prevConversations => 
        prevConversations.map(conv => {
          if (conv.id === activeConversationId) {
            return {
              ...conv,
              messages: [...conv.messages, assistantMessage],
              sessionId: data.session_id
            };
          }
          return conv;
        })
      );
    } catch (error) {
      console.error('Error:', error);
      // Add error message
      setConversations(prevConversations => 
        prevConversations.map(conv => {
          if (conv.id === activeConversationId) {
            return {
              ...conv,
              messages: [
                ...conv.messages, 
                { role: 'assistant', content: 'Sorry, an error occurred. Please try again.' }
              ]
            };
          }
          return conv;
        })
      );
    } finally {
      setIsLoading(false);
    }
  };

  const handleClearChat = () => {
    if (activeConversationId) {
      const updatedConversations = conversations.map(conv => {
        if (conv.id === activeConversationId) {
          return {
            ...conv,
            messages: [],
            sessionId: null
          };
        }
        return conv;
      });
      
      setConversations(updatedConversations);
    }
  };

  return (
    <div className="app-container">
      <div className="sidebar">
        <div className="sidebar-header">
          <button className="new-chat-btn" onClick={createNewConversation}>New</button>
        </div>
        <div className="conversation-list">
          {conversations.map((conversation) => (
            <div 
              key={conversation.id}
              className={`conversation-item ${conversation.id === activeConversationId ? 'active' : ''}`}
              onClick={() => setActiveConversationId(conversation.id)}
            >
              <div className="conversation-title">
                {conversation.title}
              </div>
              <button 
                className="delete-convo-btn"
                onClick={(e) => deleteConversation(conversation.id, e)}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      </div>
      
      <div className="main-content">
        <h1>Immigration Chatbot</h1>
        
        {activeConversation && (
          <div className="message-counter">
            {activeConversation.messages.length} / {MAX_MESSAGES} messages
          </div>
        )}
        
        <div className="chat-container">
          {!activeConversation || activeConversation.messages.length === 0 ? (
            <div className="empty-chat">
              <p>$ Ask me anything about the KB! <span className="blinking-cursor"></span></p>
            </div>
          ) : (
            activeConversation.messages.map((message, index) => (
              <div 
                key={index} 
                className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
              >
                <div className="message-content">
                  <div className="message-role">{message.role === 'user' ? '>' : '$'}</div>
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
              <p>Processing...</p>
            </div>
          )}
        </div>
        
        <form onSubmit={handleSubmit} className="input-form">
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type your query..."
            disabled={isLoading || !activeConversation || activeConversation.messages.length >= MAX_MESSAGES}
          />
          <button 
            type="submit" 
            disabled={isLoading || !input.trim() || !activeConversation || activeConversation.messages.length >= MAX_MESSAGES}
          >
            Send
          </button>
          <button 
            type="button" 
            onClick={handleClearChat} 
            className="clear-button"
            disabled={isLoading || !activeConversation || activeConversation.messages.length === 0}
          >
            Clear
          </button>
        </form>
        
        {activeConversation && activeConversation.sessionId && (
          <div className="session-info">
            <p>Session ID: {activeConversation.sessionId}</p>
          </div>
        )}
      </div>
    </div>
  );
}

export default App;