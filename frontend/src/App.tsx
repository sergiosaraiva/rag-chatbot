import React, { useState, useEffect, FormEvent, useRef } from 'react';
import './App.css';
import KnowledgeManager from './KnowledgeManager';

// Get project name and user name from environment variables with fallbacks
const CHATBOT_NAME = import.meta.env.VITE_CHATBOT_NAME || '';
const CHATBOT_USER = import.meta.env.VITE_CHATBOT_USER || '';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  username?: string;
  confidence_score?: number;
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
  confidence_score?: number;
}

interface ServerConversation {
  session_id: string;
  created_at: string;
  updated_at: string;
  messages: ServerMessage[];
}

interface ServerListResponse {
  conversations: ServerConversationSummary[];
}

interface ServerConversationSummary {
  session_id: string;
  created_at: string;
  updated_at: string;
  message_count: number;
}

interface ServerMessage {
  id: number;
  role: 'user' | 'assistant';
  content: string;
  sources: string[] | null;
  timestamp: string;
  confidence_score?: number;
}

interface Message {
  role: 'user' | 'assistant';
  content: string;
  sources?: string[];
  username?: string;
  confidence_score?: number;  // Add this line
}

// Get maximum messages per conversation from environment variable with fallback
const MAX_MESSAGES = parseInt(import.meta.env.VITE_MAX_MESSAGES || '20', 10);

