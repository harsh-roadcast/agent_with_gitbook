/**
 * GitBook Chatbot Widget Configuration
 * Customize these settings to match your setup
 * 
 * GitBook URL: https://roadcast.gitbook.io/roadcast-docs/
 * For production, update apiEndpoint to your public API URL
 */

const CHATBOT_CONFIG = {
  // API Configuration
  // IMPORTANT: Update this to your production API URL before deploying to GitBook
  apiEndpoint: 'http://localhost:8001/v1/search',  // Change to https://your-api-domain.com/v1/search
  
  // Visual Configuration
  primaryColor: '#0066cc',
  secondaryColor: '#f5f5f5',
  textColor: '#333333',
  botMessageColor: '#e8f4fd',
  userMessageColor: '#0066cc',
  
  // Position: 'bottom-right', 'bottom-left', 'top-right', 'top-left'
  position: 'bottom-right',
  
  // Widget Settings
  title: 'Documentation Assistant',
  subtitle: 'Ask me anything about the docs',
  placeholder: 'Type your question...',
  welcomeMessage: 'Hi! I can help you find information in the documentation. What would you like to know?',
  
  // Feature Flags
  showTimestamp: true,
  showResultCount: true,
  enableSessions: true,
  
  // Behavior
  maxResults: 5,
  autoOpen: false, // Auto-open widget on page load
  closeOnOutsideClick: false,
  
  // Branding
  logoUrl: null, // Optional: URL to your logo image
  poweredByText: 'Powered by AI Search',
  
  // Advanced
  sessionStorageKey: 'gitbook_chatbot_session',
  debounceDelay: 300, // ms
};

// Export for use in other files
if (typeof module !== 'undefined' && module.exports) {
  module.exports = CHATBOT_CONFIG;
}
