import os
import base64
import secrets
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class EncryptionService:
    def __init__(self):
        self.key = self._get_encryption_key()
        self.cipher = Fernet(self.key)
    
    def _get_encryption_key(self) -> bytes:
        """Generate or retrieve encryption key with proper random salt"""
        password = os.environ.get("SESSION_SECRET", "fallback_key_for_dev").encode()
        
        # Use a random salt stored in environment or generate one
        salt_b64 = os.environ.get("ENCRYPTION_SALT")
        if salt_b64:
            salt = base64.urlsafe_b64decode(salt_b64.encode())
        else:
            # Generate new salt for development
            salt = secrets.token_bytes(32)
            # In production, this should be stored securely
            os.environ["ENCRYPTION_SALT"] = base64.urlsafe_b64encode(salt).decode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
        )
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def encrypt(self, plaintext: str) -> str:
        """Encrypt a string and return base64 encoded result"""
        try:
            encrypted_data = self.cipher.encrypt(plaintext.encode())
            return base64.urlsafe_b64encode(encrypted_data).decode()
        except Exception as e:
            raise ValueError(f"Encryption failed: {e}")
    
    def decrypt(self, encrypted_data: str) -> str:
        """Decrypt base64 encoded encrypted data"""
        try:
            encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
            decrypted_data = self.cipher.decrypt(encrypted_bytes)
            return decrypted_data.decode()
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}")