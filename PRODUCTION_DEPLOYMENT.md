# SocratiQ Production Deployment Guide

This guide provides the necessary steps and configurations to deploy the SocratiQ AI Learning Platform to a production environment using **Railway**, **Vercel**, and **Supabase**.

---

## 🏗️ Phase 1: Supabase Database Setup

1. **Create Project**: Sign up at [Supabase](https://supabase.com/) and create a new project.
2. **Get Connection String**: Go to **Project Settings > Database** and copy the **URI** connection string.
   - Format: `postgresql://postgres:[YOUR-PASSWORD]@[YOUR-HOST]:6543/postgres`
   - *Note: Ensure you replace `[YOUR-PASSWORD]` with your actual database password.*
3. **Schema Initialization**: The system is designed to initialize the schema automatically on the first run. No manual SQL execution is required.

---

## 🚀 Phase 2: Backend Deployment (Railway)

1. **Source Control**: Push your codebase to a GitHub repository.
2. **Create New Project**:
   - Log in to [Railway](https://railway.app/).
   - Click **New Project > Deploy from GitHub repo**.
   - Select your `AITUTOR` repository.
3. **Configuration (Root Dockerfile)**:
   - I have added a `Dockerfile` and `railway.json` to the **root** of the repository.
   - Railway will now automatically detect the Docker project and build it.
   - **CRITICAL**: Ensure **Root Directory** in Railway is set to `/` (the project root), NOT `backend`.
4. **Environment Variables**:
   Go to the **Variables** tab and add:
   - `DATABASE_URL`: Your Supabase connection string.
   - `GEMINI_API_KEY`: Your Google Gemini API key.
   - `TAVILY_API_KEY`: Your Tavily Search API key.
   - `SECRET_KEY`: A long, random string for JWT signing.
   - `CORS_ORIGINS`: `https://your-socratiq-app.vercel.app` (Your Vercel URL).
   - `ENV`: `production`
   - `PORT`: `8000`
5. **Deploy**: Railway will automatically build and deploy using the Dockerfile.
6. **Backend URL**: Note down your service URL (e.g., `https://aitutor-backend.up.railway.app`).

---

## 🎨 Phase 3: Frontend Deployment (Vercel)

1. **Import Project**: Log in to [Vercel](https://vercel.com/) and click **Add New > Project**.
2. **Configuration**:
   - **Root Directory**: `frontend`
   - **Framework Preset**: `Vite`
3. **Environment Variables**:
   Add the following variable:
   - `VITE_API_BASE_URL`: `https://aitutor-backend.up.railway.app` (Your Railway URL).
4. **Deploy**: Vercel will build and deploy your React application.
5. **Frontend URL**: Note down your production URL.

---

## 🔗 Phase 4: Connection & Validation

1. **Verify CORS**: Ensure the `CORS_ORIGINS` in Railway matches your Vercel URL exactly.
2. **System Health**: Visit `https://your-backend.up.railway.app/health` to verify the backend is connected to the database and initialized.
3. **Live Test**:
   - Open your Vercel URL.
   - Register a new account.
   - Upload a sample document.
   - Start a Socratic chat session.
   - Generate and complete a quiz.
   - Verify that your progress and analytics appear on the dashboard.

---

## 🔐 Security Summary

- **Secrets**: All keys and credentials are managed via environment variables and never exposed in the frontend.
- **Auth**: JWT-based authentication is enforced for all protected routes.
- **Isolation**: The frontend communicates only with the backend API; direct database access is blocked.
