# GitBook Integration Guide

## Step-by-Step Integration

### Method 1: GitBook Custom Code (Easiest)

1. **Open your GitBook space**
   - Go to your GitBook workspace
   - Navigate to the space where you want to add the chatbot

2. **Access Customization Settings**
   - Click on the space settings (⚙️ icon)
   - Go to **Customize** → **Custom Code**

3. **Add the Widget Code**
   
   In the **"Body"** section, paste this code:

   ```html
   <!-- GitBook Chatbot Widget -->
   <style>
   [Paste contents of chatbot-widget.css here]
   </style>

   <script>
   // Configuration
   const CHATBOT_CONFIG = {
     apiEndpoint: 'https://your-api-domain.com/v1/search',
     primaryColor: '#0066cc',
     position: 'bottom-right',
     title: 'Documentation Assistant',
     subtitle: 'Ask me anything',
     placeholder: 'Type your question...',
     welcomeMessage: 'Hi! How can I help you today?',
     maxResults: 5,
     autoOpen: false
   };

   [Paste contents of chatbot-widget.js here]
   </script>
   ```

   **Or use the bundled version:**
   
   Copy everything from `deploy/widget-bundle.html` and paste it in the Body section.

4. **Update Configuration**
   - Replace `https://your-api-domain.com` with your actual API endpoint
   - Customize colors, title, and other settings as needed

5. **Save and Publish**
   - Click **Save**
   - Publish your changes
   - The chatbot will appear on all pages in that space

### Method 2: Host Files Separately (Recommended for Production)

1. **Host the Widget Files**
   
   Upload these files to a CDN or static hosting service:
   - `chatbot-widget.js`
   - `chatbot-widget.css`
   - `config.js`

   Options:
   - **Cloudflare Pages** (Free, Fast CDN)
   - **Netlify** (Free tier available)
   - **AWS S3 + CloudFront**
   - **GitHub Pages**
   - **Vercel**

2. **Add Script Tags to GitBook**

   In GitBook Custom Code > Body:

   ```html
   <script src="https://your-cdn.com/config.js"></script>
   <script src="https://your-cdn.com/chatbot-widget.js"></script>
   <link rel="stylesheet" href="https://your-cdn.com/chatbot-widget.css">
   ```

3. **Benefits of This Method**
   - Easier to update (just update hosted files)
   - Better caching
   - Smaller GitBook custom code section
   - Can use same widget across multiple spaces

### Method 3: GitBook Integrations (Advanced)

GitBook allows custom integrations. You can create a proper GitBook integration:

