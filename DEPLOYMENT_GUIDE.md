# 🚀 Deployment Guide — Resume Screener

> **Stack**: Next.js frontend on **Vercel** (free) + FastAPI backend on **Render** (free) + **Supabase** (free) + **Gemini API** (free)

---

## Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Get a Free Gemini API Key](#2-get-a-free-gemini-api-key)
3. [Set Up Supabase](#3-set-up-supabase)
4. [Deploy the Backend on Render](#4-deploy-the-backend-on-render)
5. [Deploy the Frontend on Vercel](#5-deploy-the-frontend-on-vercel)
6. [Connect Everything](#6-connect-everything)
7. [Environment Variable Reference](#7-environment-variable-reference)
8. [Troubleshooting](#8-troubleshooting)

---

## 1. Prerequisites

- A **GitHub** account (to connect Render and Vercel)
- Push this repository to a **GitHub repo** (public or private)

```bash
git init
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/YOUR_USERNAME/resume-screener.git
git push -u origin main
```

---

## 2. Get a Free Gemini API Key

1. Go to **[Google AI Studio](https://aistudio.google.com/apikey)**
2. Sign in with your Google account
3. Click **"Create API key"**
4. Copy the key — you'll need it for the backend

> 💡 The free tier gives you **15 RPM (requests per minute)** and **1M tokens/day** with `gemini-2.0-flash`. More than enough for resume screening.

---

## 3. Set Up Supabase

### 3.1 Create a Project

1. Go to **[supabase.com](https://supabase.com)** → Sign up (free)
2. Click **"New Project"**
3. Choose a name, set a strong database password, pick a region
4. Wait for the project to provision (~2 minutes)

### 3.2 Get Your Keys

Go to **Settings → API** and copy:

| Key | Where to use |
|-----|-------------|
| **Project URL** | `SUPABASE_URL` + `NEXT_PUBLIC_SUPABASE_URL` |
| **anon (public)** key | `SUPABASE_ANON_KEY` + `NEXT_PUBLIC_SUPABASE_ANON_KEY` |
| **service_role (secret)** key | `SUPABASE_SERVICE_KEY` (backend only!) |

### 3.3 Create Database Tables

Go to **SQL Editor** and run these queries:

```sql
-- Analysis sessions table
CREATE TABLE analysis_sessions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    jd_filename TEXT,
    jd_experience_level TEXT,
    jd_technical_skills TEXT[] DEFAULT '{}',
    jd_soft_skills TEXT[] DEFAULT '{}',
    jd_tools TEXT[] DEFAULT '{}',
    total_candidates INTEGER DEFAULT 0,
    avg_score NUMERIC,
    strong_count INTEGER DEFAULT 0,
    moderate_count INTEGER DEFAULT 0,
    weak_count INTEGER DEFAULT 0,
    ranking_analysis TEXT,
    executive_summary TEXT,
    ai_enabled BOOLEAN DEFAULT false
);

-- Candidates table
CREATE TABLE candidates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES auth.users(id),
    session_id UUID REFERENCES analysis_sessions(id),
    created_at TIMESTAMPTZ DEFAULT now(),
    file_name TEXT,
    candidate_name TEXT,
    college_name TEXT,
    score_pct NUMERIC,
    verdict TEXT,
    keyword_overlap NUMERIC,
    vector_similarity NUMERIC,
    skills_match_score NUMERIC,
    matched_keywords TEXT[] DEFAULT '{}',
    missing_keywords TEXT[] DEFAULT '{}',
    matching_technical TEXT[] DEFAULT '{}',
    missing_technical TEXT[] DEFAULT '{}',
    matching_soft TEXT[] DEFAULT '{}',
    missing_soft TEXT[] DEFAULT '{}',
    matching_tools TEXT[] DEFAULT '{}',
    missing_tools TEXT[] DEFAULT '{}',
    experience_fit TEXT,
    overall_assessment TEXT,
    resume_technical TEXT[] DEFAULT '{}',
    resume_soft TEXT[] DEFAULT '{}',
    resume_tools TEXT[] DEFAULT '{}',
    experience_level TEXT,
    ai_summary TEXT,
    jd_experience_level TEXT,
    jd_technical_skills TEXT[] DEFAULT '{}',
    resume_storage_path TEXT
);

-- Enable Row Level Security
ALTER TABLE analysis_sessions ENABLE ROW LEVEL SECURITY;
ALTER TABLE candidates ENABLE ROW LEVEL SECURITY;

-- RLS policies (users can only access their own data)
CREATE POLICY "Users see own sessions"
    ON analysis_sessions FOR ALL
    USING (auth.uid() = user_id);

CREATE POLICY "Users see own candidates"
    ON candidates FOR ALL
    USING (auth.uid() = user_id);
```

### 3.4 Create Storage Bucket

Go to **Storage** → **New Bucket**:
- Name: `resumes`
- Public: **No** (private)
- Click Create

### 3.5 Enable Email Auth

Go to **Authentication → Providers** → Make sure **Email** is enabled.

---

## 4. Deploy the Backend on Render

### 4.1 Create a Web Service

1. Go to **[render.com](https://render.com)** → Sign up (free)
2. Click **"New" → "Web Service"**
3. Connect your GitHub repo
4. Configure:

| Setting | Value |
|---------|-------|
| **Name** | `resume-screener-api` |
| **Region** | Pick the closest to you |
| **Branch** | `main` |
| **Root Directory** | `backend` |
| **Runtime** | `Python 3` |
| **Build Command** | `pip install -r requirements.txt && python -m spacy download en_core_web_md` |
| **Start Command** | `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Instance Type** | **Free** |

> ⚠️ **Python version**: The repo includes a `backend/.python-version` file that pins Python to **3.11**. This is required — `spacy`, `numpy`, and `chromadb` don't support Python 3.13+. Render reads this file automatically.

> ⚠️ **Build command**: Copy the build command exactly as shown. Do NOT include backticks or extra quotes around it.

### 4.2 Add Environment Variables

In the Render dashboard, go to **Environment** → Add these:

```
GEMINI_API_KEY=your_gemini_api_key
GEMINI_MODEL=gemini-2.0-flash
SUPABASE_URL=https://your-project-id.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_SERVICE_KEY=your_service_role_key
FRONTEND_URL=https://your-app.vercel.app
```

> ⚠️ You'll set `FRONTEND_URL` after deploying the frontend. Come back and update it.

### 4.3 Deploy

Click **"Create Web Service"**. The first build takes ~5-10 minutes (installing spaCy + model).

Your backend URL will be something like: `https://resume-screener-api.onrender.com`

> ⚠️ **Free tier note**: Render spins down free services after 15 minutes of inactivity. The first request after sleep takes ~30-60 seconds (cold start). This is normal.

---

## 5. Deploy the Frontend on Vercel

### 5.1 Import Project

1. Go to **[vercel.com](https://vercel.com)** → Sign up (free, use GitHub)
2. Click **"Add New" → "Project"**
3. Import your GitHub repo
4. Configure:

| Setting | Value |
|---------|-------|
| **Framework Preset** | Next.js |
| **Root Directory** | `frontend` |
| **Build Command** | `next build` (default) |
| **Output Directory** | `.next` (default) |

### 5.2 Add Environment Variables

In the Vercel project settings → **Environment Variables**:

```
NEXT_PUBLIC_API_URL=https://resume-screener-api.onrender.com
NEXT_PUBLIC_SUPABASE_URL=https://your-project-id.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
```

### 5.3 Deploy

Click **"Deploy"**. Should take ~1-2 minutes.

Your frontend URL will be something like: `https://your-app.vercel.app`

---

## 6. Connect Everything

After both are deployed:

### 6.1 Update Render Backend

Go back to Render → your service → **Environment**:
- Set `FRONTEND_URL` to your Vercel URL (e.g., `https://your-app.vercel.app`)

### 6.2 Update Supabase Auth

Go to Supabase → **Authentication → URL Configuration**:
- **Site URL**: `https://your-app.vercel.app`
- **Redirect URLs**: Add `https://your-app.vercel.app/**`

### 6.3 Verify

1. Visit your Vercel URL
2. The status chip should show **"✅ Gemini AI connected"**
3. Try signing up and running an analysis

---

## 7. Environment Variable Reference

### Backend (Render)

| Variable | Required | Description |
|----------|----------|-------------|
| `GEMINI_API_KEY` | ✅ | Google AI Studio API key |
| `GEMINI_MODEL` | ❌ | Model name (default: `gemini-2.0-flash`) |
| `SUPABASE_URL` | ✅ | Supabase project URL |
| `SUPABASE_ANON_KEY` | ✅ | Supabase anon/public key |
| `SUPABASE_SERVICE_KEY` | ✅ | Supabase service role key |
| `FRONTEND_URL` | ✅ | Vercel frontend URL (for CORS) |

### Frontend (Vercel)

| Variable | Required | Description |
|----------|----------|-------------|
| `NEXT_PUBLIC_API_URL` | ✅ | Render backend URL |
| `NEXT_PUBLIC_SUPABASE_URL` | ✅ | Supabase project URL |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | ✅ | Supabase anon/public key |

---

## 8. Troubleshooting

### "⏳ Checking backend…" never resolves
- Your Render service is likely sleeping (free tier). Wait 30-60 seconds and refresh.
- Check Render logs for startup errors.

### "❌ Gemini API key not configured"
- Make sure `GEMINI_API_KEY` is set in Render's environment variables.
- Verify the key works at [AI Studio](https://aistudio.google.com).

### Build fails with "unexpected EOF" or bash errors
- Make sure the **Build Command** is pasted exactly — no stray backticks or quotes.
- Correct: `pip install -r requirements.txt && python -m spacy download en_core_web_md`

### Build fails with numpy/spacy compilation errors
- Python version is too new. Make sure `backend/.python-version` contains `3.11.12`.
- Render reads this file automatically to select the Python version.

### CORS errors in browser console
- Make sure `FRONTEND_URL` in Render matches your exact Vercel URL.
- No trailing slash.

### Auth / sign-in not working
- Check Supabase → Authentication → URL Configuration.
- The Site URL and Redirect URLs must match your Vercel deployment.

### Slow first request
- Render free tier spins down after inactivity. The first request loads spaCy, NLTK data, and ChromaDB — this takes ~30-60s.
- Subsequent requests are fast.

### "Gemini API error: 429"
- You've hit the free tier rate limit (15 RPM).
- Wait a minute and retry, or upgrade your Google Cloud billing.

---

## 💡 Cost Summary

| Service | Plan | Cost |
|---------|------|------|
| **Gemini API** | Free tier | $0/month (15 RPM, 1M tokens/day) |
| **Supabase** | Free tier | $0/month (500MB DB, 1GB storage) |
| **Render** | Free tier | $0/month (750h/month, spins down) |
| **Vercel** | Hobby | $0/month (100GB bandwidth) |
| **Total** | | **$0/month** ✅ |
