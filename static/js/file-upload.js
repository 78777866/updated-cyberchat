class FileUploadManager {
    constructor() {
        this.fileInput = document.getElementById('fileInput');
        this.fileUploadBtn = document.getElementById('fileUploadBtn');
        this.fileDropZone = document.getElementById('fileDropZone');
        this.chatMessages = document.getElementById('chatMessages');
        this.messagesRemainingSpan = document.getElementById('messagesRemaining');
        
        this.allowedTypes = ['text/plain', 'application/pdf', 'image/jpeg', 'image/jpg', 'image/png'];
        this.maxFileSize = 10 * 1024 * 1024; // 10MB
        
        this.initializeEventListeners();
    }
    
    initializeEventListeners() {
        // File upload button click
        this.fileUploadBtn.addEventListener('click', () => {
            this.fileInput.click();
        });
        
        // File input change
        this.fileInput.addEventListener('change', (e) => {
            if (e.target.files.length > 0) {
                this.handleFileUpload(e.target.files[0]);
            }
        });
        
        // Drag and drop events
        this.setupDragAndDrop();
        
        // Prevent default drag behaviors on document
        ['dragenter', 'dragover', 'dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, this.preventDefaults, false);
        });
        
        // Highlight drop zone when item is dragged over it
        ['dragenter', 'dragover'].forEach(eventName => {
            document.addEventListener(eventName, this.handleDragEnter.bind(this), false);
        });
        
        ['dragleave', 'drop'].forEach(eventName => {
            document.addEventListener(eventName, this.handleDragLeave.bind(this), false);
        });
        
        // Handle dropped files
        document.addEventListener('drop', this.handleDrop.bind(this), false);
    }
    
    setupDragAndDrop() {
        // Create overlay for full-screen drop zone
        this.createDropOverlay();
    }
    
    createDropOverlay() {
        // The drop zone is already created in the HTML, just make sure it's properly styled
        if (this.fileDropZone) {
            this.fileDropZone.addEventListener('click', () => {
                this.fileInput.click();
            });
        }
    }
    
    preventDefaults(e) {
        e.preventDefault();
        e.stopPropagation();
    }
    
    handleDragEnter(e) {
        // Only show drop zone if dragging files
        if (e.dataTransfer.types.includes('Files')) {
            this.showDropZone();
        }
    }
    
    handleDragLeave(e) {
        // Hide drop zone when leaving the document
        if (e.clientX === 0 && e.clientY === 0) {
            this.hideDropZone();
        }
    }
    
    handleDrop(e) {
        this.hideDropZone();
        
        const files = e.dataTransfer.files;
        if (files.length > 0) {
            this.handleFileUpload(files[0]);
        }
    }
    
    showDropZone() {
        if (this.fileDropZone) {
            this.fileDropZone.style.display = 'flex';
            this.fileDropZone.classList.add('fade-in');
        }
    }
    
    hideDropZone() {
        if (this.fileDropZone) {
            this.fileDropZone.style.display = 'none';
            this.fileDropZone.classList.remove('fade-in');
        }
    }
    
    async handleFileUpload(file) {
        // Validate file
        const validationResult = this.validateFile(file);
        if (!validationResult.valid) {
            this.showError(validationResult.error);
            return;
        }
        
        // Show loading state
        this.setUploadState(true);
        
        // Add file upload message to chat
        this.addFileMessage(file);
        
        try {
            const formData = new FormData();
            formData.append('file', file);
            
            const response = await fetch('/api/upload_file', {
                method: 'POST',
                body: formData
            });
            
            const data = await response.json();
            
            if (response.ok) {
                // Add AI response to chat
                this.addAIResponse(data.response, data.file_info);
                this.updateMessageCount(data.messages_remaining);
            } else {
                this.addErrorMessage(`❌ Upload Error: ${data.error}`);
                if (response.status === 429) {
                    this.showMessageLimitWarning();
                }
            }
        } catch (error) {
            console.error('File upload error:', error);
            this.addErrorMessage('❌ Network error during file upload. Please try again.');
        } finally {
            this.setUploadState(false);
            this.resetFileInput();
        }
    }
    
    validateFile(file) {
        // Check file type
        if (!this.allowedTypes.includes(file.type)) {
            return {
                valid: false,
                error: `File type not supported. Allowed types: ${this.getAllowedExtensions().join(', ')}`
            };
        }
        
        // Check file size
        if (file.size > this.maxFileSize) {
            return {
                valid: false,
                error: `File too large. Maximum size: ${this.formatFileSize(this.maxFileSize)}`
            };
        }
        
        // Check for empty file
        if (file.size === 0) {
            return {
                valid: false,
                error: 'Cannot upload empty file'
            };
        }
        
        return { valid: true };
    }
    
    getAllowedExtensions() {
        const typeMap = {
            'text/plain': '.txt',
            'application/pdf': '.pdf',
            'image/jpeg': '.jpg',
            'image/jpg': '.jpg',
            'image/png': '.png'
        };
        
        return this.allowedTypes.map(type => typeMap[type] || type);
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    addFileMessage(file) {
        // Remove welcome message if it exists
        const welcomeMessage = this.chatMessages.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message message-user';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Create file preview
        const filePreview = this.createFilePreview(file);
        messageContent.appendChild(filePreview);
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-timestamp';
        messageTime.textContent = new Date().toLocaleTimeString();
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    createFilePreview(file) {
        const preview = document.createElement('div');
        preview.className = 'file-preview';
        
        // Show image preview for image files
        if (file.type.startsWith('image/')) {
            const img = document.createElement('img');
            img.src = URL.createObjectURL(file);
            img.alt = file.name;
            img.onload = () => URL.revokeObjectURL(img.src); // Clean up
            preview.appendChild(img);
        }
        
        const fileInfo = document.createElement('div');
        fileInfo.className = 'file-info';
        
        const fileIcon = this.getFileIcon(file.type);
        fileInfo.innerHTML = `
            <i class="${fileIcon} me-1"></i>
            <strong>${file.name}</strong><br>
            <small>Size: ${this.formatFileSize(file.size)} | Type: ${this.getFileTypeLabel(file.type)}</small>
        `;
        
        preview.appendChild(fileInfo);
        return preview;
    }
    
    getFileIcon(mimeType) {
        const iconMap = {
            'text/plain': 'fas fa-file-alt',
            'application/pdf': 'fas fa-file-pdf',
            'image/jpeg': 'fas fa-file-image',
            'image/jpg': 'fas fa-file-image',
            'image/png': 'fas fa-file-image'
        };
        
        return iconMap[mimeType] || 'fas fa-file';
    }
    
    getFileTypeLabel(mimeType) {
        const labelMap = {
            'text/plain': 'Text',
            'application/pdf': 'PDF',
            'image/jpeg': 'JPEG',
            'image/jpg': 'JPG',
            'image/png': 'PNG'
        };
        
        return labelMap[mimeType] || 'File';
    }
    
    addAIResponse(response, fileInfo = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message message-assistant';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Convert markdown to HTML
        const htmlContent = marked.parse(response);
        messageContent.innerHTML = htmlContent;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-timestamp';
        messageTime.textContent = new Date().toLocaleTimeString();
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    addErrorMessage(errorText) {
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message message-assistant';
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        messageContent.innerHTML = errorText;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-timestamp';
        messageTime.textContent = new Date().toLocaleTimeString();
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        
        this.chatMessages.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    setUploadState(isUploading) {
        if (this.fileUploadBtn) {
            this.fileUploadBtn.disabled = isUploading;
            this.fileUploadBtn.innerHTML = isUploading 
                ? '<i class="fas fa-spinner fa-spin"></i>' 
                : '<i class="fas fa-paperclip"></i>';
        }
        
        // Show typing indicator
        const typingIndicator = document.getElementById('typingIndicator');
        if (typingIndicator) {
            typingIndicator.style.display = isUploading ? 'flex' : 'none';
        }
    }
    
    showError(errorMessage) {
        // Create and show error alert
        const alertDiv = document.createElement('div');
        alertDiv.className = 'alert alert-danger alert-dismissible fade show';
        alertDiv.innerHTML = `
            <i class="fas fa-exclamation-triangle me-2"></i>
            ${errorMessage}
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        // Insert alert before chat messages
        this.chatMessages.parentElement.insertBefore(alertDiv, this.chatMessages);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alertDiv.parentElement) {
                alertDiv.remove();
            }
        }, 5000);
    }
    
    showMessageLimitWarning() {
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning alert-dismissible fade show';
        alert.innerHTML = `
            <strong>Message limit reached!</strong> Sign in to get higher limits.
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.chatMessages.parentElement.insertBefore(alert, this.chatMessages);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }
    
    updateMessageCount(remaining) {
        if (this.messagesRemainingSpan) {
            if (remaining === -1) {
                this.messagesRemainingSpan.textContent = 'Unlimited';
                this.messagesRemainingSpan.className = 'text-success';
            } else if (remaining <= 5) {
                this.messagesRemainingSpan.textContent = remaining;
                this.messagesRemainingSpan.className = 'text-warning';
                if (remaining === 0) {
                    this.messagesRemainingSpan.className = 'text-danger';
                }
            } else {
                this.messagesRemainingSpan.textContent = remaining;
                this.messagesRemainingSpan.className = 'text-muted';
            }
        }
    }
    
    resetFileInput() {
        if (this.fileInput) {
            this.fileInput.value = '';
        }
    }
    
    scrollToBottom() {
        this.chatMessages.scrollTop = this.chatMessages.scrollHeight;
    }
}

// Initialize file upload manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const fileUploadManager = new FileUploadManager();
    
    // Make file upload manager globally available
    window.fileUploadManager = fileUploadManager;
});

// Add CSS for drag and drop animations
document.addEventListener('DOMContentLoaded', function() {
    const style = document.createElement('style');
    style.textContent = `
        .file-drag-over {
            border-color: var(--cyber-primary) !important;
            background-color: rgba(125, 249, 255, 0.1) !important;
        }
        
        .file-upload-progress {
            position: relative;
            overflow: hidden;
        }
        
        .file-upload-progress::after {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(125, 249, 255, 0.3), transparent);
            animation: uploadProgress 1s linear infinite;
        }
        
        @keyframes uploadProgress {
            0% { left: -100%; }
            100% { left: 100%; }
        }
        
        .file-preview {
            transition: all 0.3s ease;
        }
        
        .file-preview:hover {
            transform: scale(1.02);
            box-shadow: var(--cyber-glow);
        }
        
        .file-info {
            user-select: none;
        }
        
        .alert {
            border-radius: 10px;
            border: 1px solid var(--cyber-border);
            backdrop-filter: blur(10px);
        }
        
        .alert-danger {
            background: rgba(255, 7, 58, 0.1);
            border-color: rgba(255, 7, 58, 0.3);
            color: #ff6b8a;
        }
        
        .alert-warning {
            background: rgba(255, 215, 0, 0.1);
            border-color: rgba(255, 215, 0, 0.3);
            color: #ffd700;
        }
    `;
    document.head.appendChild(style);
});