1. Go to [GitBook Integrations](https://www.gitbook.com/integrations)
2. Create a new integration
3. Configure it to inject your widget code
4. Install it on your spaces

## Configuration Options

### Basic Configuration

```javascript
const CHATBOT_CONFIG = {
  apiEndpoint: 'https://api.example.com/v1/search',
  primaryColor: '#0066cc',
  position: 'bottom-right',  // or 'bottom-left', 'top-right', 'top-left'
  title: 'Help Center',
  subtitle: 'Ask anything',
  placeholder: 'Type here...',
  welcomeMessage: 'Welcome! How can I help?',
  maxResults: 5,
  autoOpen: false,
};
```

### Advanced Configuration

```javascript
const CHATBOT_CONFIG = {
  // API
  apiEndpoint: 'https://api.example.com/v1/search',
  
  // Styling
  primaryColor: '#0066cc',
  secondaryColor: '#f5f5f5',
  textColor: '#333333',
  userMessageColor: '#0066cc',
  botMessageColor: '#e8f4fd',
  
  // Position
  position: 'bottom-right',
  
  // Text
  title: 'Documentation Assistant',
  subtitle: 'Powered by AI',
  placeholder: 'Ask a question...',
  welcomeMessage: 'Hello! I can help you find information.',
  poweredByText: 'Powered by Your Company',
  
  // Behavior
  maxResults: 5,
  autoOpen: false,
  closeOnOutsideClick: false,
  showTimestamp: true,
  showResultCount: true,
  
  // Branding
  logoUrl: 'https://example.com/logo.png',
};
```

## Backend Setup Requirements

### 1. API Endpoint

Your backend must expose a `/v1/search` endpoint that accepts:

**Request:**
```json
POST /v1/search
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
  "results": [
    {
      "title": "Document Title",
      "content": "Document content...",
      "module": "Module Name",
      "section": "Section Name"
    }
  ],
  "total": 5,
  "session_id": "session_id",
  "timestamp": 1234567890
}
```

### 2. CORS Configuration

**Critical:** Your API must allow requests from GitBook's domain.

See `CORS_SETUP.md` for detailed instructions.

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roadcast.gitbook.io",
        "https://your-gitbook.com"
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
```

### 3. HTTPS Required

For production:
- Your API must use HTTPS (not HTTP)
- GitBook will block insecure requests
- Use Let's Encrypt, Cloudflare, or your hosting provider's SSL

## Testing

### 1. Local Testing

```bash
# Open demo page
open demo.html

# Or start a simple server
python -m http.server 8080
# Then visit http://localhost:8080/demo.html
```

### 2. GitBook Testing

1. Add widget to a test GitBook space first
2. Open the space in a browser
3. Open DevTools Console (F12)
4. Click the chatbot button
5. Try sending a message
6. Check Console for any errors

### Common Errors:

- **CORS error:** Backend CORS not configured
- **Network error:** API endpoint incorrect or not accessible
- **404 error:** API endpoint doesn't exist
- **500 error:** Backend error - check your API logs

## Deployment Checklist

- [ ] Backend API is publicly accessible (not localhost)
- [ ] API uses HTTPS
- [ ] CORS is configured for GitBook domain
- [ ] `/v1/search` endpoint is working
- [ ] Test API with curl or Postman
- [ ] Widget files are hosted (if using Method 2)
- [ ] Config has correct API endpoint
- [ ] Widget is added to GitBook custom code
- [ ] Test in GitBook with DevTools open
- [ ] Verify on mobile/desktop
- [ ] Check different browsers

## Customizing for Your Brand

### Change Colors

In `config.js`:
```javascript
primaryColor: '#your-brand-color',
```

### Add Your Logo

```javascript
logoUrl: 'https://example.com/logo.png',
```

Then modify the header in `chatbot-widget.js` to include the logo.

### Change Position

```javascript
position: 'bottom-left',  // or 'top-right', 'top-left'
```

### Custom Welcome Message

```javascript
welcomeMessage: 'Welcome to [Your Company] Docs! How can I assist you today?',
```

## Performance Optimization

1. **Minify Files** - Use a JavaScript minifier for production
2. **Enable Caching** - Set proper cache headers on hosted files
3. **Use CDN** - Host on a CDN for global distribution
4. **Lazy Load** - Widget only loads when user interacts
5. **Compress Assets** - Enable gzip compression

## Support and Troubleshooting

### Widget not appearing
- Check browser console for errors
- Verify GitBook custom code is saved and published
- Check if JavaScript is enabled

### Chat button appears but doesn't open
- Check for JavaScript errors in console
- Verify no conflicting styles from GitBook theme

### Messages not sending
- Check API endpoint in config
- Verify CORS configuration
- Check network tab in DevTools for failed requests

### Results not displaying
- Verify API response format matches expected structure
- Check backend logs for errors
- Test API directly with curl/Postman

## Advanced Customization

See the source code comments in:
- `chatbot-widget.js` - Main functionality
- `chatbot-widget.css` - Styling
- `config.js` - Configuration options

All code uses vanilla JavaScript - no dependencies required!

## Updates and Maintenance

To update the widget:
1. Modify the source files
2. Test with `demo.html`
3. If using Method 1: Update code in GitBook
4. If using Method 2: Re-upload to CDN (cached files will update gradually)

## Security Notes

- Never expose API keys in the widget code
- Use backend authentication if needed
- Implement rate limiting on your API
- Monitor for abuse
- Validate and sanitize all inputs on the backend

## Need Help?

- Check `README.md` for overview
- Check `CORS_SETUP.md` for CORS issues
- Test with `demo.html` first
- Check browser console for errors
- Verify API is working with curl/Postman
