# 🎯 ResumeAI — Full-Stack AI Resume Screener

> FastAPI · Next.js 16 · Supabase · Ollama (Gemma 3) · spaCy · ChromaDB

Screen multiple resumes against a job description in seconds. Candidates are ranked by a composite NLP + AI score, with name and college automatically extracted from each resume. Every analysis run is saved to Supabase and retrievable from the History page.





<div align="center">

[![Read Documentation](https://img.shields.io/badge/Read-Documentation-0077b5?style=for-the-badge&logo=gitbook&logoColor=white)](https://drive.google.com/file/d/1osdvlCkNPrFsDm0b2XJOvbO_XCOPyxi0/view?usp=sharing)
&nbsp;&nbsp;
[![Watch Demo](https://img.shields.io/badge/Watch-Demo-red?style=for-the-badge&logo=youtube&logoColor=white)](https://drive.google.com/file/d/1H61-PfdSDcKCQ9wOlYaJO486_0Okk98o/view?usp=sharing)

</div>

## Table of Contents

- [Features](#features)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Frontend Pages](#frontend-pages)
- [How Scoring Works](#how-scoring-works)
- [Name & College Extraction](#name--college-extraction)
- [How Sessions Work](#how-sessions-work)
- [Backend Setup](#backend-setup)
- [Frontend Setup](#frontend-setup)
- [Supabase Setup](#supabase-setup)
- [Environment Variables](#environment-variables)
- [Architecture](#architecture)
- [Production](#production)

---

## Features

- **Resume screening** — upload a JD + multiple resumes (PDF or DOCX), get a ranked leaderboard instantly
- **Composite scoring** — keyword overlap (spaCy) + semantic similarity (word vectors) + AI skills match (Ollama)
- **AI analysis** — skills extraction, gap analysis, per-candidate summaries, ranking narrative, executive summary
- **Name extraction** — automatically extracted from each resume using spaCy NER + heuristics
- **College extraction** — pulled from the education section using spaCy NER + keyword matching
- **Analysis history** — every run saved as a session; expandable cards with all candidates, JD skills, AI summaries
- **Candidates database** — searchable, filterable flat table of every candidate across all sessions
- **Authentication** — Supabase Auth with email/password; all data is scoped per user
- **Excel export** — download the full ranked results as a formatted `.xlsx` file
- **Vector search** — semantic search over all stored resumes via ChromaDB

---

## Project Structure

```
resume-screener/
├── backend/
│   ├── main.py                  ← FastAPI app — all endpoints
│   ├── llm_service.py           ← Ollama calls + structured response parsers
│   ├── resume_analyzer.py       ← NLP scoring, name/college extraction, ChromaDB
│   ├── supabase_client.py       ← Supabase REST API client (no SDK, plain requests)
│   ├── requirements.txt
│   └── .env                     ← Backend secrets (never commit)
│
└── frontend/
    ├── app/
    │   ├── layout.tsx            ← AuthProvider + Navbar mounted globally
    │   ├── page.tsx              ← Main screener UI
    │   ├── globals.css           ← Full design system (CSS variables)
    │   ├── history/
    │   │   └── page.tsx          ← Analysis history — one card per run
    │   └── candidates/
    │       └── page.tsx          ← All candidates — flat searchable table
    ├── components/
    │   ├── Navbar.tsx            ← Sticky nav with auth state
    │   ├── AuthModal.tsx         ← Sign in / sign up modal
    │   ├── ResumeCard.tsx        ← Per-resume result card (collapsible)
    │   ├── Uploader.tsx          ← Drag-and-drop file uploader
    │   └── ui.tsx                ← Shared primitives (badges, bars, pills)
    ├── lib/
    │   ├── api.ts                ← Typed FastAPI client
    │   └── auth.tsx              ← Supabase auth context + useAuth hook
    ├── package.json
    └── .env.local                ← Frontend public keys (never commit)
```

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend framework | FastAPI + uvicorn |
| NLP scoring | spaCy `en_core_web_md` |
| AI analysis | Ollama — Gemma 3 |
| Name / college extraction | spaCy NER + regex heuristics |
| Vector store | ChromaDB (local persistent) |
| PDF extraction | PyPDF2 |
| DOCX extraction | docx2txt |
| Excel export | pandas + xlsxwriter |
| Database | Supabase (PostgreSQL) |
| Auth | Supabase Auth (JWT) |
| Supabase client | Plain `requests` HTTP — no SDK |
| Frontend framework | Next.js 16 (App Router) |
| Frontend auth | `@supabase/supabase-js` |
| Styling | Pure CSS custom properties |
| Language | Python 3.14 · TypeScript 5 |

---

## Frontend Pages

| Route | Page | Description |
|---|---|---|
| `/` | Screener | Upload JD + resumes, run analysis, view ranked results |
| `/history` | Analysis History | Every run as an expandable card — candidates, JD skills, AI summaries loaded on demand |
| `/candidates` | All Candidates | Flat searchable table across all sessions — filter by verdict, sort by score or date |

The **History** and **Candidates** links in the navbar only appear when signed in.

---

## How Scoring Works

Each resume receives a **composite score** (0–100%) built from three components:

```
Without AI:   score = 0.6 × keyword_overlap + 0.4 × vector_similarity
With AI:      score = 0.4 × keyword_overlap + 0.3 × vector_similarity + 0.3 × ai_skills_match
```

| Component | How it is calculated |
|---|---|
| Keyword overlap | Set intersection of JD and resume lemmas (spaCy POS-filtered nouns, verbs, adjectives) |
| Vector similarity | Cosine similarity between TF-weighted JD vector and mean resume vector |
| AI skills match | Ollama Gemma 3 compares extracted JD skills vs resume content, returns 0–100 |

**Verdict thresholds**

| Score | Verdict |
|---|---|
| ≥ 70% | Strong Match |
| 45 – 69% | Moderate Match |
| < 45% | Weak Match |

---

## Name & College Extraction

Handled in `resume_analyzer.py` using a layered fallback strategy.

### `extract_candidate_name`

1. Scan the first 6 non-empty lines for a 2–5 word title-case or ALL-CAPS string with no digits or contact keywords (email, phone, LinkedIn, GitHub, etc.)
2. Fall back to spaCy `PERSON` NER on the first 500 characters of the resume

### `extract_college_name`

1. Find the `Education` section header, scan the next 20 lines for lines containing education keywords (`university`, `college`, `institute`, `IIT`, `NIT`, `BITS`, `IIIT`, `academy`, etc.)
2. Fall back to spaCy `ORG` NER on the education section, filtered by the same keyword list
3. Fall back to regex: `from XYZ University` or `at XYZ College` patterns

> Extraction accuracy depends on resume formatting. Unstructured or image-based PDFs may return `null`, which is handled gracefully in the UI and database.

---

## How Sessions Work

Every analysis run creates one `analysis_sessions` row and N `candidates` rows all sharing the same `session_id`.

```
POST /analyze
  │
  ├── save_session(session_id, user_id, { jd info, stats, AI summaries })
  │     → 1 row in analysis_sessions
  │
  └── save_candidate(result, user_id, session_id)  ×  N resumes
        → N rows in candidates, all with the same session_id
```

- **History page** loads `analysis_sessions` only — candidates are fetched on demand when you expand a session
- **Candidates page** loads all candidates flat — useful for cross-session search and comparison
- **Deleting a session** removes the session row and all its linked candidates

For full schema details see [`database_schema.md`](./database_schema.md).

---

## Backend Setup

```bash
cd backend

# Create and activate a virtualenv
python -m venv .venv

# Windows
.venv\Scripts\activate
# macOS / Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Download spaCy model
python -m spacy download en_core_web_md

# Start Ollama and pull a model
ollama serve &
ollama pull gemma3

# Start the API server
uvicorn main:app --reload --port 8000
```

Interactive API docs at `http://localhost:8000/docs`

### API Endpoints

| Method | Path | Description | Auth |
|---|---|---|---|
| GET | `/health` | Ollama + Supabase status | No |
| POST | `/analyze` | Full pipeline — ranks resumes, saves to DB | Optional |
| POST | `/jd/skills` | Extract required skills from JD only | No |
| GET | `/sessions` | List all analysis sessions for user | Required |
| GET | `/sessions/{id}/candidates` | Get all candidates in a session | Required |
| DELETE | `/sessions/{id}` | Delete session + all its candidates | Required |
| GET | `/candidates` | List all candidates across all sessions | Required |
| DELETE | `/candidates/{id}` | Delete a single candidate | Required |
| POST | `/export` | Re-run analysis + stream Excel download | Optional |
| GET | `/search?q=…` | Semantic search over ChromaDB | No |
| GET | `/debug/auth` | Debug: verify JWT + Supabase config | No |

When a valid `Authorization: Bearer <token>` header is present in `/analyze`, results are automatically saved to Supabase and `saved_to_db: true` is returned.

---

## Frontend Setup

```bash
cd frontend

npm install
npm run dev
```

App runs at `http://localhost:3000`

---

## Supabase Setup

1. Go to [supabase.com](https://supabase.com) → create a new project
2. **SQL Editor → New query** → paste the full contents of `supabase_schema_v2.sql` → click **Run**
3. **Authentication → Settings** → disable **Enable email confirmations** (recommended for local dev)
4. Sign in via the app's Sign In button — results will now save automatically on every analysis run

> If you previously ran `supabase_schema.sql` (v1), run `supabase_schema_v2.sql` — it adds the `analysis_sessions` table and two new columns (`candidate_name`, `college_name`) to the existing `candidates` table using `ADD COLUMN IF NOT EXISTS`, so it is safe to re-run.

---

## Environment Variables

### Where to find your Supabase keys

Go to your Supabase project → **Settings (gear icon) → API**

| Value to copy | Where it is | Used in |
|---|---|---|
| Project URL | Top of the page | Both files |
| `anon public` key | Under "Project API keys" | Both files |
| `service_role` key | Under "Project API keys" → click **Reveal** | Backend only |

---

### `frontend/.env.local`

Create this file inside the `frontend/` folder, at the same level as `package.json`.

```env
# Supabase project URL  —  Settings → API → Project URL
NEXT_PUBLIC_SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co

# Supabase anon / public key  —  Settings → API → anon public
NEXT_PUBLIC_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# FastAPI backend URL (local dev default)
NEXT_PUBLIC_API_URL=http://localhost:8000
```

After creating or editing this file **restart the dev server** — Next.js only reads `.env.local` at startup.

---

### `backend/.env`

Create this file inside the `backend/` folder, at the same level as `main.py`.

```env
# Supabase project URL  —  same as NEXT_PUBLIC_SUPABASE_URL
SUPABASE_URL=https://YOUR_PROJECT_REF.supabase.co

# service_role SECRET key  —  Settings → API → service_role (click Reveal)
# Never expose this to the browser or commit it to git
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# anon public key  —  same value as NEXT_PUBLIC_SUPABASE_ANON_KEY
SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...

# Optional — deployed frontend URL for CORS in production
# FRONTEND_URL=https://your-domain.com
```

---

### Complete variable reference

| Variable | File | Notes |
|---|---|---|
| `NEXT_PUBLIC_SUPABASE_URL` | `frontend/.env.local` | Project URL from Supabase dashboard |
| `NEXT_PUBLIC_SUPABASE_ANON_KEY` | `frontend/.env.local` | `anon public` key |
| `NEXT_PUBLIC_API_URL` | `frontend/.env.local` | `http://localhost:8000` for local dev |
| `SUPABASE_URL` | `backend/.env` | Same project URL |
| `SUPABASE_SERVICE_KEY` | `backend/.env` | `service_role` key — keep secret |
| `SUPABASE_ANON_KEY` | `backend/.env` | Same `anon public` key as frontend |
| `FRONTEND_URL` | `backend/.env` | Production only — for CORS |

**Formatting rules for both files:**
- No quotes around values — `KEY=value` not `KEY="value"`
- No spaces around `=`
- No trailing slash on the Supabase URL
- File names are exact: `.env.local` and `.env`

---

### Troubleshooting

| Symptom | Fix |
|---|---|
| `Invalid supabaseUrl` in browser | `NEXT_PUBLIC_SUPABASE_URL` is `undefined` — verify the file is named `.env.local` inside `frontend/`, then restart `npm run dev` |
| `user: null` from `/debug/auth` | SSL verification failing on Windows — `supabase_client.py` already uses `verify=False` to handle this; check the uvicorn terminal for other errors |
| `saved_to_db: false` after analysis | Not signed in, or JWT verification failed — check the terminal for error output |
| `Token exists: false` in console | Email not confirmed — go to **Authentication → Settings → disable "Enable email confirmations"** |
| History page shows no sessions | Analysis was run while logged out — sign in first, then run a new analysis |
| `Missing SUPABASE_URL` in terminal | `backend/.env` is missing or `python-dotenv` not installed — run `pip install python-dotenv` |
| `supabase_configured: false` in `/health` | `SUPABASE_SERVICE_KEY` not loaded — verify with `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('SUPABASE_URL'))"` |

---

## Architecture

```
Browser  (Next.js 16)
  │  Authorization: Bearer <supabase-jwt>
  │  multipart/form-data  (JD + resumes)
  ▼
FastAPI  main.py
  ├── resume_analyzer.py    spaCy NLP · name/college extraction · ChromaDB
  ├── llm_service.py        Ollama Gemma 3 · structured parsers
  └── supabase_client.py    Pure HTTP REST  (no SDK · verify=False for Windows SSL)
        ├── GET  /auth/v1/user                  JWT validation
        ├── POST /rest/v1/analysis_sessions      one row per run
        └── POST /rest/v1/candidates             one row per resume
```

---

## Production

- Set `NEXT_PUBLIC_API_URL` in `frontend/.env.local` to your deployed backend URL
- Set `FRONTEND_URL` in `backend/.env` to your frontend domain
- Update `allow_origins` in `main.py` to match your frontend domain
- Re-enable email confirmations in **Authentication → Settings** for production users
- Neither `.env` nor `.env.local` should ever be committed — both are in `.gitignore`
