# Production Deployment Guide

## Your GitBook Documentation
**URL:** https://roadcast.gitbook.io/roadcast-docs/

## Pre-Deployment Checklist

### 1. API Setup
- [ ] Your API is publicly accessible (not localhost)
- [ ] API uses HTTPS (required for GitBook)
- [ ] CORS is configured to allow `https://roadcast.gitbook.io`

### 2. Update API Endpoint

In `config.js`, change:
```javascript
// FROM:
apiEndpoint: 'http://localhost:8001/v1/search',

// TO:
apiEndpoint: 'https://your-api-domain.com/v1/search',
```

### 3. CORS Configuration

In your FastAPI `main.py`:
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roadcast.gitbook.io",  # Your GitBook domain
        "https://roadcast.gitbook.io/*", # All GitBook pages
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
```

### 4. Deploy Widget to GitBook

#### Option A: Direct Embedding (Recommended)

1. Go to https://roadcast.gitbook.io/roadcast-docs/
2. Click Settings → Customize → Custom Code
3. In the **Body** section, paste:

```html
<style>
[Copy entire content from chatbot-widget.css]
</style>

<script>
// Configuration
const CHATBOT_CONFIG = {
  apiEndpoint: 'https://YOUR-API-DOMAIN.com/v1/search', // UPDATE THIS!
  primaryColor: '#0066cc',
  position: 'bottom-right',
  title: 'Roadcast Docs Assistant',
  subtitle: 'Ask me anything',
  placeholder: 'Ask about fleet management...',
  welcomeMessage: 'Hi! I can help you find information about Roadcast. What would you like to know?',
  maxResults: 5,
  autoOpen: false
};

[Copy entire content from chatbot-widget.js]
</script>
```

4. Save and Publish

#### Option B: Hosted Files (Better for Updates)

1. **Host the files** on a CDN:
   - Cloudflare Pages (Free)
   - Netlify (Free)
   - Vercel (Free)
   - AWS S3 + CloudFront
   - GitHub Pages

2. **Upload these files:**
   - `config.js` (with updated API endpoint)
   - `chatbot-widget.js`
   - `chatbot-widget.css`

3. **In GitBook Custom Code (Body section):**

```html
<script src="https://your-cdn.com/config.js"></script>
<script src="https://your-cdn.com/chatbot-widget.js"></script>
<link rel="stylesheet" href="https://your-cdn.com/chatbot-widget.css">
```

## Example Production Configuration

```javascript
const CHATBOT_CONFIG = {
  // Production API endpoint
  apiEndpoint: 'https://api.roadcast.io/v1/search',
  
  // Roadcast branding
  primaryColor: '#0066cc',
  position: 'bottom-right',
  
  // Custom messages for Roadcast
  title: 'Roadcast Assistant',
  subtitle: 'Fleet Management Help',
  placeholder: 'Ask about tracking, yard management, reports...',
  welcomeMessage: 'Welcome to Roadcast Docs! I can help you find information about fleet management, tracking, billing, and more. What would you like to know?',
  
  // Behavior
  maxResults: 5,
  autoOpen: false,
  
  // Branding
  poweredByText: 'Powered by Roadcast AI',
};
```

## Testing After Deployment

### 1. Test in GitBook
1. Publish your GitBook space
2. Visit: https://roadcast.gitbook.io/roadcast-docs/
3. Look for the chat button in bottom-right corner
4. Click and try asking questions

### 2. Test Queries
Try these questions to verify it works:
- "How do I configure authentication?"
- "Tell me about yard management"
- "What is fleet tracking?"
- "How do I set up billing?"
- "Explain live tracking features"

### 3. Check Browser Console
1. Open DevTools (F12)
2. Look for any errors
3. Check Network tab for API calls
4. Verify CORS headers are present

## Common Issues

### Widget not appearing
- Check GitBook custom code is saved and published
- Clear browser cache (Ctrl+Shift+R)
- Check browser console for JavaScript errors

### CORS errors
```
Access to fetch at 'https://api.example.com/v1/search' from origin 
'https://roadcast.gitbook.io' has been blocked by CORS policy
```

**Fix:** Update your FastAPI CORS configuration (see step 3 above)

### API not responding
- Verify API is publicly accessible
- Test with curl:
```bash
curl -X POST https://your-api.com/v1/search \
  -H "Content-Type: application/json" \
  -H "Origin: https://roadcast.gitbook.io" \
  -d '{"query":"test","message_id":"msg1","session_id":"s1","limit":5}'
```

### Results not opening GitBook pages
- Verify search results contain valid `url` fields
- Check that URLs match your GitBook domain
- Open browser console to see any errors

## API Hosting Options

### Free/Low-Cost Options:
1. **Railway** - Easy deployment, free tier
2. **Render** - Free tier available
3. **Fly.io** - Free allowance
4. **Heroku** - Free dyno (with limitations)
5. **Google Cloud Run** - Pay per use
6. **AWS Lambda + API Gateway** - Pay per request

### Requirements:
- Must support HTTPS
- Must allow CORS configuration
- Port 443 (HTTPS) must be accessible

## Security Recommendations

1. **Restrict CORS** to only your GitBook domain
2. **Add rate limiting** to prevent abuse
3. **Monitor API usage** 
4. **Use environment variables** for sensitive config
5. **Enable API authentication** (if needed)
6. **Set up error tracking** (Sentry, etc.)

## Monitoring

### What to Monitor:
- API response times
- Error rates
- Popular queries
- Number of sessions
- CORS errors

### Recommended Tools:
- API: FastAPI built-in logs
- Frontend: Browser error tracking
- Analytics: Google Analytics or Mixpanel (optional)

## Updating the Widget

### When you update the code:
1. Update the files on your CDN (if using hosted files)
2. Or update the code in GitBook custom code
3. Clear CDN cache if applicable
4. Test on a staging GitBook space first

### Versioning:
Add version to URLs:
```html
<script src="https://your-cdn.com/chatbot-widget.js?v=1.1.0"></script>
```

## Support

If you encounter issues:
1. Check [QUICK_START.md](QUICK_START.md)
2. Review [CORS_SETUP.md](CORS_SETUP.md)
3. Test with [demo.html](demo.html) locally first
4. Check browser console for errors
5. Verify API is responding

---

**Your GitBook:** https://roadcast.gitbook.io/roadcast-docs/

**Ready to deploy!** Follow the checklist above and you'll have a working chatbot in your GitBook documentation.