function App() {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConversationId, setActiveConversationId] = useState<string | null>(null);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isInitialLoading, setIsInitialLoading] = useState(true);
  const [expandedSources, setExpandedSources] = useState<{[messageIndex: number]: boolean}>({});
  const [showKnowledgeManager, setShowKnowledgeManager] = useState(false);
  const titleInputRef = useRef<HTMLInputElement>(null);
  
  // Load conversations from server and localStorage
  useEffect(() => {
    const fetchAndLoadConversations = async () => {
      setIsInitialLoading(true);
      
      // First load from local storage as a fallback
      const storedConversations = localStorage.getItem('chatConversations');
      let localConversations: Conversation[] = [];
      
      if (storedConversations) {
        try {
          const parsedConversations = JSON.parse(storedConversations);
          // Add isEditingTitle flag if it doesn't exist
          localConversations = parsedConversations.map((conv: any) => ({
            ...conv,
            isEditingTitle: false
          }));
          
          // Set conversations from localStorage first for a faster initial load
          setConversations(localConversations);
          
          // Set active conversation to the first one if available
          if (localConversations.length > 0) {
            setActiveConversationId(localConversations[0].id);
          }
        } catch (error) {
          console.error("Error parsing conversations:", error);
          localConversations = [];
        }
      }
      
      // Then fetch all conversations from server
      try {
        const allServerConversations = await fetchAllServerConversations();
        if (allServerConversations && allServerConversations.length > 0) {
          // Process server conversations
          const processedConversations = await processServerConversations(
            allServerConversations, 
            localConversations
          );
          
          if (processedConversations.length > 0) {
            setConversations(processedConversations);
            
            // Set active conversation if none is active
            if (!activeConversationId && processedConversations.length > 0) {
              setActiveConversationId(processedConversations[0].id);
            }
          } else if (localConversations.length === 0) {
            // If no conversations from server or localStorage, create a new one
            createNewConversation();
          }
        } else if (localConversations.length === 0) {
          // If no server conversations and no localStorage conversations, create a new one
          createNewConversation();
        }
      } catch (error) {
        console.error("Error fetching server conversations:", error);
        
        // If we have no local conversations either, create a new one
        if (localConversations.length === 0) {
          createNewConversation();
        }
      } finally {
        setIsInitialLoading(false);
      }
    };
    
    fetchAndLoadConversations();
  }, []);
  
  // Process server conversations and merge with local ones
  const processServerConversations = async (
    serverSummaries: ServerConversationSummary[],
    localConversations: Conversation[]
  ): Promise<Conversation[]> => {
    const result: Conversation[] = [];
    const processedSessionIds = new Set<string>();
    
    // Sort server conversations by update date (newest first)
    serverSummaries.sort((a, b) => 
      new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime()
    );
    
    // Process each server conversation
    for (const summary of serverSummaries) {
      try {
        const serverConv = await fetchServerConversation(summary.session_id);
        if (!serverConv) continue;
        
        // Check if this session ID is already in a local conversation
        const existingLocalConv = localConversations.find(
          c => c.sessionId === summary.session_id
        );
        
        if (existingLocalConv) {
          // Update existing conversation with server data
          const messages: Message[] = serverConv.messages.map(msg => ({
            role: msg.role,
            content: msg.content,
            sources: msg.sources || undefined,
            username: msg.role === 'user' ? undefined : CHATBOT_USER || undefined
          }));
          
          result.push({
            ...existingLocalConv,
            messages,
            sessionId: serverConv.session_id,
            isEditingTitle: false
          });
        } else {
          // Create new conversation from server data
          const newId = 'conv_' + Date.now() + '_' + Math.random().toString(36).substring(2, 9);
          const timestamp = new Date(serverConv.updated_at).toLocaleString('en-US', {
            year: 'numeric',
            month: '2-digit', 
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit',
            hour12: false
          });
          
          const messages: Message[] = serverConv.messages.map(msg => ({
            role: msg.role,
            content: msg.content,
            sources: msg.sources || undefined,
            username: msg.role === 'user' ? undefined : CHATBOT_USER || undefined
          }));
          
          result.push({
            id: newId,
            title: timestamp,
            messages,
            sessionId: serverConv.session_id,
            isEditingTitle: false
          });
        }
        
        processedSessionIds.add(summary.session_id);
      } catch (error) {
        console.error(`Error processing server conversation ${summary.session_id}:`, error);
      }
    }
    
    // Add local conversations that aren't on the server
    for (const localConv of localConversations) {
      if (!localConv.sessionId || !processedSessionIds.has(localConv.sessionId)) {
        result.push({
          ...localConv,
          isEditingTitle: false
        });
      }
    }
    
    // Sort by most recent first (based on ID which includes timestamp)
    result.sort((a, b) => {
      // Extract timestamp from ID or use current timestamp if not available
      const getTimestamp = (id: string) => {
        const match = id.match(/conv_(\d+)/);
        return match ? parseInt(match[1]) : Date.now();
      };
      
      return getTimestamp(b.id) - getTimestamp(a.id);
    });
    
    return result;
  };
  
  // Fetch all conversations from server
  const fetchAllServerConversations = async (): Promise<ServerConversationSummary[]> => {
    try {
      const response = await fetch('/api/conversations');
      if (!response.ok) {
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }
      
      const data: ServerListResponse = await response.json();
      return data.conversations;
    } catch (error) {
      console.error("Error fetching all conversations:", error);
      return [];
    }
  };
  
  // Fetch conversation from server
  const fetchServerConversation = async (sessionId: string): Promise<ServerConversation | null> => {
    try {
      const response = await fetch(`/api/conversations/${sessionId}`);
      if (!response.ok) {
        if (response.status === 404) {
          return null; // Conversation not found on server
        }
        throw new Error(`Server returned ${response.status}: ${response.statusText}`);
      }
      return await response.json();
    } catch (error) {
      console.error(`Error fetching conversation ${sessionId}:`, error);
      return null;
    }
  };

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
     username: CHATBOT_USER || undefined,
     confidence_score: data.confidence_score
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
   
   // Now fetch the complete conversation from server to ensure sync
   if (data.session_id) {
     try {
       const serverConv = await fetchServerConversation(data.session_id);
       if (serverConv && activeConversationId) {
         setConversations(prevConversations => 
           prevConversations.map(conv => {
             if (conv.id === activeConversationId) {
               // Convert server messages to local format
               const messages: Message[] = serverConv.messages.map(msg => ({
                 role: msg.role,
                 content: msg.content,
                 sources: msg.sources || undefined,
                 username: msg.role === 'user' ? undefined : CHATBOT_USER || undefined,
                 confidence_score: msg.confidence_score
               }));
               
               return {
                 ...conv,
                 messages,
                 sessionId: serverConv.session_id,
               };
             }
             return conv;
           })
         );
       }
     } catch (syncError) {
       console.error("Error syncing after message:", syncError);
       // Continue with local data if server sync fails
     }
   }
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

  // Function to refresh conversations from server
  const refreshConversations = async () => {
    setIsLoading(true);
    try {
      const allServerConversations = await fetchAllServerConversations();
      if (allServerConversations && allServerConversations.length > 0) {
        const processedConversations = await processServerConversations(
          allServerConversations, 
          conversations
        );
        
        if (processedConversations.length > 0) {
          setConversations(processedConversations);
        }
      }
    } catch (error) {
      console.error("Error refreshing conversations:", error);
      alert("Failed to refresh conversations from server.");
    } finally {
      setIsLoading(false);
    }
  };

  // Toggle knowledge manager visibility
  const toggleKnowledgeManager = () => {
    setShowKnowledgeManager(!showKnowledgeManager);
  };

  return (
    <div className="app-container">
      {showKnowledgeManager ? (
        <div className="knowledge-manager-container">
          <div className="knowledge-manager-header">
            <h1>{CHATBOT_NAME ? `${CHATBOT_NAME} Knowledge Manager` : 'Knowledge Manager'}</h1>
            <button className="back-to-chat-btn" onClick={toggleKnowledgeManager}>
              Back to Chat
            </button>
          </div>
          <KnowledgeManager />
        </div>
      ) : (
        <>
          <div className="sidebar">
            <div className="sidebar-header">
              <button className="new-chat-btn" onClick={createNewConversation}>New Chat</button>
              <button className="refresh-btn" onClick={refreshConversations} disabled={isLoading}>
                Refresh
              </button>
            </div>
            <div className="conversation-list">
              {isInitialLoading ? (
                <div className="loading-sidebar">Loading conversations...</div>
              ) : conversations.length === 0 ? (
                <div className="no-conversations">No conversations found</div>
              ) : (
                conversations.map((conversation) => (
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
                ))
              )}
            </div>
            <div className="sidebar-footer">
              <button className="kb-manager-btn" onClick={toggleKnowledgeManager}>
                Manage Knowledge Base
              </button>
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
              {isInitialLoading ? (
                <div className="loading-indicator">
                  <p>Loading conversations...</p>
                </div>
              ) : !activeConversation || activeConversation.messages.length === 0 ? (
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
                      {message.role === 'assistant' && message.confidence_score !== undefined && message.confidence_score !== null && (
                        <div className="confidence-score">
                          Confidence: {message.confidence_score.toFixed(1)}%
                        </div>
                      )}
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
              {isLoading && !isInitialLoading && (
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
        </>
      )}
    </div>
  );
}

export default App;