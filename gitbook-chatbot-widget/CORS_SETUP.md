# CORS Setup Guide

## Why CORS is Needed

When the chatbot widget is embedded in GitBook (running on a different domain), the browser will block API requests due to Cross-Origin Resource Sharing (CORS) policy. You need to configure your FastAPI backend to allow requests from GitBook.

## Quick Setup

### 1. Check if CORS is Already Enabled

Look for this in your `main.py`:

```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # or specific domains
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

### 2. Add CORS if Missing

Add this code to your `main.py` right after creating the FastAPI app:

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

# CORS Configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roadcast.gitbook.io",  # Your GitBook domain
        "http://localhost:*",           # Local testing
        "http://127.0.0.1:*",          # Local testing
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)
```

### 3. Production CORS (Recommended)

For production, specify exact origins:

```python
ALLOWED_ORIGINS = [
    "https://roadcast.gitbook.io",
    "https://your-docs.gitbook.io",
    "https://your-custom-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)
```

## Testing CORS

### Test with curl:

```bash
curl -X OPTIONS http://localhost:8001/v1/search \
  -H "Origin: https://roadcast.gitbook.io" \
  -H "Access-Control-Request-Method: POST" \
  -v
```

Look for these headers in the response:
- `Access-Control-Allow-Origin: https://roadcast.gitbook.io`
- `Access-Control-Allow-Methods: POST`

### Test with the widget:

1. Open `demo.html` in your browser
2. Open browser DevTools Console (F12)
3. Try sending a message
4. Check for CORS errors in the Console

## Common Issues

### Issue: "CORS policy: No 'Access-Control-Allow-Origin' header"

**Solution:** Make sure CORS middleware is added to your FastAPI app.

### Issue: "CORS policy: The value of the 'Access-Control-Allow-Origin' header must not be the wildcard '*'"

**Solution:** When using `allow_credentials=True`, you cannot use `allow_origins=["*"]`. Specify exact domains instead.

### Issue: Widget works locally but not in GitBook

**Solution:** 
1. Make sure your API is publicly accessible (not just localhost)
2. Update `config.js` with your public API URL
3. Add your GitBook domain to `allow_origins`

## Security Best Practices

1. **Never use `allow_origins=["*"]` in production** - always specify exact domains
2. **Use HTTPS** for your API in production
3. **Limit methods** to only what you need (GET, POST)
4. **Set proper headers** - don't use wildcard for headers in production
5. **Consider rate limiting** to prevent abuse

## Environment-Based Configuration

```python
import os

if os.getenv("ENV") == "production":
    ALLOWED_ORIGINS = [
        "https://roadcast.gitbook.io",
        "https://your-domain.com",
    ]
else:
    ALLOWED_ORIGINS = ["*"]  # Allow all in development

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Additional Resources

- [FastAPI CORS Documentation](https://fastapi.tiangolo.com/tutorial/cors/)
- [MDN CORS Guide](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
