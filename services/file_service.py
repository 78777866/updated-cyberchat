import os
import logging
from werkzeug.utils import secure_filename
from werkzeug.datastructures import FileStorage
from typing import Dict, Any
import PyPDF2
from PIL import Image
import io

class FileService:
    def __init__(self):
        self.allowed_extensions = {'txt', 'pdf', 'png', 'jpg', 'jpeg'}
        self.max_file_size = 10 * 1024 * 1024  # 10MB
    
    def allowed_file(self, filename: str) -> bool:
        """Check if file extension is allowed"""
        return '.' in filename and \
               filename.rsplit('.', 1)[1].lower() in self.allowed_extensions
    
    def process_file(self, file: FileStorage) -> Dict[str, Any]:
        """Process uploaded file and return content"""
        try:
            if not file or file.filename == '':
                return {'error': 'No file provided'}
            
            if not self.allowed_file(file.filename):
                return {'error': f'File type not supported. Allowed types: {", ".join(self.allowed_extensions)}'}
            
            # Check file size
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            
            if file_size > self.max_file_size:
                return {'error': f'File too large. Maximum size: {self.max_file_size // (1024*1024)}MB'}
            
            filename = secure_filename(file.filename)
            file_extension = filename.rsplit('.', 1)[1].lower()
            
            # Read file content
            file_content = file.read()
            
            result = {
                'filename': filename,
                'size': file_size,
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
        """Process image file"""
        try:
            # Validate image
            image = Image.open(io.BytesIO(content))
            width, height = image.size
            
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
        """Process text file"""
        try:
            # Try different encodings
            encodings = ['utf-8', 'latin-1', 'cp1252']
            text_content = None
            
            for encoding in encodings:
                try:
                    text_content = content.decode(encoding)
                    break
                except UnicodeDecodeError:
                    continue
            
            if text_content is None:
                return {'error': 'Unable to decode text file'}
            
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
        """Process PDF file"""
        try:
            pdf_reader = PyPDF2.PdfReader(io.BytesIO(content))
            
            text_content = ""
            for page in pdf_reader.pages:
                try:
                    text_content += page.extract_text() + "\n"
                except Exception as e:
                    logging.warning(f"Error extracting text from PDF page: {e}")
                    continue
            
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