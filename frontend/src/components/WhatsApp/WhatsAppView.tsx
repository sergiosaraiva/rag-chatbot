// WhatsAppView.tsx
import React, { useState, useEffect } from 'react';
import ConversationList from './ConversationList';
import ConversationDetail from './ConversationDetail';
import ResponseReview from './ResponseReview';
import { fetchConversations, syncConversations } from '../../services/whatsappService';

interface Conversation {
  id: number;
  contact_name: string;
  last_message: string;
  timestamp: string;
  unread_count: number;
  status: string;
  confidence_score: number;
}

const WhatsAppView: React.FC = () => {
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedConversation, setSelectedConversation] = useState<number | null>(null);
  const [isSyncing, setIsSyncing] = useState(false);
  const [syncLimit, setSyncLimit] = useState(20);
  
  useEffect(() => {
    loadConversations();
  }, []);
  
  const loadConversations = async () => {
    const data = await fetchConversations();
    setConversations(data);
  };
  
  const handleSync = async () => {
    setIsSyncing(true);
    try {
      await syncConversations(syncLimit);
      await loadConversations();
    } catch (error) {
      console.error('Sync failed:', error);
    } finally {
      setIsSyncing(false);
    }
  };
  
  return (
    <div className="whatsapp-container">
      <div className="whatsapp-header">
        <h2>WhatsApp Integration</h2>
        <div className="sync-controls">
          <input 
            type="number" 
            value={syncLimit} 
            onChange={(e) => setSyncLimit(parseInt(e.target.value))} 
            min="1" 
            max="50"
          />
          <button onClick={handleSync} disabled={isSyncing}>
            {isSyncing ? 'Syncing...' : 'Sync WhatsApp'}
          </button>
        </div>
      </div>
      <div className="whatsapp-content">
        <ConversationList 
          conversations={conversations}
          selectedId={selectedConversation}
          onSelect={setSelectedConversation}
        />
        {selectedConversation && (
          <ConversationDetail 
            conversationId={selectedConversation} 
          />
        )}
      </div>
    </div>
  );
};

export default WhatsAppView;