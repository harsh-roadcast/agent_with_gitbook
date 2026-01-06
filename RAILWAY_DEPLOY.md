# Railway Deployment Guide

## 🚂 Deploy Your DSPy Agent to Railway

This guide will help you deploy your FastAPI application to Railway with HTTPS support.

---

## Prerequisites

- ✅ Railway account (sign up at [railway.app](https://railway.app))
- ✅ GitHub account (to connect your repo)
- ✅ Git installed locally
- ✅ Your code in a Git repository

---

## Step 1: Prepare Your Project

### Files Already Created ✅

The following files have been created for Railway deployment:

1. **requirements.txt** - Python dependencies
2. **Procfile** - Tells Railway how to start your app
3. **railway.json** - Railway configuration
4. **.railwayignore** - Files to exclude from deployment

### Verify Environment Variables

Check your `.env` file or create one with these variables:

```bash
# Elasticsearch Configuration
ES_HOST=your-elasticsearch-host
ES_USERNAME=your-es-username
ES_PASSWORD=your-es-password
ES_VERIFY_CERTS=False

# Redis Configuration
REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

# LLM Configuration
OLLAMA_BASE_URL=http://localhost:11434
LLM_MODEL=llama3.2

# JWT Configuration
JWT_SECRET_KEY=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30

# Application
ENV=production
```

---

## Step 2: Push to GitHub

If not already done:

```bash
# Initialize git (if not already done)
git init

# Add all files
git add .

# Commit
git commit -m "Prepare for Railway deployment"

# Add remote (replace with your repo URL)
git remote add origin https://github.com/yourusername/your-repo.git

# Push
git push -u origin main
```

---

## Step 3: Deploy to Railway

### Option A: Deploy via Railway Dashboard (Recommended)

1. **Go to Railway**
   - Visit [railway.app](https://railway.app)
   - Sign in with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Choose your repository

3. **Configure Service**
   - Railway will auto-detect FastAPI
   - Click on your service

4. **Add Environment Variables**
   - Go to "Variables" tab
   - Add these variables:

   ```
   ES_HOST=your-elasticsearch-host
   ES_USERNAME=your-es-username
   ES_PASSWORD=your-es-password
   ES_VERIFY_CERTS=False
   REDIS_HOST=your-redis-host (see Step 4)
   REDIS_PORT=6379
   JWT_SECRET_KEY=your-secret-key
   LLM_MODEL=llama3.2
   ENV=production
   PORT=8001
   ```

5. **Deploy**
   - Railway will automatically deploy
   - Wait for build to complete (5-10 minutes)

6. **Get Your URL**
   - Go to "Settings" tab
   - Under "Domains", click "Generate Domain"
   - You'll get a URL like: `https://your-app.up.railway.app`

### Option B: Deploy via Railway CLI

```bash
# Install Railway CLI
npm i -g @railway/cli

# Login
railway login

# Initialize project
railway init

# Link to project
railway link

# Deploy
railway up
```

---

## Step 4: Add Redis Database

Railway provides Redis as an add-on:

1. **Add Redis Plugin**
   - In your project, click "New"
   - Select "Database" → "Add Redis"

2. **Connect Redis**
   - Railway will automatically create these variables:
     - `REDIS_HOST`
     - `REDIS_PORT` 
     - `REDIS_PASSWORD`
   - These are automatically injected into your app

3. **Update Your Code** (if needed)
   - Railway Redis requires password authentication
   - Check `util/redis_client.py` uses these env vars

---

## Step 5: Add Elasticsearch

You have two options:

### Option A: Use Existing Elasticsearch (Recommended)

If you have Elasticsearch hosted elsewhere (Elastic Cloud, AWS, etc.):

1. Add connection details as environment variables
2. Make sure your ES instance allows Railway IPs

### Option B: Deploy Elasticsearch on Railway

1. Create new service: "Docker → Elasticsearch"
2. Connect it to your FastAPI service
3. Railway will provide connection variables

**Note:** Elasticsearch can be resource-heavy. Consider using Elastic Cloud for production.

---

## Step 6: Update CORS for Production

Update `main.py` to allow your Railway domain:

```python
# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://roadcast.gitbook.io",  # GitBook
        "https://your-app.up.railway.app",  # Your Railway URL
        "http://localhost:8080",  # Local testing
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

Commit and push:
```bash
git add main.py
git commit -m "Update CORS for production"
git push
```

Railway will auto-redeploy.

---

## Step 7: Update GitBook Widget

Once deployed, update your chatbot widget configuration:

1. **Update config.js**:
   ```javascript
   const CHATBOT_CONFIG = {
     apiEndpoint: 'https://your-app.up.railway.app/v1/search',
     // ... rest of config
   };
   ```

2. **Update in GitBook**:
   - Go to GitBook Settings → Custom Code
   - Update the API endpoint
   - Save and publish

---

## Step 8: Test Your Deployment

### Test API Health
```bash
curl https://your-app.up.railway.app/health
```

### Test Search Endpoint
```bash
curl -X POST https://your-app.up.railway.app/v1/search \
  -H "Content-Type: application/json" \
  -H "Origin: https://roadcast.gitbook.io" \
  -d '{
    "query": "authentication",
    "message_id": "test_msg",
    "session_id": "test_session",
    "limit": 5
  }'
```

### Test CORS
```bash
curl -I -X OPTIONS https://your-app.up.railway.app/v1/search \
  -H "Origin: https://roadcast.gitbook.io" \
  -H "Access-Control-Request-Method: POST"
```

Look for: `Access-Control-Allow-Origin: https://roadcast.gitbook.io`

---

## Monitoring & Logs

### View Logs
- Railway Dashboard → Your Service → "Deployments" tab
- Click on latest deployment
- View real-time logs

### Metrics
- Railway Dashboard → "Metrics" tab
- See CPU, Memory, Network usage

---

## Environment Variables Reference

Railway needs these environment variables:

| Variable | Description | Example |
|----------|-------------|---------|
| `ES_HOST` | Elasticsearch host | `https://es.example.com:9200` |
| `ES_USERNAME` | Elasticsearch username | `elastic` |
| `ES_PASSWORD` | Elasticsearch password | `your-password` |
| `ES_VERIFY_CERTS` | Verify SSL certs | `False` |
| `REDIS_HOST` | Redis host | `redis.railway.internal` |
| `REDIS_PORT` | Redis port | `6379` |
| `REDIS_PASSWORD` | Redis password | Auto-generated by Railway |
| `JWT_SECRET_KEY` | JWT secret | Generate secure key |
| `LLM_MODEL` | LLM model name | `llama3.2` |
| `OLLAMA_BASE_URL` | Ollama API URL | Skip if using OpenAI |
| `ENV` | Environment | `production` |
| `PORT` | Port (set by Railway) | `8001` |

---

## Troubleshooting

### Build Fails

**Error:** `No module named 'dspy'`
- Check `requirements.txt` has all dependencies
- Ensure Python version is 3.12

**Error:** `Failed to install pyodbc`
- pyodbc requires system dependencies
- Add to railway.toml or remove if not needed

### Application Crashes

**Error:** `Connection refused to Elasticsearch`
- Check ES_HOST is accessible from Railway
- Verify ES credentials
- Check ES allows Railway IPs

**Error:** `Redis connection failed`
- Ensure Redis plugin is added
- Check REDIS_HOST variable is set

### CORS Issues

**Error:** `CORS policy blocked`
- Update CORS origins in main.py
- Include your Railway URL
- Redeploy after changes

### High Memory Usage

Railway free tier has 512MB RAM limit:
- Reduce loaded models
- Use external LLM (OpenAI) instead of Ollama
- Upgrade Railway plan

---

## Cost Optimization

### Free Tier Limits
- **Railway Free Plan**: $5 credit/month
- **Usage-based pricing** after free tier
- Monitor usage in Railway dashboard

### Tips to Reduce Costs
1. **Use external services** (Elastic Cloud, Redis Cloud)
2. **Optimize embeddings** - Load model only when needed
3. **Use CDN** for static files
4. **Set up auto-scaling** limits
5. **Monitor logs** to catch errors early

---

## Production Checklist

- [ ] All environment variables set in Railway
- [ ] Redis database added and connected
- [ ] Elasticsearch accessible from Railway
- [ ] CORS configured for GitBook domain
- [ ] Railway domain generated
- [ ] Application deployed successfully
- [ ] Health endpoint responding
- [ ] Search endpoint tested
- [ ] CORS headers verified
- [ ] GitBook widget updated with Railway URL
- [ ] Error monitoring set up (optional)
- [ ] Logs monitored for issues

---

## Next Steps

1. **Set up custom domain** (optional)
   - Railway Settings → Domains → Add Custom Domain
   - Configure DNS records

2. **Add monitoring**
   - Railway has built-in metrics
   - Consider: Sentry, LogRocket, or Datadog

3. **Set up CI/CD**
   - Railway auto-deploys on git push
   - Add GitHub Actions for tests

4. **Enable SSL** (automatic)
   - Railway provides SSL certificates automatically
   - Your app will be HTTPS by default

5. **Scale if needed**
   - Railway Settings → Scale
   - Adjust instances, memory, CPU

---

## Useful Commands

```bash
# View logs
railway logs

# Open app in browser
railway open

# Run commands in Railway environment
railway run python manage.py migrate

# View environment variables
railway variables

# Redeploy
git push  # Auto-deploys

# Rollback
railway rollback
```

---

## Alternative Deployment Options

If Railway doesn't work for your needs:

1. **Render.com** - Similar to Railway, free tier
2. **Fly.io** - Good for global deployment
3. **Heroku** - Classic PaaS (limited free tier)
4. **Google Cloud Run** - Pay per request
5. **AWS Elastic Beanstalk** - More control
6. **DigitalOcean App Platform** - Simple deployment

---

## Support

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **Railway Status**: https://status.railway.app

---

**Your Railway URL will be:** `https://your-app.up.railway.app`

**Update this in:**
- `gitbook-chatbot-widget/config.js`
- GitBook Custom Code
- CORS configuration in `main.py`

Good luck with your deployment! 🚀
