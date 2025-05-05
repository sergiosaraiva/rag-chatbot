import React, { useState, useEffect, FormEvent, useRef } from 'react';
import './App.css';

// Get project name and user name from environment variables with fallbacks
const CHATBOT_NAME = import.meta.env.VITE_CHATBOT_NAME || '';
const CHATBOT_USER = import.meta.env.VITE_CHATBOT_USER || '';

console.log("Env vars:", {
  name: import.meta.env.VITE_CHATBOT_NAME,
  user: import.meta.env.VITE_CHATBOT_USER
});

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  username?: string;
}

interface Conversation {
  id: string;
  title: string;
  messages: Message[];
  sessionId: string | null;
  isEditingTitle: boolean;
}

interface ChatResponse {
  answer: string;
  sources: string[];
  session_id: string;
}

// Get maximum messages per conversation from environment variable with fallback
const MAX_MESSAGES = parseInt(import.meta.env.VITE_MAX_MESSAGES || '20', 10);

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [expandedSources, setExpandedSources] = useState<{[messageIndex: number]: boolean}>({});
  const titleInputRef = useRef<HTMLInputElement>(null);

  // Load conversations from localStorage
  useEffect(() => {
    const storedConversations = localStorage.getItem('chatConversations');
    if (storedConversations) {
      try {
        const parsedConversations = JSON.parse(storedConversations);
        // Add isEditingTitle flag if it doesn't exist
        const updatedConversations = parsedConversations.map((conv: any) => ({
          ...conv,
          isEditingTitle: false
        }));
        setConversations(updatedConversations);
        
        // Set active conversation to the last one if available
        if (updatedConversations.length > 0) {
          setActiveConversationId(updatedConversations[0].id);
        }
      } catch (error) {
        console.error("Error parsing conversations:", error);
        createNewConversation();
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

  // Auto-focus on title input when editing starts
  useEffect(() => {
    if (titleInputRef.current) {
      titleInputRef.current.focus();
    }
  }, [conversations.find(conv => conv.isEditingTitle)]);

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
      title: timestamp,
      messages: [],
      sessionId: null,
      isEditingTitle: false
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

  const startEditingTitle = (id: string, e: React.MouseEvent) => {
    e.stopPropagation();
    setConversations(prevConversations => 
      prevConversations.map(conv => ({
        ...conv,
        isEditingTitle: conv.id === id
      }))
    );
  };

  const handleTitleChange = (id: string, newTitle: string) => {
    setConversations(prevConversations => 
      prevConversations.map(conv => {
        if (conv.id === id) {
          return {
            ...conv,
            title: newTitle
          };
        }
        return conv;
      })
    );
  };

  const finishEditingTitle = (id: string) => {
    setConversations(prevConversations => 
      prevConversations.map(conv => ({
        ...conv,
        isEditingTitle: conv.id === id ? false : conv.isEditingTitle
      }))
    );
  };

  const handleTitleKeyDown = (id: string, e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      finishEditingTitle(id);
    }
  };

  const updateConversationTitle = (conversation: Conversation) => {
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

  const toggleSources = (index: number) => {
    setExpandedSources(prev => ({
      ...prev,
      [index]: !prev[index]
    }));
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
    updateConversationTitle(activeConversation);

    // Add user message to chat
    const userMessage: Message = {
      role: 'user',
      content: input,
      username: activeConversation.title !== new Date(parseInt(activeConversation.id.split('_')[1])).toLocaleString('en-US', {
        year: 'numeric',
        month: '2-digit', 
        day: '2-digit',
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        hour12: false
      }) ? activeConversation.title : undefined
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
        sources: data.sources,
        username: CHATBOT_USER || undefined
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
                { 
                  role: 'assistant', 
                  content: 'Sorry, an error occurred. Please try again.',
                  username: CHATBOT_USER || undefined
                }
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

  // Function to render message content with preserved formatting
  const renderMessageContent = (content: string) => {
    return content.split('\n').map((line, index) => (
      <React.Fragment key={index}>
        {line}
        {index < content.split('\n').length - 1 && <br />}
      </React.Fragment>
    ));
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
                {conversation.isEditingTitle ? (
                  <input
                    ref={titleInputRef}
                    value={conversation.title}
                    onChange={(e) => handleTitleChange(conversation.id, e.target.value)}
                    onBlur={() => finishEditingTitle(conversation.id)}
                    onKeyDown={(e) => handleTitleKeyDown(conversation.id, e)}
                    onClick={(e) => e.stopPropagation()}
                    className="title-edit-input"
                  />
                ) : (
                  <span onClick={(e) => startEditingTitle(conversation.id, e)}>
                    {conversation.title}
                  </span>
                )}
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
        <h1>{CHATBOT_NAME ? `${CHATBOT_NAME} Chatbot` : 'Chatbot'}</h1>
        
        {activeConversation && (
          <div className="message-counter">
            {activeConversation.messages.length} / {MAX_MESSAGES} messages
          </div>
        )}
        
        <div className="chat-container">
          {!activeConversation || activeConversation.messages.length === 0 ? (
            <div className="empty-chat">
              <p>$ Ask {CHATBOT_USER ? `${CHATBOT_USER}` : 'me'} about {CHATBOT_NAME ? `${CHATBOT_NAME}` : ' my knowledge base'}! <span className="blinking-cursor"></span></p>
            </div>
          ) : (
            activeConversation.messages.map((message, index) => (
              <div 
                key={index} 
                className={`message ${message.role === 'user' ? 'user-message' : 'assistant-message'}`}
              >
                <div className="message-content">
                  <div className="message-role">
                    {message.role === 'user' ? 
                      (message.username ? `${message.username} >` : '>') : 
                      (message.username ? `${message.username} $` : '$')}
                  </div>
                  <div className="message-text">{renderMessageContent(message.content)}</div>
                  {message.sources && message.sources.length > 0 && (
                    <div className="message-sources">
                      <div className="sources-header" onClick={() => toggleSources(index)}>
                        <span className="sources-toggle">
                          {expandedSources[index] ? '−' : '+'}
                        </span>
                        <p className="sources-label">Sources</p>
                      </div>
                      {expandedSources[index] && (
                        <ul>
                          {message.sources.map((source, idx) => (
                            <li key={idx}>{source}</li>
                          ))}
                        </ul>
                      )}
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
            placeholder={`Ask your question${CHATBOT_USER ? ` to ${CHATBOT_USER}` : ''}...`}
            disabled={isLoading || !activeConversation || activeConversation.messages.length >= MAX_MESSAGES}
            className="chat-input"
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