/**
 * GitBook Chatbot Widget
 * Vanilla JavaScript implementation - no dependencies required
 */

(function() {
  'use strict';

  // Use config or defaults
  const config = typeof CHATBOT_CONFIG !== 'undefined' ? CHATBOT_CONFIG : {
    apiEndpoint: 'http://localhost:8001/v1/search',
    primaryColor: '#0066cc',
    position: 'bottom-right',
    title: 'Documentation Assistant',
    subtitle: 'Ask me anything about the docs',
    placeholder: 'Type your question...',
    welcomeMessage: 'Hi! I can help you find information in the documentation. What would you like to know?',
    maxResults: 5,
    autoOpen: false,
    sessionStorageKey: 'gitbook_chatbot_session',
  };

  class GitBookChatbot {
    constructor() {
      this.isOpen = false;
      this.messages = [];
      this.sessionId = this.getOrCreateSession();
      this.messageCounter = 0;
      
      this.init();
    }

    init() {
      this.createWidget();
      this.attachEventListeners();
      
      // Add welcome message
      this.addBotMessage(config.welcomeMessage);
      
      // Auto-open if configured
      if (config.autoOpen) {
        setTimeout(() => this.toggleChat(), 500);
      }
    }

    getOrCreateSession() {
      let sessionId = sessionStorage.getItem(config.sessionStorageKey);
      if (!sessionId) {
        sessionId = 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
        sessionStorage.setItem(config.sessionStorageKey, sessionId);
      }
      return sessionId;
    }

    createWidget() {
      const widgetHTML = `
        <div id="gitbook-chatbot-widget" class="position-${config.position}">
          <!-- Toggle Button -->
          <button class="chatbot-toggle-button" aria-label="Toggle chat">
            <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path d="M20 2H4c-1.1 0-2 .9-2 2v18l4-4h14c1.1 0 2-.9 2-2V4c0-1.1-.9-2-2-2zm0 14H6l-2 2V4h16v12z"/>
            </svg>
            <span class="chatbot-unread-badge">1</span>
          </button>

          <!-- Chat Window -->
          <div class="chatbot-window">
            <!-- Header -->
            <div class="chatbot-header">
              <div class="chatbot-header-content">
                <h3>${config.title}</h3>
                <p>${config.subtitle}</p>
              </div>
              <button class="chatbot-close-button" aria-label="Close chat">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path d="M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z"/>
                </svg>
              </button>
            </div>

            <!-- Messages -->
            <div class="chatbot-messages" id="chatbot-messages"></div>

            <!-- Input -->
            <div class="chatbot-input-container">
              <input 
                type="text" 
                class="chatbot-input" 
                id="chatbot-input"
                placeholder="${config.placeholder}"
                aria-label="Message input"
              />
              <button class="chatbot-send-button" id="chatbot-send-button" aria-label="Send message">
                <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
                  <path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/>
                </svg>
              </button>
            </div>
          </div>
        </div>
      `;

      document.body.insertAdjacentHTML('beforeend', widgetHTML);
    }

    attachEventListeners() {
      const toggleBtn = document.querySelector('.chatbot-toggle-button');
      const closeBtn = document.querySelector('.chatbot-close-button');
      const sendBtn = document.getElementById('chatbot-send-button');
      const input = document.getElementById('chatbot-input');

      toggleBtn.addEventListener('click', () => this.toggleChat());
      closeBtn.addEventListener('click', () => this.toggleChat());
      sendBtn.addEventListener('click', () => this.sendMessage());
      
      input.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') {
          this.sendMessage();
        }
      });
    }

    toggleChat() {
      this.isOpen = !this.isOpen;
      const chatWindow = document.querySelector('.chatbot-window');
      
      if (this.isOpen) {
        chatWindow.classList.add('open');
        document.getElementById('chatbot-input').focus();
        this.hideUnreadBadge();
      } else {
        chatWindow.classList.remove('open');
      }
    }

    showUnreadBadge() {
      const badge = document.querySelector('.chatbot-unread-badge');
      badge.classList.add('show');
    }

    hideUnreadBadge() {
      const badge = document.querySelector('.chatbot-unread-badge');
      badge.classList.remove('show');
    }

    async sendMessage() {
      const input = document.getElementById('chatbot-input');
      const message = input.value.trim();
      
      if (!message) return;

      // Clear input
      input.value = '';
      
      // Add user message to UI
      this.addUserMessage(message);
      
      // Show typing indicator
      this.showTypingIndicator();
      
      // Send to API
      try {
        const messageId = `msg_${Date.now()}_${this.messageCounter++}`;
        const response = await this.callSearchAPI(message, messageId);
        
        this.hideTypingIndicator();
        
        if (response.results && response.results.length > 0) {
          this.addBotMessageWithResults(response);
        } else {
          this.addBotMessage("I couldn't find any relevant information. Could you try rephrasing your question?");
        }
      } catch (error) {
        this.hideTypingIndicator();
        this.addBotMessage("Sorry, I encountered an error. Please try again later.");
        console.error('Chatbot API error:', error);
      }
    }

    async callSearchAPI(query, messageId) {
      const response = await fetch(config.apiEndpoint, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          query: query,
          message_id: messageId,
          session_id: this.sessionId,
          limit: config.maxResults,
        }),
      });

      if (!response.ok) {
        throw new Error(`API error: ${response.status}`);
      }

      return await response.json();
    }

    addUserMessage(text) {
      const message = {
        type: 'user',
        text: text,
        timestamp: new Date(),
      };
      this.messages.push(message);
      this.renderMessage(message);
    }

    addBotMessage(text) {
      const message = {
        type: 'bot',
        text: text,
        timestamp: new Date(),
      };
      this.messages.push(message);
      this.renderMessage(message);
      
      if (!this.isOpen) {
        this.showUnreadBadge();
      }
    }

    addBotMessageWithResults(response) {
      const message = {
        type: 'bot',
        text: `I found ${response.total} relevant ${response.total === 1 ? 'result' : 'results'}:`,
        results: response.results,
        timestamp: new Date(),
      };
      this.messages.push(message);
      this.renderMessage(message);
      
      if (!this.isOpen) {
        this.showUnreadBadge();
      }
    }

    renderMessage(message) {
      const messagesContainer = document.getElementById('chatbot-messages');
      const messageHTML = this.createMessageHTML(message);
      messagesContainer.insertAdjacentHTML('beforeend', messageHTML);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    createMessageHTML(message) {
      const time = this.formatTime(message.timestamp);
      const avatarIcon = message.type === 'bot' ? '🤖' : '👤';
      
      let resultsHTML = '';
      if (message.results && message.results.length > 0) {
        resultsHTML = '<div class="chatbot-results">';
        message.results.forEach((result, index) => {
          const title = result.title || 'Documentation';
          const content = result.content || result.text || '';
          const module = result.module || '';
          const section = result.section || '';
          const url = result.url || '';
          
          // Create onclick handler to open URL in new tab
          const clickHandler = url ? `onclick="window.open('${this.escapeHtml(url)}', '_blank')"` : '';
          const cursorStyle = url ? 'style="cursor: pointer;"' : '';
          
          resultsHTML += `
            <div class="chatbot-result-item" ${clickHandler} ${cursorStyle} title="${url ? 'Click to open in new tab' : ''}">
              <div class="chatbot-result-title">${this.escapeHtml(title)}</div>
              <div class="chatbot-result-content">${this.escapeHtml(content.substring(0, 200))}${content.length > 200 ? '...' : ''}</div>
              ${module || section ? `<div class="chatbot-result-meta">${[module, section].filter(Boolean).join(' › ')}</div>` : ''}
            </div>
          `;
        });
        resultsHTML += '</div>';
      }

      return `
        <div class="chatbot-message ${message.type}">
          <div class="chatbot-message-avatar">${avatarIcon}</div>
          <div class="chatbot-message-content">
            <div class="chatbot-message-bubble">
              ${this.escapeHtml(message.text)}
              ${resultsHTML}
            </div>
            <div class="chatbot-message-time">${time}</div>
          </div>
        </div>
      `;
    }

    showTypingIndicator() {
      const messagesContainer = document.getElementById('chatbot-messages');
      const typingHTML = `
        <div class="chatbot-message bot" id="typing-indicator">
          <div class="chatbot-message-avatar">🤖</div>
          <div class="chatbot-message-content">
            <div class="chatbot-message-bubble">
              <div class="chatbot-typing">
                <div class="chatbot-typing-dot"></div>
                <div class="chatbot-typing-dot"></div>
                <div class="chatbot-typing-dot"></div>
              </div>
            </div>
          </div>
        </div>
      `;
      messagesContainer.insertAdjacentHTML('beforeend', typingHTML);
      messagesContainer.scrollTop = messagesContainer.scrollHeight;
    }

    hideTypingIndicator() {
      const indicator = document.getElementById('typing-indicator');
      if (indicator) {
        indicator.remove();
      }
    }

    formatTime(date) {
      return date.toLocaleTimeString('en-US', { 
        hour: '2-digit', 
        minute: '2-digit' 
      });
    }

    escapeHtml(text) {
      const div = document.createElement('div');
      div.textContent = text;
      return div.innerHTML;
    }
  }

  // Initialize chatbot when DOM is ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => {
      window.gitbookChatbot = new GitBookChatbot();
    });
  } else {
    window.gitbookChatbot = new GitBookChatbot();
  }

})();
