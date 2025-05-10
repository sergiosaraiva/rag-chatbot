# client.py
import asyncio
from baileys import WhatsAppSocket
import qrcode
import io
import base64

class WhatsAppClient:
    def __init__(self):
        self.client = None
        self.authenticated = False
        
    async def initialize(self):
        """Initialize WhatsApp connection"""
        self.client = WhatsAppSocket()
        await self.client.connect()
        
    async def get_qr_code(self):
        """Get QR code for authentication"""
        qr_data = await self.client.wait_for_qr_code()
        # Generate QR code image
        img = qrcode.make(qr_data)
        buffered = io.BytesIO()
        img.save(buffered, format="PNG")
        return base64.b64encode(buffered.getvalue()).decode("utf-8")
        
    async def fetch_conversations(self, limit=20):
        """Fetch recent conversations with unread messages"""
        if not self.authenticated:
            raise Exception("Not authenticated")
            
        chats = await self.client.get_all_chats()
        # Filter for unread messages and sort by recency
        unread_chats = [c for c in chats if c.unread_count > 0]
        sorted_chats = sorted(unread_chats, key=lambda x: x.timestamp, reverse=True)
        return sorted_chats[:limit]
        
    async def fetch_messages(self, chat_id, limit=20):
        """Fetch recent messages from a conversation"""
        if not self.authenticated:
            raise Exception("Not authenticated")
            
        messages = await self.client.get_messages(chat_id, limit)
        return messages
        
    async def send_message(self, chat_id, message):
        """Send message to a conversation"""
        if not self.authenticated:
            raise Exception("Not authenticated")
            
        await self.client.send_message(chat_id, message)
        return True