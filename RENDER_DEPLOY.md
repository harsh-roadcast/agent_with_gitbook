# Deploy to Render.com

This guide walks you through deploying the DSPy Agent API to Render.com.

## Prerequisites

- GitHub repository with your code pushed
- Render.com account (free tier available)
- Environment variables ready (see below)

## Step 1: Create render.yaml Configuration

Render uses `render.yaml` for deployment configuration. This is already in your repo, but here's what it should contain:

```yaml
services:
  - type: web
    name: dspy-agent-api
    runtime: docker
    plan: free
    branch: main
    dockerfilePath: ./Dockerfile
    envVars:
      - key: OLLAMA_MODEL
        value: llama3.2
      - key: LOG_LEVEL
        value: INFO
      # Add other non-sensitive variables here
```

## Step 2: Push Your Code to GitHub

```bash
# Make sure all changes are committed
git add .
git commit -m "Prepare for Render deployment"
git push origin main
```

## Step 3: Connect Render to GitHub

1. Go to [render.com](https://render.com) and sign up/login
2. Click **"New +"** → **"Web Service"**
3. Select **"Connect a repository"**
4. Find and connect your GitHub repository
5. Select the branch: **main**

## Step 4: Configure Web Service

### Basic Settings
- **Name**: `dspy-agent-api`
- **Runtime**: Select **"Docker"** (NOT Node/Python)
- **Region**: Choose closest to you (e.g., `us-west` for US)
- **Plan**: Free tier (to test) or Starter+ for production

### Docker Settings
- **Dockerfile path**: `Dockerfile` (leave default if in root)
- **Docker context**: Leave empty
- **Docker registry**: DockerHub (default)

## Step 5: Add Environment Variables

Click **"Environment"** section and add:

```
ES_HOST=your-elasticsearch-host
ES_USERNAME=your-es-username
ES_PASSWORD=your-es-password
ES_VERIFY_CERTS=false

REDIS_HOST=your-redis-host
REDIS_PORT=6379
REDIS_PASSWORD=your-redis-password

OPENAI_API_KEY=sk-your-key-here
JWT_SECRET_KEY=your-secret-key-here

LLM_MODEL=llama3.2
LOG_LEVEL=INFO
```

## Step 6: Deploy

1. Scroll to bottom and click **"Create Web Service"**
2. Render will:
   - Pull your GitHub code
   - Build Docker image
   - Deploy automatically

**Deployment takes 5-10 minutes** (watch the logs in real-time)

## Step 7: Get Your URL

After successful deployment, Render provides:
```
https://your-app-name.onrender.com
```

Your API endpoints will be at:
- Search: `https://your-app-name.onrender.com/v1/search`
- Chat: `https://your-app-name.onrender.com/v1/chat/completions`

## Step 8: Update GitBook Widget

Update your widget configuration:

```javascript
// gitbook-chatbot-widget/config.js
export const CHATBOT_CONFIG = {
    apiEndpoint: 'https://your-app-name.onrender.com/v1/search',
    // ... other config
};
```

Or update in GitBook Custom Code:

```html
<script>
    window.CHATBOT_API_ENDPOINT = 'https://your-app-name.onrender.com/v1/search';
</script>
```

## Step 9: Test the Deployment

```bash
# Test search endpoint
curl -X POST https://your-app-name.onrender.com/v1/search \
  -H "Content-Type: application/json" \
  -d '{
    "query":"authentication",
    "message_id":"test",
    "session_id":"test",
    "limit":2
  }'

# Expected response:
# {
#   "query": "authentication",
#   "results": [...],
#   "total": 2,
#   "limit": 2,
#   ...
# }
```

## Image Size Advantages

- **Render limit**: 4.7 GB (plenty of room for your app)
- **Current image**: ~800 MB after optimization
- **Status**: ✅ Fits comfortably

## Monitoring & Logs

1. Go to your service dashboard
2. Click **"Logs"** tab to see:
   - Build progress
   - Runtime errors
   - Application output

## Common Issues

### Build Fails: "Docker build failed"
- Check logs for specific error
- Ensure all dependencies are in `pyproject.toml`
- Verify `.dockerignore` is not excluding critical files

### Deploy Succeeds but API returns 502
- Check environment variables are set correctly
- Ensure Elasticsearch/Redis are accessible from Render
- Check application logs for runtime errors

### CORS Issues with GitBook
- Add CORS origin to your API:
```python
# main.py
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://roadcast.gitbook.io", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Auto-Deployment

Every time you push to `main` branch:
1. Render detects the change
2. Automatically rebuilds Docker image
3. Deploys new version
4. No manual action needed

## Database Connections

If using external services:
- **Elasticsearch**: Provide full connection string with auth
- **Redis**: Use connection string from provider
- **OpenAI**: Use API key directly

All should be in environment variables, never in code.

## Next Steps

1. ✅ Deploy to Render
2. ✅ Get production URL
3. ✅ Update GitBook widget config
4. ✅ Test in production
5. ✅ Monitor logs and errors

---

**Need help?** Check Render docs: https://render.com/docs
