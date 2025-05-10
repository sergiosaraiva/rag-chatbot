# service.py
from openai import OpenAI
import os
from sqlalchemy.orm import Session
import json

class AssessmentService:
    def __init__(self, db: Session):
        self.db = db
        self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.assessment_prompt = os.getenv("WHATSAPP_ASSESSMENT_PROMPT", 
            "Based on the following conversation, determine if our knowledge base can answer the user's query effectively. Respond with a confidence score from 0-100.")
        self.confidence_threshold = float(os.getenv("WHATSAPP_CONFIDENCE_THRESHOLD", "70"))
        
    async def assess_conversation(self, conversation_id: int):
        """Assess if the conversation can be answered with the knowledge base"""
        # Get conversation messages
        conversation = self.db.query(WhatsAppConversation).filter_by(id=conversation_id).first()
        if not conversation:
            raise Exception("Conversation not found")
            
        messages = self.db.query(WhatsAppMessage).filter_by(conversation_id=conversation_id).order_by(WhatsAppMessage.timestamp.desc()).limit(20).all()
        messages.reverse()  # Chronological order
        
        # Build context
        context = "\n".join([f"{'User' if msg.direction == 'inbound' else 'Assistant'}: {msg.content}" for msg in messages])
        
        # Call assessment prompt
        response = self.client.chat.completions.create(
            model=os.getenv("MODEL_NAME", "gpt-4o-mini"),
            messages=[
                {"role": "system", "content": self.assessment_prompt},
                {"role": "user", "content": context}
            ],
            temperature=0.2
        )
        
        # Parse confidence score - extract a number from the response
        result_text = response.choices[0].message.content
        try:
            # Extract number from text using regex
            import re
            confidence_match = re.search(r'(\d+)', result_text)
            confidence = float(confidence_match.group(1)) if confidence_match else 0
            
            # Update conversation with assessment
            conversation.confidence_score = confidence
            conversation.status = "assessed"
            self.db.commit()
            
            # Create assessment record
            assessment = {
                "confidence": confidence,
                "raw_response": result_text,
                "can_answer": confidence >= self.confidence_threshold
            }
            
            return assessment
        except Exception as e:
            return {"confidence": 0, "error": str(e), "can_answer": False}
        
# service.py (continued)
class ResponseService:
    def __init__(self, db: Session):
        self.db = db
        
    async def generate_response(self, conversation_id: int):
        """Generate a response for the conversation using the RAG service"""
        # Get conversation
        conversation = self.db.query(WhatsAppConversation).filter_by(id=conversation_id).first()
        if not conversation:
            raise Exception("Conversation not found")
            
        if conversation.confidence_score < float(os.getenv("WHATSAPP_CONFIDENCE_THRESHOLD", "70")):
            raise Exception("Confidence score too low to generate response")
            
        # Get messages
        messages = self.db.query(WhatsAppMessage).filter_by(conversation_id=conversation_id).order_by(WhatsAppMessage.timestamp.desc()).limit(20).all()
        messages.reverse()
        
        # Build question from conversation
        question = "\n".join([f"{'User' if msg.direction == 'inbound' else 'Assistant'}: {msg.content}" for msg in messages])
        
        # Call existing RAG service
        from app.api import chat
        from app.models import ChatRequest
        
        response = await chat(ChatRequest(query=question, session_id=None))
        
        # Store response
        whatsapp_response = WhatsAppResponse(
            conversation_id=conversation_id,
            generated_content=response.answer,
            confidence_score=conversation.confidence_score,
            assessment_results=json.dumps({"sources": response.sources})
        )
        self.db.add(whatsapp_response)
        self.db.commit()
        
        return whatsapp_response