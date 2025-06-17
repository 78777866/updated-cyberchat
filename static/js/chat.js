class ChatInterface {
    constructor() {
        this.messagesContainer = document.getElementById('chatMessages');
        this.messageInput = document.getElementById('messageInput');
        this.sendBtn = document.getElementById('sendBtn');
        this.searchBtn = document.getElementById('searchBtn');
        this.clearChatBtn = document.getElementById('clearChatBtn');
        this.typingIndicator = document.getElementById('typingIndicator');
        this.messagesRemainingSpan = document.getElementById('messagesRemaining');
        
        this.isTyping = false;
        this.messagesRemaining = -1;
        
        this.initializeEventListeners();
        this.loadChatHistory();
        this.updateMessageCount();
    }
    
    initializeEventListeners() {
        // Send message on button click
        this.sendBtn.addEventListener('click', () => this.sendMessage());
        
        // Send message on Enter key
        this.messageInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Search functionality
        this.searchBtn.addEventListener('click', () => this.performSearch());
        
        // Clear chat
        this.clearChatBtn.addEventListener('click', () => this.clearChat());
        
        // Auto-resize text input
        this.messageInput.addEventListener('input', () => {
            this.messageInput.style.height = 'auto';
            this.messageInput.style.height = this.messageInput.scrollHeight + 'px';
        });
    }
    
    async sendMessage() {
        const message = this.messageInput.value.trim();
        if (!message || this.isTyping) return;
        
        // Clear input and disable controls
        this.messageInput.value = '';
        this.messageInput.style.height = 'auto';
        this.setControlsDisabled(true);
        
        // Add user message to UI
        this.addMessage('user', message);
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            const response = await fetch('/api/send_message', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ message: message })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.addMessage('assistant', data.response);
                this.messagesRemaining = data.messages_remaining;
                this.updateMessageCount();
            } else {
                this.addMessage('assistant', `❌ Error: ${data.error}`);
                if (response.status === 429) {
                    this.showMessageLimitWarning();
                }
            }
        } catch (error) {
            console.error('Error sending message:', error);
            this.addMessage('assistant', '❌ Network error. Please try again.');
        } finally {
            this.hideTypingIndicator();
            this.setControlsDisabled(false);
            this.messageInput.focus();
        }
    }
    
    async performSearch() {
        const query = this.messageInput.value.trim();
        if (!query || this.isTyping) return;
        
        // Clear input and disable controls
        this.messageInput.value = '';
        this.setControlsDisabled(true);
        
        // Add search message to UI
        this.addMessage('user', `🔍 Search: ${query}`);
        
        // Show typing indicator
        this.showTypingIndicator();
        
        try {
            const response = await fetch('/api/search', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ query: query })
            });
            
            const data = await response.json();
            
            if (response.ok) {
                this.addMessage('assistant', data.results);
                this.messagesRemaining = data.messages_remaining;
                this.updateMessageCount();
            } else {
                this.addMessage('assistant', `❌ Search Error: ${data.error}`);
                if (response.status === 429) {
                    this.showMessageLimitWarning();
                }
            }
        } catch (error) {
            console.error('Error performing search:', error);
            this.addMessage('assistant', '❌ Search failed. Please try again.');
        } finally {
            this.hideTypingIndicator();
            this.setControlsDisabled(false);
            this.messageInput.focus();
        }
    }
    
    addMessage(type, content, timestamp = null, fileData = null) {
        // Remove welcome message if it exists
        const welcomeMessage = this.messagesContainer.querySelector('.welcome-message');
        if (welcomeMessage) {
            welcomeMessage.remove();
        }
        
        const messageDiv = document.createElement('div');
        messageDiv.className = `message message-${type}`;
        
        const messageContent = document.createElement('div');
        messageContent.className = 'message-content';
        
        // Handle file data display
        if (fileData) {
            const filePreview = this.createFilePreview(fileData);
            messageContent.appendChild(filePreview);
        }
        
        // Convert markdown to HTML
        const htmlContent = marked.parse(content);
        messageContent.innerHTML += htmlContent;
        
        const messageTime = document.createElement('div');
        messageTime.className = 'message-timestamp';
        messageTime.textContent = timestamp ? new Date(timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();
        
        messageDiv.appendChild(messageContent);
        messageDiv.appendChild(messageTime);
        
        this.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    createFilePreview(fileData) {
        const preview = document.createElement('div');
        preview.className = 'file-preview';
        
        if (fileData.type === 'image' && fileData.preview_url) {
            const img = document.createElement('img');
            img.src = fileData.preview_url;
            img.alt = fileData.filename;
            preview.appendChild(img);
        }
        
        const fileInfo = document.createElement('div');
        fileInfo.className = 'file-info';
        fileInfo.innerHTML = `
            <i class="fas fa-file me-1"></i>
            <strong>${fileData.filename}</strong><br>
            <small>Size: ${this.formatFileSize(fileData.size)} | Type: ${fileData.extension.toUpperCase()}</small>
        `;
        
        preview.appendChild(fileInfo);
        return preview;
    }
    
    formatFileSize(bytes) {
        if (bytes === 0) return '0 Bytes';
        const k = 1024;
        const sizes = ['Bytes', 'KB', 'MB', 'GB'];
        const i = Math.floor(Math.log(bytes) / Math.log(k));
        return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    }
    
    showTypingIndicator() {
        this.isTyping = true;
        this.typingIndicator.style.display = 'flex';
    }
    
    hideTypingIndicator() {
        this.isTyping = false;
        this.typingIndicator.style.display = 'none';
    }
    
    setControlsDisabled(disabled) {
        this.sendBtn.disabled = disabled;
        this.searchBtn.disabled = disabled;
        this.messageInput.disabled = disabled;
        
        if (disabled) {
            this.sendBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
            this.searchBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i>';
        } else {
            this.sendBtn.innerHTML = '<i class="fas fa-paper-plane"></i>';
            this.searchBtn.innerHTML = '<i class="fas fa-search"></i>';
        }
    }
    
    scrollToBottom() {
        this.messagesContainer.scrollTop = this.messagesContainer.scrollHeight;
    }
    
    async loadChatHistory() {
        try {
            const response = await fetch('/api/get_chat_history');
            const data = await response.json();
            
            if (response.ok && data.messages) {
                // Clear existing messages
                this.messagesContainer.innerHTML = '';
                
                if (data.messages.length === 0) {
                    // Show welcome message
                    this.messagesContainer.innerHTML = `
                        <div class="welcome-message text-center">
                            <div class="cyber-logo mb-3">
                                <i class="fas fa-robot"></i>
                            </div>
                            <h5>Welcome to CyberChat AI</h5>
                            <p class="text-muted">Start a conversation, upload files, or search the web!</p>
                        </div>
                    `;
                } else {
                    // Load existing messages
                    data.messages.forEach(msg => {
                        this.addMessage(msg.type, msg.content, msg.timestamp, msg.file_data);
                    });
                }
                
                this.messagesRemaining = data.messages_remaining;
                this.updateMessageCount();
            }
        } catch (error) {
            console.error('Error loading chat history:', error);
        }
    }
    
    async clearChat() {
        if (!confirm('Are you sure you want to clear the chat history?')) {
            return;
        }
        
        try {
            const response = await fetch('/api/clear_chat', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                }
            });
            
            if (response.ok) {
                this.messagesContainer.innerHTML = `
                    <div class="welcome-message text-center">
                        <div class="cyber-logo mb-3">
                            <i class="fas fa-robot"></i>
                        </div>
                        <h5>Welcome to CyberChat AI</h5>
                        <p class="text-muted">Start a conversation, upload files, or search the web!</p>
                    </div>
                `;
                this.updateMessageCount();
            }
        } catch (error) {
            console.error('Error clearing chat:', error);
        }
    }
    
    updateMessageCount() {
        if (this.messagesRemaining === -1) {
            this.messagesRemainingSpan.textContent = 'Unlimited';
            this.messagesRemainingSpan.className = 'text-success';
        } else if (this.messagesRemaining <= 5) {
            this.messagesRemainingSpan.textContent = this.messagesRemaining;
            this.messagesRemainingSpan.className = 'text-warning';
            if (this.messagesRemaining === 0) {
                this.messagesRemainingSpan.className = 'text-danger';
            }
        } else {
            this.messagesRemainingSpan.textContent = this.messagesRemaining;
            this.messagesRemainingSpan.className = 'text-muted';
        }
    }
    
    showMessageLimitWarning() {
        const alert = document.createElement('div');
        alert.className = 'alert alert-warning alert-dismissible fade show';
        alert.innerHTML = `
            <strong>Message limit reached!</strong> Sign in to get higher limits.
            <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
        `;
        
        this.messagesContainer.parentElement.insertBefore(alert, this.messagesContainer);
        
        // Auto-dismiss after 5 seconds
        setTimeout(() => {
            if (alert.parentElement) {
                alert.remove();
            }
        }, 5000);
    }
}

// Initialize chat interface when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const chat = new ChatInterface();
    
    // Make chat instance globally available for debugging
    window.chat = chat;
});
