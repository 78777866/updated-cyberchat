import os
import logging
import requests
import json
import time
from typing import Optional, Dict, Any
from models import APIKey, User
from services.encryption_service import EncryptionService
from app import db

class AIService:
    def __init__(self):
        self.encryption_service = EncryptionService()
        self.openrouter_base_url = "https://openrouter.ai/api/v1"
        self.google_ai_base_url = "https://generativelanguage.googleapis.com/v1beta"
    
    def get_active_openrouter_key(self, user_id: Optional[str] = None) -> Optional[str]:
        """Get an active OpenRouter API key, with rotation on failure"""
        # Get all active OpenRouter keys
        keys = APIKey.query.filter_by(service='openrouter', is_active=True).all()
        
        if not keys:
            return None
        
        # Try each key with rotation
        for key in keys:
            try:
                decrypted_key = self.encryption_service.decrypt(key.encrypted_key)
                # Test the key with a simple request
                if self._test_openrouter_key(decrypted_key):
                    key.last_used = db.func.now()
                    db.session.commit()
                    return decrypted_key
            except Exception as e:
                logging.warning(f"OpenRouter key {key.key_name} failed: {e}")
                continue
        
        return None
    
    def get_active_google_ai_key(self) -> Optional[str]:
        """Get an active Google AI API key"""
        key = APIKey.query.filter_by(service='google_ai', is_active=True).first()
        if key:
            return self.encryption_service.decrypt(key.encrypted_key)
        return None
    
    def _test_openrouter_key(self, api_key: str) -> bool:
        """Test if an OpenRouter API key is valid"""
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            response = requests.get(
                f"{self.openrouter_base_url}/models",
                headers=headers,
                timeout=10
            )
            
            return response.status_code == 200
        except:
            return False
    
    def get_user_preferred_model(self, user_id: Optional[str] = None, session_id: Optional[str] = None) -> str:
        """Get user's preferred model or default"""
        from models import UserModelPreference
        
        if user_id:
            preference = UserModelPreference.query.filter_by(user_id=user_id).first()
        elif session_id:
            preference = UserModelPreference.query.filter_by(session_id=session_id).first()
        else:
            preference = None
            
        return preference.preferred_model if preference else "openai/gpt-3.5-turbo"
    
    def get_chat_response(self, message: str, user_context: str, model: Optional[str] = None) -> str:
        """Get AI chat response using OpenRouter"""
        api_key = self.get_active_openrouter_key()
        if not api_key:
            return "❌ No active OpenRouter API key found. Please configure API keys in settings."
        
        # Use provided model or get user preference
        if not model:
            # Extract user_id or session_id from user_context for model preference
            if user_context and user_context.isdigit():
                model = self.get_user_preferred_model(user_id=user_context)
            else:
                model = self.get_user_preferred_model(session_id=user_context)
        
        try:
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://cyberchat-ai.replit.app",
                "X-Title": "CyberChat AI"
            }
            
            data = {
                "model": model,
                "messages": [
                    {
                        "role": "system",
                        "content": "You are CyberChat AI, a cyberpunk-themed AI assistant. You're helpful, knowledgeable, and have a slight edge with cyberpunk flair. Keep responses concise but informative."
                    },
                    {
                        "role": "user",
                        "content": message
                    }
                ],
                "max_tokens": 1000,
                "temperature": 0.7
            }
            
            response = requests.post(
                f"{self.openrouter_base_url}/chat/completions",
                headers=headers,
                json=data,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if 'choices' in result and len(result['choices']) > 0:
                    return result['choices'][0]['message']['content']
                else:
                    return "❌ Unexpected response format from AI service."
            elif response.status_code == 401:
                return "❌ API key authentication failed. Please check your OpenRouter API key."
            elif response.status_code == 429:
                # Rate limited, try with delay
                time.sleep(0.75)
                return "⏳ Rate limit reached. Please try again in a moment."
            else:
                return f"❌ AI service error: {response.status_code} - {response.text[:200]}"
                
        except requests.exceptions.Timeout:
            return "⏳ Request timed out. Please try again."
        except Exception as e:
            logging.error(f"OpenRouter API error: {e}")
            return f"❌ An error occurred: {str(e)}"
    
    def describe_image(self, image_data: bytes, filename: str) -> str:
        """Describe an image using Google AI"""
        api_key = self.get_active_google_ai_key()
        if not api_key:
            return "No Google AI API key configured for image description."
        
        try:
            import base64
            
            # Convert image to base64
            image_base64 = base64.b64encode(image_data).decode('utf-8')
            
            # Determine mime type
            mime_type = "image/jpeg"
            if filename.lower().endswith('.png'):
                mime_type = "image/png"
            
            url = f"{self.google_ai_base_url}/models/gemini-1.5-flash:generateContent?key={api_key}"
            
            data = {
                "contents": [{
                    "parts": [
                        {"text": "Describe this image in detail. Focus on the key elements, colors, composition, and overall mood."},
                        {
                            "inline_data": {
                                "mime_type": mime_type,
                                "data": image_base64
                            }
                        }
                    ]
                }]
            }
            
            headers = {"Content-Type": "application/json"}
            
            response = requests.post(url, headers=headers, json=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if 'candidates' in result and len(result['candidates']) > 0:
                    return result['candidates'][0]['content']['parts'][0]['text']
                else:
                    return "Could not generate image description."
            else:
                logging.error(f"Google AI error: {response.status_code} - {response.text}")
                return "Error describing image."
                
        except Exception as e:
            logging.error(f"Image description error: {e}")
            return f"Error describing image: {str(e)}"
    
    def process_file_content(self, file_data: Dict[str, Any], user_context: str) -> str:
        """Process file content and get AI response"""
        if file_data['type'] == 'image':
            # First describe the image
            description = self.describe_image(file_data['content'], file_data['filename'])
            
            # Then get AI response about the image
            prompt = f"I've uploaded an image: {file_data['filename']}\n\nImage description: {description}\n\nCan you tell me more about this image and what you observe?"
            return self.get_chat_response(prompt, user_context)
        
        elif file_data['type'] == 'text':
            content = file_data['content'][:4000]  # Limit content length
            prompt = f"I've uploaded a text file: {file_data['filename']}\n\nContent:\n{content}\n\nCan you summarize this content and provide insights?"
            return self.get_chat_response(prompt, user_context)
        
        elif file_data['type'] == 'pdf':
            content = file_data['content'][:4000]  # Limit content length
            prompt = f"I've uploaded a PDF file: {file_data['filename']}\n\nExtracted content:\n{content}\n\nCan you summarize this document and provide key insights?"
            return self.get_chat_response(prompt, user_context)
        
        else:
            return f"✅ File uploaded: {file_data['filename']}. File type processing not yet supported."
