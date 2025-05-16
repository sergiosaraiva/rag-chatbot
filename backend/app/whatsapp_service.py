# backend/app/whatsapp_service.py

import json
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from sqlalchemy.orm import Session
from app.whatsapp_repository import WhatsAppRepository

class WhatsAppService:
    def __init__(self, db: Session):
        self.repo = WhatsAppRepository(db)
        self.db = db
    
    def process_incoming_message(self, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process an incoming WhatsApp message
        
        Args:
            message_data: Dictionary containing:
                - phone: Sender's phone number
                - name: Sender's name (if available)
                - chat_id: WhatsApp chat identifier
                - message_id: WhatsApp message identifier
                - content: Message content
                - content_type: Type of content (text, image, etc.)
                - media_url: URL to media (if applicable)
                - timestamp: Message timestamp
                - metadata: Any additional metadata
        
        Returns:
            Dict with processed message and conversation details
        """
        # Get or create contact
        contact = self.repo.get_or_create_contact(
            phone=message_data["phone"],
            name=message_data.get("name")
        )
        
        # Update last interaction time
        self.repo.update_contact(contact.id, {"last_interaction": datetime.utcnow()})
        
        # Get or create conversation
        conversation = self.repo.get_or_create_conversation(
            contact_id=contact.id,
            whatsapp_chat_id=message_data["chat_id"]
        )
        
        # Check if message already exists
        existing_message = self.repo.get_message_by_whatsapp_id(message_data["message_id"])
        if existing_message:
            return {
                "message": existing_message.to_dict(),
                "conversation": conversation.to_dict(),
                "status": "already_processed"
            }
        
        # Create new message
        message = self.repo.create_message({
            "conversation_id": conversation.id,
            "whatsapp_message_id": message_data["message_id"],
            "direction": "incoming",
            "content_type": message_data["content_type"],
            "content": message_data["content"],
            "media_url": message_data.get("media_url"),
            "metadata": message_data.get("metadata"),
            "timestamp": message_data["timestamp"],
            "processed": False
        })
        
        # Update conversation status to unread if it wasn't already
        if conversation.status not in ["unread"]:
            self.repo.update_conversation_status(conversation.id, "unread")
        
        return {
            "message": message.to_dict(),
            "conversation": conversation.to_dict(),
            "status": "success"
        }
    
    def get_conversation_context(self, conversation_id: int, message_limit: int = 10) -> Dict[str, Any]:
        """
        Get the context of a conversation for generating a response
        
        Args:
            conversation_id: ID of the conversation
            message_limit: Maximum number of messages to retrieve
            
        Returns:
            Dict containing conversation details and recent messages
        """
        # Get conversation and contact info
        conversation = self.db.query(Conversation).filter(Conversation.id == conversation_id).first()
        if not conversation:
            return {"error": "Conversation not found"}
            
        # Get recent messages
        messages = self.repo.get_conversation_messages(conversation_id, limit=message_limit)
        
        # Format messages for context
        formatted_messages = []
        for msg in reversed(messages):  # Oldest first
            formatted_messages.append({
                "role": "user" if msg.direction == "incoming" else "assistant",
                "content": msg.content,
                "timestamp": msg.timestamp.isoformat() if msg.timestamp else None
            })
            
        return {
            "conversation": conversation.to_dict(),
            "contact": conversation.contact.to_dict(),
            "messages": [m.to_dict() for m in messages],
            "formatted_context": formatted_messages
        }
    
    def create_response_draft(self, message_id: int, rag_response: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a draft response based on RAG output
        
        Args:
            message_id: ID of the message being responded to
            rag_response: Output from the RAG system containing:
                - answer: Generated response text
                - sources: Sources used for the response
                - confidence: Confidence score (if available)
                
        Returns:
            Dict with the created response
        """
        # Get the message
        message = self.db.query(Message).filter(Message.id == message_id).first()
        if not message:
            return {"error": "Message not found"}
            
        # Create response draft
        response = self.repo.create_response({
            "message_id": message_id,
            "original_response": rag_response["answer"],
            "confidence_score": rag_response.get("confidence", 0.0),
            "sources": rag_response.get("sources", []),
            "status": "draft"
        })
        
        return {"response": response.to_dict()}
    
    def edit_response(self, response_id: int, edited_text: str) -> Dict[str, Any]:
        """
        Edit a draft response
        
        Args:
            response_id: ID of the response to edit
            edited_text: New text for the response
            
        Returns:
            Dict with the updated response
        """
        updated_response = self.repo.update_response(response_id, {
            "edited_response": edited_text,
            "status": "edited"
        })
        
        if not updated_response:
            return {"error": "Response not found"}
            
        return {"response": updated_response.to_dict()}
    
    def send_response(self, response_id: int) -> Dict[str, Any]:
        """
        Mark a response as sent
        
        Args:
            response_id: ID of the response that was sent
            
        Returns:
            Dict with the updated response and conversation
        """
        # Get the response
        response = self.db.query(Response).filter(Response.id == response_id).first()
        if not response:
            return {"error": "Response not found"}
            
        # Get the message and conversation
        message = response.message
        conversation = message.conversation
        
        # Mark response as sent
        sent_response = self.repo.mark_response_as_sent(response_id)
        
        # Mark message as processed
        self.repo.mark_message_as_processed(message.id)
        
        # Update conversation status
        self.repo.update_conversation_status(conversation.id, "answered")
        
        # Create outgoing message record for the response
        response_text = response.edited_response if response.edited_response else response.original_response
        outgoing_message = self.repo.create_message({
            "conversation_id": conversation.id,
            "whatsapp_message_id": f"out_{response_id}_{int(datetime.utcnow().timestamp())}",
            "direction": "outgoing",
            "content_type": "text",
            "content": response_text,
            "timestamp": datetime.utcnow(),
            "processed": True
        })
        
        return {
            "response": sent_response.to_dict(),
            "outgoing_message": outgoing_message.to_dict(),
            "conversation": conversation.to_dict()
        }
    
    def update_conversation_status(self, conversation_id: int, status: str) -> Dict[str, Any]:
        """
        Update the status of a conversation
        
        Args:
            conversation_id: ID of the conversation
            status: New status (unread, read, answered, skipped, dont_answer)
            
        Returns:
            Dict with the updated conversation
        """
        updated_conversation = self.repo.update_conversation_status(conversation_id, status)
        
        if not updated_conversation:
            return {"error": "Conversation not found"}
            
        return {"conversation": updated_conversation.to_dict()}
    
    def schedule_followup(self, conversation_id: int, followup_time: datetime) -> Dict[str, Any]:
        """
        Schedule a conversation for follow-up
        
        Args:
            conversation_id: ID of the conversation
            followup_time: When to follow up
            
        Returns:
            Dict with the updated conversation
        """
        updated_conversation = self.repo.set_followup_time(conversation_id, followup_time)
        
        if not updated_conversation:
            return {"error": "Conversation not found"}
            
        return {"conversation": updated_conversation.to_dict()}
    
    def get_next_conversations(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get the next conversations to process
        
        Args:
            limit: Maximum number of conversations to return
            
        Returns:
            List of conversations with their context
        """
        # First, check for any follow-ups that are due
        due_followups = self.repo.get_conversations_due_for_followup()
        for conv in due_followups:
            # Reset their scheduled followup time and set status to unread
            self.repo.update_conversation(conv.id, {
                "scheduled_followup": None,
                "status": "unread"
            })
        
        # Get unprocessed conversations
        conversations = self.repo.get_unprocessed_conversations(limit=limit)
        
        result = []
        for conv in conversations:
            context = self.get_conversation_context(conv.id)
            result.append({
                "conversation": conv.to_dict(),
                "context": context
            })
            
        return result
    
    def get_response_templates(self, category: Optional[str] = None, tags: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """
        Get response templates
        
        Args:
            category: Optional category filter
            tags: Optional tags filter
            
        Returns:
            List of templates
        """
        templates = self.repo.get_templates(category, tags)
        return [template.to_dict() for template in templates]
