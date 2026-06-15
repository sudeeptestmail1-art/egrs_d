# 🎯 ResumeAI — AI Resume Screener

> FastAPI · Next.js 16 · Supabase · Gemini 2.0 Flash · spaCy · ChromaDB

Screen multiple resumes against a job description in seconds. Candidates are ranked by a composite NLP + AI score, with full history, PDF preview, and an AI chatbot — all saved per user.

<div align="center">

[![Read Documentation](https://img.shields.io/badge/Read-Documentation-0077b5?style=for-the-badge&logo=gitbook&logoColor=white)](https://drive.google.com/file/d/1osdvlCkNPrFsDm0b2XJOvbO_XCOPyxi0/view?usp=sharing)
&nbsp;&nbsp;
[![Watch Demo](https://img.shields.io/badge/Watch-Demo-red?style=for-the-badge&logo=youtube&logoColor=white)](https://drive.google.com/file/d/1H61-PfdSDcKCQ9wOlYaJO486_0Okk98o/view?usp=sharing)

</div>

---

## Features

- **Resume screening** — upload a JD + multiple resumes (PDF/DOCX), get a ranked leaderboard instantly
- **Composite scoring** — keyword overlap (spaCy) + semantic similarity + AI skills match (Gemini)
- **Skills gap analysis** — matching vs. missing technical skills, soft skills, and tools per candidate
- **Name & college extraction** — auto-extracted from each resume via spaCy NER + heuristics
- **Analysis history** — every run saved as a session with lazy-loaded candidate cards
- **Candidate database** — searchable, filterable table across all sessions with expandable detail rows
- **PDF resume viewer** — view stored resumes in-browser via a secure backend proxy
- **AI chatbot** — context-aware assistant with live access to your candidate database (streaming)
- **Auth** — email/password + Google OAuth via Supabase; all data scoped per user
- **Export** — download results as `.xlsx` (server) or `.csv` (client-side, instant)

---

## Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + uvicorn (Python 3.11) |
| NLP | spaCy `en_core_web_md` + NLTK |
| AI | Google Gemini 2.0 Flash |
| Vector store | ChromaDB |
| File parsing | PyPDF2, docx2txt |
| Database / Auth / Storage | Supabase (PostgreSQL + JWT + S3-compatible) |
| Frontend | Next.js 16 App Router + React 19 + TypeScript 5 |
| Styling | Pure CSS custom properties (no Tailwind) |

---

## Scoring

```
Without AI:  score = 0.6 × keyword_overlap + 0.4 × vector_similarity
With AI:     score = 0.4 × keyword_overlap + 0.3 × vector_similarity + 0.3 × ai_skills_match
```

| Score | Verdict |
|---|---|
| ≥ 70% | Strong Match |
| 45–69% | Moderate Match |
| < 45% | Weak Match |

---

## Project Structure

```
resume-screener/
├── backend/
│   ├── main.py               # FastAPI app — all endpoints
│   ├── llm_service.py        # Gemini API calls + structured parsers
│   ├── resume_analyzer.py    # NLP scoring, name/college extraction, ChromaDB
│   ├── chat_service.py       # Streaming Gemini chat + context builder
│   ├── supabase_client.py    # Supabase REST client (plain requests, no SDK)
│   └── requirements.txt
└── frontend/
    ├── app/
    │   ├── layout.tsx         # AuthProvider + Navbar + Chatbot (global)
    │   ├── page.tsx           # / — Screener
    │   ├── history/page.tsx   # /history — Analysis history
    │   └── candidates/page.tsx# /candidates — Candidate database
    ├── components/
    │   ├── Navbar.tsx         # Sticky nav with avatar + profile dropdown
    │   ├── AuthModal.tsx      # Sign in / sign up / forgot password
    │   ├── Chatbot.tsx        # Floating AI chat panel (SSE streaming)
    │   ├── ResumeCard.tsx     # Collapsible per-resume result card
    │   └── Uploader.tsx       # Drag-and-drop file uploader
    └── lib/
        ├── api.ts             # Typed FastAPI HTTP client
        └── auth.tsx           # Supabase auth context + useAuth hook
```

---

## Local Setup

### 1 — Backend

```bash
cd backend
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m spacy download en_core_web_md
uvicorn main:app --reload --port 8000
```

Create `backend/.env`:

```env
GEMINI_API_KEY=your_key_here
GEMINI_MODEL=gemini-2.0-flash
SUPABASE_URL=https://YOUR_PROJECT.supabase.co
SUPABASE_SERVICE_KEY=your_service_role_key
SUPABASE_ANON_KEY=your_anon_key
# FRONTEND_URL=https://your-domain.com   # production only
```

Get a free Gemini key at [aistudio.google.com](https://aistudio.google.com/apikey).

### 2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local`:

```env
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 3 — Supabase

1. Create a project at [supabase.com](https://supabase.com)
2. **SQL Editor** → run `supabase_schema_v2.sql`
3. **Storage** → create a private bucket named `resumes`
4. **Authentication → Settings** → disable email confirmations (dev only)

Keys are at **Settings → API** in your Supabase dashboard.

---

## Deployment

| Service | Role | Config |
|---|---|---|
| **Render** (free) | Backend | Root dir: `backend` · Build: `pip install -r requirements.txt && python -m spacy download en_core_web_md` · Start: `uvicorn main:app --host 0.0.0.0 --port $PORT` |
| **Vercel** (hobby) | Frontend | Root dir: `frontend` · Add all `NEXT_PUBLIC_*` env vars |

> **Python version:** Render reads `backend/.python-version` (pinned to `3.11.12`). Do not change this — spaCy and ChromaDB don't support 3.13+.

After both are deployed, set `FRONTEND_URL` in Render to your Vercel URL and update **Supabase → Authentication → URL Configuration** with your Vercel domain.

---

## API Endpoints

| Method | Path | Auth |
|---|---|---|
| GET | `/health` | No |
| POST | `/analyze` | Optional |
| POST | `/jd/skills` | No |
| GET | `/sessions` | Required |
| GET | `/sessions/{id}/candidates` | Required |
| DELETE | `/sessions/{id}` | Required |
| GET | `/candidates` | Required |
| DELETE | `/candidates/{id}` | Required |
| GET | `/candidates/{id}/resume` | Required |
| POST | `/export` | Optional |
| POST | `/chat` | Optional |
| GET | `/search?q=` | No |

Interactive docs: `http://localhost:8000/docs`

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Backend never loads on Render | Free tier cold start — wait 30–60 s |
| `saved_to_db: false` | Not signed in, or JWT failed — check uvicorn logs |
| Build fails (NumPy/spaCy errors) | Wrong Python version — confirm `backend/.python-version` = `3.11.12` |
| CORS errors | `FRONTEND_URL` in Render must match Vercel URL exactly (no trailing slash) |
| PDF viewer blank | Resume was analysed while logged out — re-run signed in |
| Chatbot 429 error | Gemini free tier rate limit (15 RPM) — wait 60 s |
| History page empty | Analysis run while logged out — sign in first, then re-analyse |

---

> `.env` and `.env.local` are in `.gitignore` — never commit them. The `SUPABASE_SERVICE_KEY` is server-side only.
