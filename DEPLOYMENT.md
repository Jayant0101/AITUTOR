# SocratiQ Deployment Guide

## Docker (Self-Hosted / VPS)
Run everything in one command:
```bash
docker-compose up --build -d
```
Access the frontend at `http://localhost`.

## Cloud Platforms

### Backend (Render / Railway / EC2)
1. **Source**: Connect your GitHub repository.
2. **Build Command**: `pip install -r backend/requirements.txt && python -m spacy download en_core_web_sm`
3. **Start Command**: `gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:$PORT` (set `cwd` to `backend`)
4. **Environment Variables**:
   - `OPENAI_API_KEY` or `GEMINI_API_KEY`
   - `TAVILY_API_KEY`
   - `SECRET_KEY` (generate a random string)
   - `CORS_ORIGINS` (e.g. `https://your-frontend.vercel.app`)

### Frontend (Vercel / Netlify)
1. **Source**: Connect your GitHub repository.
2. **Build Command**: `npm run build` (set `root directory` to `frontend`)
3. **Output Directory**: `dist`
4. **Environment Variables**:
   - `VITE_API_BASE_URL` (point to your backend URL if not using relative proxy)
   - *Note*: If using the provided `nginx.conf` in Docker, the proxy is handled automatically. On Vercel, you might need a `vercel.json` for proxying.

## Security Notes
- Ensure `SECRET_KEY` is not the default in production.
- Use HTTPS for all endpoints.
- Rate limiting is active by default (60 requests/min per IP).
