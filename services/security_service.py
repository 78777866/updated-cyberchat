import os
import hashlib
import hmac
import time
import magic
import bleach
from typing import Optional, Dict, Any
from werkzeug.datastructures import FileStorage
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64

class SecurityService:
    def __init__(self):
        self.allowed_tags = ['p', 'br', 'strong', 'em', 'u', 'ol', 'ul', 'li', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6']
        self.allowed_attributes = {}
        
    def sanitize_html(self, content: str) -> str:
        """Sanitize HTML content to prevent XSS"""
        return bleach.clean(content, tags=self.allowed_tags, attributes=self.allowed_attributes)
    
    def validate_file_signature(self, file: FileStorage) -> bool:
        """Validate file signature matches extension"""
        try:
            # Read first 2048 bytes for magic number detection
            file.seek(0)
            header = file.read(2048)
            file.seek(0)
            
            # Get MIME type from file content
            mime_type = magic.from_buffer(header, mime=True)
            
            # Get expected MIME types for file extension
            filename = file.filename.lower()
            expected_types = {
                '.txt': ['text/plain'],
                '.pdf': ['application/pdf'],
                '.jpg': ['image/jpeg'],
                '.jpeg': ['image/jpeg'],
                '.png': ['image/png']
            }
            
            for ext, types in expected_types.items():
                if filename.endswith(ext):
                    return mime_type in types
            
            return False
        except Exception:
            return False
    
    def scan_for_malicious_content(self, file_content: bytes) -> bool:
        """Basic malicious content detection"""
        try:
            # Check for common malicious patterns
            malicious_patterns = [
                b'<script',
                b'javascript:',
                b'vbscript:',
                b'onload=',
                b'onerror=',
                b'eval(',
                b'document.cookie',
                b'window.location'
            ]
            
            content_lower = file_content.lower()
            for pattern in malicious_patterns:
                if pattern in content_lower:
                    return True
            
            return False
        except Exception:
            return True  # Err on the side of caution
    
    def generate_csrf_token(self, session_id: str) -> str:
        """Generate CSRF token for session"""
        secret = os.environ.get('SESSION_SECRET', 'dev-secret')
        timestamp = str(int(time.time()))
        message = f"{session_id}:{timestamp}"
        signature = hmac.new(
            secret.encode(),
            message.encode(),
            hashlib.sha256
        ).hexdigest()
        return f"{timestamp}:{signature}"
    
    def validate_csrf_token(self, token: str, session_id: str, max_age: int = 3600) -> bool:
        """Validate CSRF token"""
        try:
            timestamp_str, signature = token.split(':', 1)
            timestamp = int(timestamp_str)
            
            # Check if token is expired
            if time.time() - timestamp > max_age:
                return False
            
            # Verify signature
            secret = os.environ.get('SESSION_SECRET', 'dev-secret')
            message = f"{session_id}:{timestamp_str}"
            expected_signature = hmac.new(
                secret.encode(),
                message.encode(),
                hashlib.sha256
            ).hexdigest()
            
            return hmac.compare_digest(signature, expected_signature)
        except Exception:
            return False
    
    def hash_password(self, password: str, salt: Optional[bytes] = None) -> tuple[str, bytes]:
        """Hash password with salt"""
        if salt is None:
            salt = os.urandom(32)
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = kdf.derive(password.encode())
        return base64.urlsafe_b64encode(key).decode(), salt
    
    def verify_password(self, password: str, hashed: str, salt: bytes) -> bool:
        """Verify password against hash"""
        try:
            new_hash, _ = self.hash_password(password, salt)
            return hmac.compare_digest(hashed, new_hash)
        except Exception:
            return False