# GitBook Chatbot Widget

A lightweight, embeddable chatbot widget for GitBook documentation that connects to your DSPy agent search API.

## Features

- 🎨 Modern, floating chat interface
- 💬 Real-time conversation with AI agent
- 📚 Contextual search across GitBook documentation
- 🔄 Session persistence
- 🎯 Easy embedding in GitBook pages
- 🚀 Zero dependencies - pure vanilla JavaScript
- 📱 Mobile responsive

## Quick Start

### 1. Configure the Widget

Edit `config.js` to point to your API endpoint:

```javascript
const CHATBOT_CONFIG = {
  apiEndpoint: 'http://localhost:8001/v1/search',
  primaryColor: '#0066cc',
  position: 'bottom-right'
};
```

### 2. Embed in GitBook

Add this script to your GitBook custom code section:

```html
<!-- GitBook Chatbot Widget -->
<script src="https://your-domain.com/chatbot-widget.js"></script>
<link rel="stylesheet" href="https://your-domain.com/chatbot-widget.css">
```

Or for local testing:

```html
<script src="./chatbot-widget.js"></script>
<link rel="stylesheet" href="./chatbot-widget.css">
```

### 3. Test Locally

Open `demo.html` in your browser to test the widget.

## Files Structure

```
gitbook-chatbot-widget/
├── README.md               # This file
├── config.js              # Configuration settings
├── chatbot-widget.js      # Main widget JavaScript
├── chatbot-widget.css     # Widget styles
├── demo.html              # Demo page for testing
└── deploy/
    └── widget-bundle.html # All-in-one deployable file
```

## Deployment Options

### Option 1: Separate Files (Recommended)
Host `chatbot-widget.js` and `chatbot-widget.css` on a CDN or static server, then reference them in GitBook.

### Option 2: All-in-One Bundle
Use `deploy/widget-bundle.html` - copy the content and paste into GitBook's custom HTML/JavaScript section.

### Option 3: GitBook Script Injection
In GitBook settings:
1. Go to Customize → Custom Code
2. Paste the widget code in the "Body" section
3. Save and publish

## API Requirements

The widget expects a POST endpoint at `/v1/search` with:

**Request:**
```json
{
  "query": "user question",
  "message_id": "unique_id",
  "session_id": "session_id",
  "limit": 5
}
```

**Response:**
```json
{
  "query": "user question",
  "results": [...],
  "total": 5,
  "session_id": "session_id",
  "timestamp": 1234567890
}
```

## Customization

### Colors
Modify CSS variables in `chatbot-widget.css`:
```css
:root {
  --chatbot-primary: #0066cc;
  --chatbot-secondary: #f5f5f5;
  --chatbot-text: #333333;
}
```

### Position
Change the position in `config.js`:
- `bottom-right` (default)
- `bottom-left`
- `top-right`
- `top-left`

### Branding
Update the widget title and icon in `chatbot-widget.js`

## CORS Configuration

Make sure your FastAPI backend has CORS enabled:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specify GitBook domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)
- Mobile browsers

## License

MIT
