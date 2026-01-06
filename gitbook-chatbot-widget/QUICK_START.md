# 🚀 Quick Start Guide

Get your GitBook chatbot widget running in 5 minutes!

## Prerequisites

- ✅ Your FastAPI backend running on port 8001
- ✅ CORS enabled (already done in your main.py)
- ✅ A GitBook space where you want to add the chatbot

## Step 1: Test Locally (2 minutes)

### Test the API
```bash
cd gitbook-chatbot-widget
./test.sh
```

This will verify:
- API is accessible
- CORS is configured
- Search endpoint works
- All files are present

### Test the Widget
```bash
# Start a local server
python -m http.server 8080

# Open in browser
# http://localhost:8080/demo.html
```

Try asking:
- "How do I configure authentication?"
- "Tell me about fleet management"
- "What is yard management?"

## Step 2: Deploy to GitBook (3 minutes)

### Option A: Quick Deploy (Copy & Paste)

1. Open your GitBook space
2. Go to Settings ⚙️ → Customize → Custom Code
3. In the **Body** section, paste the content from:
   ```
   deploy/widget-bundle.html
   ```
4. Update the API endpoint in the pasted code:
   ```javascript
   apiEndpoint: 'https://your-api-domain.com/v1/search'
   ```
5. Save and Publish ✨

### Option B: Hosted Files (Better for Production)

1. **Upload files to a CDN/hosting:**
   - Upload `chatbot-widget.js`, `chatbot-widget.css`, `config.js`
   - Recommended: Cloudflare Pages, Netlify, Vercel, GitHub Pages

2. **Update config.js** with your production API URL

3. **Add to GitBook** (Settings → Custom Code → Body):
   ```html
   <script src="https://your-cdn.com/config.js"></script>
   <script src="https://your-cdn.com/chatbot-widget.js"></script>
   <link rel="stylesheet" href="https://your-cdn.com/chatbot-widget.css">
   ```

4. Save and Publish ✨

## Step 3: Configure for Production

### Update API Endpoint

Edit `config.js`:
```javascript
const CHATBOT_CONFIG = {
  apiEndpoint: 'https://your-api.example.com/v1/search',
  // ... other settings
};
```

### Secure CORS

In your FastAPI `main.py`, update CORS to allow only your GitBook domain:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roadcast.gitbook.io",  # Your GitBook domain
        "https://your-custom-domain.com"
    ],
    allow_credentials=True,
    allow_methods=["POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)
```

### Enable HTTPS

Make sure your API uses HTTPS in production:
- Use a reverse proxy (nginx, Caddy)
- Or deploy to a platform with built-in SSL (Heroku, Railway, Render, etc.)

## Step 4: Customize (Optional)

### Change Colors

```javascript
primaryColor: '#your-brand-color',
```

### Change Position

```javascript
position: 'bottom-left',  // or top-right, top-left
```

### Custom Welcome Message

```javascript
welcomeMessage: 'Welcome! How can I help you today?',
```

### Auto-Open on Page Load

```javascript
autoOpen: true,
```

## Troubleshooting

### Widget doesn't appear
- Check browser console (F12) for errors
- Verify custom code is saved and published in GitBook

### CORS errors
```bash
# Test CORS
curl -X OPTIONS http://localhost:8001/v1/search \
  -H "Origin: https://roadcast.gitbook.io" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

See [CORS_SETUP.md](CORS_SETUP.md) for detailed CORS configuration.

### API not responding
- Verify your API is publicly accessible (not just localhost)
- Check if port 8001 is open in your firewall
- Test with: `curl http://your-api-url/v1/search`

### Results not showing
- Check API response format matches expected structure
- Open browser DevTools → Network tab to see API responses
- Verify your Elasticsearch index has data

## Testing Checklist

- [ ] API running and accessible
- [ ] CORS configured correctly
- [ ] Widget appears in demo.html
- [ ] Can send messages and get responses
- [ ] Results display correctly
- [ ] Works on mobile
- [ ] Added to GitBook
- [ ] Tested in GitBook (published version)
- [ ] HTTPS enabled for production API
- [ ] CORS restricted to GitBook domain only

## Next Steps

Once working:
1. ✅ Test on different devices/browsers
2. 📊 Monitor API usage and performance
3. 🎨 Customize styling to match your brand
4. 📈 Add analytics (optional)
5. 🔒 Implement rate limiting (recommended)

## File Structure

```
gitbook-chatbot-widget/
├── README.md                    # Overview
├── QUICK_START.md              # This file
├── GITBOOK_INTEGRATION.md      # Detailed integration guide
├── CORS_SETUP.md               # CORS configuration help
├── config.js                   # Widget configuration
├── chatbot-widget.js           # Main widget code
├── chatbot-widget.css          # Widget styles
├── demo.html                   # Local testing page
├── test.sh                     # Automated test script
└── deploy/
    └── widget-bundle.html      # All-in-one bundle for GitBook
```

## Support

- 📖 Full documentation: [GITBOOK_INTEGRATION.md](GITBOOK_INTEGRATION.md)
- 🔧 CORS issues: [CORS_SETUP.md](CORS_SETUP.md)
- 🧪 Run tests: `./test.sh`
- 🎨 Customize: Edit [config.js](config.js)

## Production Deployment Tips

1. **Use a CDN** for faster loading globally
2. **Minify files** for smaller size
3. **Enable caching** on hosted files
4. **Monitor errors** with browser error tracking
5. **Set up analytics** to track usage
6. **Implement rate limiting** on your API
7. **Use HTTPS everywhere**
8. **Restrict CORS** to specific domains only

---

**That's it! Your chatbot should now be working in GitBook! 🎉**

Need help? Check the other documentation files or test with `demo.html` first.
