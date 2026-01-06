# Poetry Deployment on Railway

## ✅ What Changed for Poetry

Railway **natively supports Poetry**! Here's what's optimized:

### Files Updated:
1. **railway.toml** - Uses `poetry run` command
2. **Procfile** - Updated to use Poetry
3. **requirements.txt** - Kept as fallback

---

## How Railway Handles Poetry

Railway will automatically:
1. ✅ Detect `pyproject.toml` and `poetry.lock`
2. ✅ Install Poetry
3. ✅ Run `poetry install`
4. ✅ Use your lock file for reproducible builds
5. ✅ Start app with `poetry run`

---

## Before Deploying

### 1. **Generate poetry.lock** (if not exists)
```bash
poetry lock
```

### 2. **Ensure poetry.lock is committed**
```bash
git add poetry.lock pyproject.toml
git commit -m "Add Poetry lock file"
```

### 3. **Test locally with Poetry**
```bash
# Install dependencies
poetry install

# Run the app
poetry run uvicorn main:app --host 0.0.0.0 --port 8001
```

---

## Environment Variables in Railway

Add these in Railway Dashboard → Variables:

```bash
# Copy from your .env file

# Elasticsearch
ES_HOST=http://127.0.0.1:9200
ES_USERNAME=
ES_PASSWORD=
ES_VERIFY_CERTS=false
ES_REQUEST_TIMEOUT=30

# Redis (Railway Redis plugin will auto-provide these)
REDIS_HOST=redis.railway.internal
REDIS_PORT=6379
REDIS_DB=0
REDIS_PASSWORD=

# OpenAI
OPENAI_API_KEY=your-openai-key

# JWT
JWT_SECRET_KEY=your-super-secret-jwt-key-here-change-this-in-production
JWT_ALGORITHM=HS256
TOKEN_EXPIRE_MINUTES=30

# Models
EMBEDDING_MODEL=all-MiniLM-L6-v2
DEFAULT_CHART_TYPE=column
DEFAULT_QUERY_SIZE=10

# Logging
LOG_LEVEL=INFO
```

---

## Deploy to Railway

### Option A: Railway Dashboard

1. Go to [railway.app](https://railway.app)
2. New Project → Deploy from GitHub
3. Select your repository
4. Railway auto-detects Poetry from `pyproject.toml`
5. Add environment variables
6. Deploy! 🚀

### Option B: Railway CLI

```bash
# Install CLI
npm i -g @railway/cli

# Login
railway login

# Link project
railway link

# Add environment variables from .env
railway variables set --from-env-file .env

# Deploy
railway up
```

---

## Poetry-Specific Benefits

### ✅ Advantages:
- **Exact versions** from poetry.lock
- **Faster installs** with cached dependencies
- **Development dependencies** excluded in production
- **Better dependency resolution**

### Production Optimization:

Update `pyproject.toml` if needed:

```toml
[tool.poetry]
# ... your config

[tool.poetry.dependencies]
python = "^3.12, <3.14"
# ... your dependencies

[tool.poetry.group.dev.dependencies]
pytest = "^8.4.1"
# Move dev-only deps here

[build-system]
requires = ["poetry-core"]
build-backend = "poetry.core.masonry.api"
```

Then install without dev dependencies:
```bash
poetry install --without dev
```

Railway will use: `poetry install --no-dev` automatically in production.

---

## Troubleshooting

### Poetry not detected
- Ensure `pyproject.toml` and `poetry.lock` are committed
- Check Railway logs for Poetry installation

### Dependency conflicts
```bash
# Update lock file
poetry lock --no-update

# Or regenerate
rm poetry.lock
poetry lock
```

### Build takes too long
- Poetry caches dependencies
- First build may take 5-10 minutes
- Subsequent builds are faster

### Missing system dependencies

If packages like `pyodbc` fail, add to `railway.toml`:

```toml
[nixpacks]
pythonVersion = "3.12"

[phases.setup]
nixPkgs = ["unixODBC", "gcc"]
```

---

## Quick Deploy Checklist

- [ ] `poetry.lock` exists and committed
- [ ] `pyproject.toml` has all dependencies
- [ ] Test locally: `poetry run uvicorn main:app`
- [ ] Push to GitHub
- [ ] Deploy on Railway
- [ ] Add environment variables
- [ ] Add Redis plugin (if needed)
- [ ] Test deployed URL
- [ ] Update GitBook widget with new URL

---

## Commands Reference

```bash
# Local development
poetry install                    # Install dependencies
poetry add package-name          # Add new package
poetry remove package-name       # Remove package
poetry run uvicorn main:app      # Run app
poetry run pytest                # Run tests
poetry lock                      # Update lock file

# Railway deployment
railway login                    # Login to Railway
railway link                     # Link to project
railway variables set KEY=VALUE  # Set env var
railway up                       # Deploy
railway logs                     # View logs
railway open                     # Open app in browser
```

---

## Your Deployment Command

Railway will run:
```bash
poetry install --no-dev
poetry run uvicorn main:app --host 0.0.0.0 --port $PORT
```

This is already configured in `railway.toml` and `Procfile`!

---

**Ready to deploy!** Just push to GitHub and Railway handles the rest. 🚀
