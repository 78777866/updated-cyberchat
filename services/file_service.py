import os
import logging
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from typing import Dict, Any
import PyPDF2
from PIL import Image
import io
from services.security_service import SecurityService
from services.validation_service import ValidationService

class FileService:
    def __init__(self):
        self.allowed_extensions = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
        self.security_service = SecurityService()
        self.validation_service = ValidationService()
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def process_file(self, file: FileStorage) -> Dict[str, Any]:
        """Process uploaded file and return content with security checks"""
        try:
            if not file or file.filename == '':
                return {'error': 'No file provided'}
            
            # Validate file upload
            validation_result = self.validation_service.validate_file_upload(
                file, self.allowed_extensions, self.max_file_size
            )
            if not validation_result['valid']:
                return {'error': validation_result['errors'][0]}
            
            # Validate file signature
            if not self.security_service.validate_file_signature(file):
                logging.warning(f"File signature validation failed for {file.filename}")
                return {'error': 'File signature does not match extension'}
            
            filename = self.validation_service.sanitize_filename(file.filename)
            file_extension = filename.rsplit('.', 1)[1].lower()
            
            # Read file content
            file_content = file.read()
            
            # Scan for malicious content
            if self.security_service.scan_for_malicious_content(file_content):
                logging.warning(f"Malicious content detected in {filename}")
                return {'error': 'File contains potentially malicious content'}
            
            result = {
                'filename': filename,
                'size': len(file_content),
                'extension': file_extension
            }
            
            if file_extension in ['jpg', 'jpeg', 'png']:
                result.update(self._process_image(file_content, filename))
            elif file_extension == 'txt':
                result.update(self._process_text(file_content))
            elif file_extension == 'pdf':
                result.update(self._process_pdf(file_content))
            
            return result
            
        except Exception as e:
            logging.error(f"File processing error: {e}")
            return {'error': f'Error processing file: {str(e)}'}
    
    def _process_image(self, content: bytes, filename: str) -> Dict[str, Any]:
        """Process image file with security checks"""
        try:
            # Validate and process image
            image = Image.open(io.BytesIO(content))
            
            # Remove EXIF data for privacy
            if hasattr(image, '_getexif'):
                image = image.copy()
            
            width, height = image.size
            
            # Validate image dimensions (prevent zip bombs)
            if width * height > 50000000:  # 50MP limit
                return {'error': 'Image too large (dimensions)'}
            
            return {
                'type': 'image',
                'width': width,
                'height': height,
                'format': image.format,
                'content': content,  # Store raw bytes for AI processing
                'preview_url': f'data:image/{image.format.lower()};base64,{self._to_base64(content)}'
            }
        except Exception as e:
            logging.error(f"Image processing error: {e}")
            return {'error': f'Invalid image file: {str(e)}'}
    
    def _process_text(self, content: bytes) -> Dict[str, Any]:
        """Process text file with encoding detection"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252', 'ascii']
            text_content = None
            
            for encoding in encodings:
                try:
                    text_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if text_content is None:
                return {'error': 'Unable to decode text file'}
            
            # Sanitize text content
            text_content = self.security_service.sanitize_html(text_content)
            
            # Limit text length
            if len(text_content) > 100000:  # 100KB text limit
                text_content = text_content[:100000] + "\n... (content truncated)"
            
            return {
                'type': 'text',
                'content': text_content,
                'line_count': len(text_content.splitlines()),
                'character_count': len(text_content)
            }
        except Exception as e:
            logging.error(f"Text processing error: {e}")
            return {'error': f'Error processing text file: {str(e)}'}
    
    def _process_pdf(self, content: bytes) -> Dict[str, Any]:
        """Process PDF file with security checks"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            
            # Check for password protection
            if pdf_reader.is_encrypted:
                return {'error': 'Password-protected PDFs are not supported'}
            
            # Limit number of pages
            if len(pdf_reader.pages) > 100:
                return {'error': 'PDF has too many pages (max 100)'}
            
            text_content = ""
            for i, page in enumerate(pdf_reader.pages):
                try:
                    page_text = page.extract_text()
                    text_content += page_text + "\n"
                    
                    # Limit total text length
                    if len(text_content) > 100000:  # 100KB limit
                        text_content += "\n... (content truncated)"
                        break
                        
                except Exception as e:
                    logging.warning(f"Error extracting text from PDF page {i}: {e}")
                    continue
            
            # Sanitize extracted text
            text_content = self.security_service.sanitize_html(text_content)
            
            return {
                'type': 'pdf',
                'content': text_content,
                'page_count': len(pdf_reader.pages),
                'character_count': len(text_content)
            }
        except Exception as e:
            logging.error(f"PDF processing error: {e}")
            return {'error': f'Error processing PDF file: {str(e)}'}
    
    def _to_base64(self, content: bytes) -> str:
        """Convert bytes to base64 string"""
        import base64
        return base64.b64encode(content).decode('utf-8')