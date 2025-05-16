# backend/app/whatsapp_client.py

import os
import json
import asyncio
import logging
from typing import Dict, Any, List, Optional, Callable
from datetime import datetime
import qrcode
import base64
from fastapi import BackgroundTasks

# Use the appropriate client library that's available in PyPI
from pywhatsapp import WhatsApp

from app.database import get_db
from app.whatsapp_service import WhatsAppService

logger = logging.getLogger("whatsapp_client")

class WhatsAppClient:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(WhatsAppClient, cls).__new__(cls)
            cls._instance.initialized = False
        return cls._instance
    
    def __init__(self):
        if self.initialized:
            return
            
        self.initialized = True
        self.client = None
        self.ready = False
        self.auth_path = os.path.join(os.getcwd(), 'whatsapp_auth')
        os.makedirs(self.auth_path, exist_ok=True)
        
        # Queue for pending actions
        self.action_queue = asyncio.Queue()
        
        # Store known non-answer chats to avoid reprocessing
        self.dont_answer_chats = set()
        
        # Track session status
        self.session_status = {
            "authenticated": False,
            "status": "disconnected",
            "qr_code": None,
            "last_connected": None,
            "last_disconnected": None,
            "error": None
        }
    
    def initialize(self, background_tasks: BackgroundTasks):
        """Initialize the WhatsApp client"""
        if self.client:
            return
            
        try:
            # Create client with local authentication
            self.client = WhatsApp(
                session_path=self.auth_path,
                headless=True
            )
            
            # Start monitoring in background
            background_tasks.add_task(self.start_client)
            
            logger.info("WhatsApp client initialization scheduled")
            
        except Exception as e:
            logger.error(f"Error initializing WhatsApp client: {str(e)}")
            self.session_status["error"] = str(e)
    
    async def start_client(self):
        """Start the WhatsApp client"""
        try:
            # Start the client and get QR if needed
            self.client.start(callback=self.on_qr_received)
            
            # Set status to authenticated if no QR needed
            if self.client.is_logged_in():
                await self.on_authenticated()
                await self.on_ready()
            
            # Start the action processor
            asyncio.create_task(self.process_action_queue())
            
            # Start the message listener
            asyncio.create_task(self.listen_for_messages())
            
        except Exception as e:
            logger.error(f"Error starting WhatsApp client: {str(e)}")
            self.session_status["error"] = str(e)
            await self.on_disconnected(str(e))
    
    def on_qr_received(self, qr_data: str):
        """Handle QR code received event"""
        self.session_status["qr_code"] = qr_data
        self.session_status["status"] = "qr_received"
        
        logger.info("WhatsApp QR code received, ready for scan")
        
        # In a real implementation, you might want to notify via a WebSocket
    
    async def on_authenticated(self):
        """Handle authenticated event"""
        self.session_status["authenticated"] = True
        self.session_status["status"] = "authenticated"
        self.session_status["qr_code"] = None
        
        logger.info("WhatsApp authenticated successfully")
    
    async def on_ready(self):
        """Handle ready event"""
        self.ready = True
        self.session_status["status"] = "connected"
        self.session_status["last_connected"] = datetime.utcnow()
        self.session_status["error"] = None
        
        logger.info("WhatsApp client is ready")
        
        # Load don't-answer chats from database
        from sqlalchemy.orm import sessionmaker
        from app.database import engine
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        try:
            # Query all conversations with dont_answer status
            from app.whatsapp_db import Conversation
            dont_answer_convs = db.query(Conversation).filter(
                Conversation.status == "dont_answer"
            ).all()
            
            # Add them to the set
            self.dont_answer_chats = set(conv.whatsapp_chat_id for conv in dont_answer_convs)
            
            logger.info(f"Loaded {len(self.dont_answer_chats)} don't-answer chats")
        finally:
            db.close()
    
    async def on_disconnected(self, reason: Optional[str] = None):
        """Handle disconnected event"""
        self.ready = False
        self.session_status["status"] = "disconnected"
        self.session_status["last_disconnected"] = datetime.utcnow()
        
        if reason:
            self.session_status["error"] = reason
            logger.warning(f"WhatsApp client disconnected: {reason}")
        else:
            logger.info("WhatsApp client disconnected")
    
    async def listen_for_messages(self):
        """Listen for incoming messages"""
        while self.ready:
            try:
                # Check for new messages
                messages = self.client.get_unread_messages()
                
                for message in messages:
                    await self.process_message(message)
                
                # Mark all as read
                self.client.mark_all_read()
                
                # Wait before checking again
                await asyncio.sleep(2)
                
            except Exception as e:
                logger.error(f"Error listening for messages: {str(e)}")
                await asyncio.sleep(5)  # Longer delay after error
    
    async def process_message(self, message: Dict[str, Any]):
        """Process a message from WhatsApp"""
        # Skip messages from us
        if message.get("from_me", False):
            return
            
        # Get chat ID
        chat_id = message.get("chat_id", "")
        
        # Skip if this chat is marked as don't answer
        if chat_id in self.dont_answer_chats:
            logger.debug(f"Skipping message from chat {chat_id} (don't answer)")
            return
        
        # Prepare message data
        message_data = {
            "phone": message.get("author", ""),
            "name": message.get("sender_name", ""),
            "chat_id": chat_id,
            "message_id": message.get("id", ""),
            "content": message.get("body", ""),
            "content_type": "text",  # Default to text
            "timestamp": datetime.fromtimestamp(message.get("timestamp", 0)/1000) if message.get("timestamp") else datetime.utcnow(),
            "metadata": {
                "is_group": message.get("is_group", False),
                "chat_name": message.get("chat_name", "")
            }
        }
        
        # Handle media messages
        if message.get("has_media", False):
            try:
                media_path = self.client.download_media(message)
                message_data["media_url"] = media_path
                message_data["content_type"] = message.get("type", "text")
            except Exception as e:
                logger.error(f"Error downloading media: {str(e)}")
        
        # Queue the message for processing
        await self.action_queue.put({
            "action": "process_message",
            "data": message_data
        })
        
        logger.info(f"Queued message for processing: {message_data['content'][:50]}...")
    
    async def process_action_queue(self):
        """Process the action queue in the background"""
        while True:
            try:
                # Get next action from queue
                action = await self.action_queue.get()
                
                if action["action"] == "process_message":
                    await self.process_incoming_message(action["data"])
                elif action["action"] == "send_message":
                    await self.send_message(
                        action["data"]["chat_id"],
                        action["data"]["content"],
                        action["data"]["response_id"]
                    )
                
                # Mark action as done
                self.action_queue.task_done()
                
            except Exception as e:
                logger.error(f"Error processing action: {str(e)}")
                
            # Small delay to prevent CPU hogging
            await asyncio.sleep(0.1)
    
    async def process_incoming_message(self, message_data: Dict[str, Any]):
        """Process an incoming message and generate a response"""
        # Get a database session
        from sqlalchemy.orm import sessionmaker
        from app.database import engine
        
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        db = SessionLocal()
        
        try:
            # Process the message
            service = WhatsAppService(db)
            result = service.process_incoming_message(message_data)
            
            if result.get("status") == "already_processed":
                logger.debug(f"Message {message_data['message_id']} already processed")
                return
                
            # Continue with the processing as before...
            # [rest of the implementation is the same]
            
        except Exception as e:
            logger.error(f"Error processing incoming message: {str(e)}")
        finally:
            db.close()
    
    async def send_message(self, chat_id: str, content: str, response_id: Optional[int] = None):
        """Send a message to a WhatsApp chat"""
        if not self.ready or not self.client:
            logger.error("WhatsApp client not ready")
            return False
            
        try:
            # Send the message
            self.client.send_message(chat_id, content)
            
            logger.info(f"Message sent to {chat_id}: {content[:50]}...")
            
            # Update the response status in the database
            # [rest of the implementation is the same]
            
            return True
            
        except Exception as e:
            logger.error(f"Error sending message: {str(e)}")
            return False
    
    async def logout(self):
        """Logout from WhatsApp"""
        if self.client:
            self.client.logout()
            self.ready = False
            self.session_status["authenticated"] = False
            self.session_status["status"] = "logged_out"
            logger.info("Logged out from WhatsApp")
    
    async def disconnect(self):
        """Disconnect the client"""
        if self.client:
            self.client.close()
            self.client = None
            self.ready = False
            self.session_status["status"] = "disconnected"
            logger.info("WhatsApp client disconnected")
    
    def get_session_status(self) -> Dict[str, Any]:
        """Get the current session status"""
        return self.session_status
