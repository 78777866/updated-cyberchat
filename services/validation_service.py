import re
from typing import Dict, Any, List, Optional
from werkzeug.datastructures import FileStorage

class ValidationService:
    def __init__(self):
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
        self.safe_string_pattern = re.compile(r'^[a-zA-Z0-9\s\-_.,!?]+$')
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        if not email or len(email) > 254:
            return False
        return bool(self.email_pattern.match(email))
    
    def validate_string_input(self, text: str, max_length: int = 1000, allow_html: bool = False) -> Dict[str, Any]:
        """Validate string input"""
        result = {'valid': True, 'errors': []}
        
        if not isinstance(text, str):
            result['valid'] = False
            result['errors'].append('Input must be a string')
            return result
        
        if len(text) > max_length:
            result['valid'] = False
            result['errors'].append(f'Text too long (max {max_length} characters)')
        
        if not allow_html and not self.safe_string_pattern.match(text):
            result['valid'] = False
            result['errors'].append('Text contains invalid characters')
        
        return result
    
    def validate_file_upload(self, file: FileStorage, allowed_extensions: set, max_size: int) -> Dict[str, Any]:
        """Validate file upload"""
        result = {'valid': True, 'errors': []}
        
        if not file or not file.filename:
            result['valid'] = False
            result['errors'].append('No file provided')
            return result
        
        # Check file extension
        if '.' not in file.filename:
            result['valid'] = False
            result['errors'].append('File has no extension')
            return result
        
        extension = file.filename.rsplit('.', 1)[1].lower()
        if extension not in allowed_extensions:
            result['valid'] = False
            result['errors'].append(f'File type not allowed. Allowed: {", ".join(allowed_extensions)}')
        
        # Check file size
        file.seek(0, 2)  # Seek to end
        file_size = file.tell()
        file.seek(0)  # Reset to beginning
        
        if file_size > max_size:
            result['valid'] = False
            result['errors'].append(f'File too large (max {max_size // (1024*1024)}MB)')
        
        if file_size == 0:
            result['valid'] = False
            result['errors'].append('File is empty')
        
        return result
    
    def validate_api_request(self, data: Dict[str, Any], required_fields: List[str]) -> Dict[str, Any]:
        """Validate API request data"""
        result = {'valid': True, 'errors': []}
        
        if not isinstance(data, dict):
            result['valid'] = False
            result['errors'].append('Invalid request format')
            return result
        
        # Check required fields
        for field in required_fields:
            if field not in data:
                result['valid'] = False
                result['errors'].append(f'Missing required field: {field}')
            elif not data[field] or (isinstance(data[field], str) and not data[field].strip()):
                result['valid'] = False
                result['errors'].append(f'Field cannot be empty: {field}')
        
        return result
    
    def sanitize_filename(self, filename: str) -> str:
        """Sanitize filename for safe storage"""
        # Remove path components
        filename = filename.split('/')[-1].split('\\')[-1]
        
        # Remove dangerous characters
        filename = re.sub(r'[^\w\-_\.]', '_', filename)
        
        # Limit length
        if len(filename) > 255:
            name, ext = filename.rsplit('.', 1) if '.' in filename else (filename, '')
            filename = name[:250] + ('.' + ext if ext else '')
        
        return filename