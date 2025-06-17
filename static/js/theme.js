class ThemeManager {
    constructor() {
        this.themeToggle = document.getElementById('themeToggle');
        this.themeIcon = document.getElementById('themeIcon');
        this.currentTheme = this.getStoredTheme() || 'dark';
        
        this.initializeTheme();
        this.setupEventListeners();
    }
    
    initializeTheme() {
        document.documentElement.setAttribute('data-bs-theme', this.currentTheme);
        this.updateThemeIcon();
    }
    
    setupEventListeners() {
        if (this.themeToggle) {
            this.themeToggle.addEventListener('click', () => this.toggleTheme());
        }
    }
    
    toggleTheme() {
        this.currentTheme = this.currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-bs-theme', this.currentTheme);
        this.storeTheme(this.currentTheme);
        this.updateThemeIcon();
        
        // Add transition effect
        document.body.style.transition = 'all 0.3s ease';
        setTimeout(() => {
            document.body.style.transition = '';
        }, 300);
    }
    
    updateThemeIcon() {
        if (this.themeIcon) {
            if (this.currentTheme === 'dark') {
                this.themeIcon.className = 'fas fa-sun';
                this.themeToggle.title = 'Switch to Light Theme';
            } else {
                this.themeIcon.className = 'fas fa-moon';
                this.themeToggle.title = 'Switch to Dark Theme';
            }
        }
    }
    
    getStoredTheme() {
        try {
            return localStorage.getItem('cyberchat-theme');
        } catch (e) {
            return null;
        }
    }
    
    storeTheme(theme) {
        try {
            localStorage.setItem('cyberchat-theme', theme);
        } catch (e) {
            console.log('Could not store theme preference');
        }
    }
}

// Initialize theme manager when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    const themeManager = new ThemeManager();
    
    // Make theme manager globally available
    window.themeManager = themeManager;
});

// Add smooth transitions for theme changes
document.addEventListener('DOMContentLoaded', function() {
    // Add CSS transitions for smooth theme switching
    const style = document.createElement('style');
    style.textContent = `
        * {
            transition: background-color 0.3s ease, color 0.3s ease, border-color 0.3s ease !important;
        }
        
        .fade-transition {
            opacity: 0;
            transition: opacity 0.3s ease;
        }
        
        .fade-transition.show {
            opacity: 1;
        }
    `;
    document.head.appendChild(style);
});
