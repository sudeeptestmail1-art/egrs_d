# 🔌 MCP Server Guide — AI Resume Screener

> Use the Resume Screener directly from your AI assistant (Claude Desktop, VS Code, Cursor, etc.) via the **Model Context Protocol** — locally or remotely.

---

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) (MCP) is an open standard that lets AI assistants connect to external tools and data sources. Instead of copy-pasting text into a chat window, your AI assistant can **directly call** the Resume Screener's analysis tools — extracting skills, scoring resumes, querying candidates — all through natural language.

The server supports **two transport modes**:

```
LOCAL (stdio)                              REMOTE (Streamable HTTP)

┌──────────────┐  stdin/stdout  ┌────────┐     ┌──────────────┐  HTTPS   ┌────────────────────┐
│ Claude       │◄──────────────►│ MCP    │     │ Any MCP      │◄────────►│ MCP Server         │
│ Desktop      │   JSON-RPC     │ Server │     │ Client       │  /mcp    │ on Render           │
└──────────────┘  (same machine)│(local) │     │ (any device) │          │ (cloud)            │
                                └────────┘     └──────────────┘          └────────────────────┘
```

---

## Prerequisites

1. **Python 3.10+** installed
2. **Backend dependencies** already installed (see main [README](./README.md))
3. **Gemini API key** configured in `backend/.env` (required for AI-powered tools)
4. **Supabase** configured in `backend/.env` (optional — only needed for session/candidate tools)

---

## Installation

From the project root:

```bash
cd backend

# If you haven't installed the base dependencies yet:
pip install -r requirements.txt

# Download the spaCy model (if not already done):
python -m spacy download en_core_web_md
```

The `mcp[cli]>=1.2.0` dependency is already in `requirements.txt`.

To verify the MCP SDK is installed:

```bash
python -c "from mcp.server.fastmcp import FastMCP; print('✅ MCP SDK installed')"
```

---

## Running the MCP Server

### Mode 1: Local (stdio) — Default

```bash
cd backend
python mcp_server.py
```

This starts the server on **stdio** transport. It will appear to hang — that's normal! It's waiting for JSON-RPC messages from an MCP client.

Press `Ctrl+C` to stop.

### Mode 2: Remote (Streamable HTTP)

```bash
cd backend
python mcp_server.py --transport http
```

This starts an HTTP server on `http://0.0.0.0:8001/mcp` that any MCP client can connect to over the network. This is the mode you need for **Render deployment** and **remote access**.

Configure host/port via environment variables:

| Variable | Default | Description |
|---|---|---|
| `MCP_HOST` | `0.0.0.0` | Bind address |
| `MCP_PORT` | `8001` | Port number |
| `MCP_TRANSPORT` | `stdio` | Default transport when `--transport` flag is omitted |

### With MCP Inspector (interactive debugging)

```bash
cd backend
mcp dev mcp_server.py
```

This opens a browser UI where you can see all tools, call them interactively, and inspect JSON-RPC messages.

---

## Deploying on Render (Remote Access)

This lets you access the MCP server from **any device, anywhere**.

### Step 1: Add a Render service

In your Render dashboard, create a **new Web Service** with:

| Setting | Value |
|---|---|
| **Build Command** | `cd backend && pip install -r requirements.txt && python -m spacy download en_core_web_md` |
| **Start Command** | `cd backend && python mcp_server.py --transport http` |

### Step 2: Set environment variables

In Render's **Environment** tab, add:

| Variable | Value |
|---|---|
| `GEMINI_API_KEY` | Your Gemini API key |
| `GEMINI_MODEL` | `gemini-2.0-flash` |
| `MCP_TRANSPORT` | `http` |
| `MCP_PORT` | `8001` |
| `CHROMADB_EPHEMERAL` | `true` |
| `SUPABASE_URL` | *(your Supabase URL)* |
| `SUPABASE_SERVICE_KEY` | *(your Supabase service key)* |
| `SUPABASE_ANON_KEY` | *(your Supabase anon key)* |

> **Note**: If you're already running the FastAPI backend on Render (port 8000), the MCP server uses port **8001** by default — so they don't conflict. You can run both as separate Render services, or set `MCP_PORT` to match Render's `PORT` env var if running as a standalone service.

> **Tip**: Render auto-assigns `PORT`. To use it: set `MCP_PORT` to `$PORT` in Render's Start Command:
> ```
> cd backend && MCP_PORT=$PORT python mcp_server.py --transport http
> ```

### Step 3: Get your MCP endpoint URL

Once deployed, your MCP endpoint will be:

```
https://your-mcp-server.onrender.com/mcp
```

### Step 4: Connect from any device

Use this URL in any MCP client's **remote server configuration** (see sections below).

---

## Client Configuration

### Local Clients (stdio)

These spawn the server as a local subprocess — only works on the same machine.

#### Claude Desktop

1. Open your Claude Desktop config file:
   - **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
   - **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`
   - **Linux**: `~/.config/Claude/claude_desktop_config.json`

2. Add the Resume Screener server:

```json
{
  "mcpServers": {
    "resume-screener": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/backend/mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here",
        "GEMINI_MODEL": "gemini-2.0-flash"
      }
    }
  }
}
```

> **Important**: Replace `/ABSOLUTE/PATH/TO/backend/mcp_server.py` with the actual absolute path. If using a venv, point `command` to `.venv/bin/python`.

3. Restart Claude Desktop.

#### VS Code (GitHub Copilot)

Create `.vscode/mcp.json` in the project root:

```json
{
  "servers": {
    "resume-screener": {
      "command": "python",
      "args": ["backend/mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here",
        "GEMINI_MODEL": "gemini-2.0-flash"
      }
    }
  }
}
```

#### Cursor

Create `.cursor/mcp.json` in the project root:

```json
{
  "mcpServers": {
    "resume-screener": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/backend/mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here",
        "GEMINI_MODEL": "gemini-2.0-flash"
      }
    }
  }
}
```

#### Gemini CLI

Add to `~/.gemini/settings.json`:

```json
{
  "mcpServers": {
    "resume-screener": {
      "command": "python",
      "args": ["/ABSOLUTE/PATH/TO/backend/mcp_server.py"],
      "env": {
        "GEMINI_API_KEY": "your_gemini_api_key_here"
      }
    }
  }
}
```

---

### Remote Clients (Streamable HTTP)

These connect to the deployed MCP server over the network — works from **any device**.

#### Claude Desktop (remote)

```json
{
  "mcpServers": {
    "resume-screener": {
      "type": "streamable-http",
      "url": "https://your-mcp-server.onrender.com/mcp"
    }
  }
}
```

#### VS Code (remote)

In `.vscode/mcp.json`:

```json
{
  "servers": {
    "resume-screener": {
      "type": "http",
      "url": "https://your-mcp-server.onrender.com/mcp"
    }
  }
}
```

#### Cursor (remote)

In `.cursor/mcp.json`:

```json
{
  "mcpServers": {
    "resume-screener": {
      "url": "https://your-mcp-server.onrender.com/mcp"
    }
  }
}
```

---

## Available Tools

| # | Tool | Description | Parameters |
|---|---|---|---|
| 1 | `health_check` | System status — Gemini/Supabase config, model name | *(none)* |
| 2 | `extract_jd_skills` | Extract required skills from a job description | `jd_text` |
| 3 | `analyze_resume` | Full resume analysis against a JD — scores, verdict, skills comparison | `resume_text`, `jd_text`, `resume_name` (optional) |
| 4 | `search_resumes` | Semantic search over stored resumes via ChromaDB | `query`, `num_results` (optional) |
| 5 | `list_sessions` | List all analysis sessions for a user | `user_id` |
| 6 | `get_session_candidates` | Get candidates from a specific session | `session_id`, `user_id` |
| 7 | `list_candidates` | List all candidates across sessions | `user_id`, `limit` (optional) |
| 8 | `ask_recruiter_ai` | Chat with the ResumeAI assistant about candidates | `question`, `user_id` (optional) |

### Resources

| URI | Description |
|---|---|
| `resume-screener://status` | Live system health status |

---

## Usage Examples

Once connected, just ask your AI assistant naturally:

### Basic health check
> "Check if the resume screener is running and properly configured."

### Extract skills from a JD
> "Extract the required skills from this job description: [paste JD text]"

### Analyze a resume
> "Analyze this resume against the following job description and tell me if they're a good fit:
>
> **Job Description:** [paste JD]
>
> **Resume:** [paste resume text]"

### Search stored resumes
> "Search the resume database for candidates with Python and machine learning experience."

### Query candidate data (requires Supabase + user_id)
> "List all my analysis sessions."
>
> "Show me the candidates from my latest session."
>
> "Who are the top candidates across all my analyses?"

### Ask the recruiter AI
> "Based on my candidate data, who should I interview first and why?"
>
> "What technical skills are most commonly missing across my candidates?"

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| Server doesn't start | Make sure you're running from the `backend/` directory, or the imports for `llm_service`, `resume_analyzer`, etc. won't resolve. |
| `ModuleNotFoundError: mcp` | Run `pip install "mcp[cli]>=1.2.0"` in your backend virtual environment. |
| `ModuleNotFoundError: spacy` | Run `pip install -r requirements.txt && python -m spacy download en_core_web_md`. |
| Tools show but calls fail | Check that `GEMINI_API_KEY` is set. Either put it in `backend/.env` or pass it via the `env` field in your MCP client config. |
| Supabase tools return errors | `SUPABASE_URL` and `SUPABASE_SERVICE_KEY` must be set. These are only needed for session/candidate tools. |
| Claude Desktop doesn't see the server | Verify the absolute path in `claude_desktop_config.json` is correct. Use the full path to the Python binary if using a venv. Restart Claude Desktop after editing the config. |
| `print()` breaks the server (stdio) | MCP stdio uses stdout for JSON-RPC. Never use `print()` in server code — use `logging` (which goes to stderr) instead. |
| Inspector doesn't open | Run `mcp dev mcp_server.py` from the `backend/` directory. Make sure `mcp[cli]` is installed. |
| Render port conflict | Set `MCP_PORT=$PORT` in the start command so Render assigns the port. |
| Remote client can't connect | Ensure the Render service is running and the URL ends with `/mcp`. Check Render logs for startup errors. |

---

## Architecture

The MCP server is a thin adapter layer — it imports and reuses the existing backend modules directly:

```
mcp_server.py
  │
  ├── llm_service.py        → Gemini API calls (extract skills, compare, summarize)
  ├── resume_analyzer.py    → NLP scoring, name/college extraction, ChromaDB
  ├── supabase_client.py    → Session & candidate CRUD
  └── chat_service.py       → ResumeAI assistant system prompt builder
```

No business logic is duplicated. The MCP server simply translates tool calls into function calls on the existing modules and formats the results as JSON strings.

The FastAPI server (`main.py`) and MCP server (`mcp_server.py`) are **independent** — you can run either or both. They share the same `.env` configuration and backend modules.

| | FastAPI (`main.py`) | MCP (`mcp_server.py`) |
|---|---|---|
| **Purpose** | Web app backend (REST API) | AI assistant integration |
| **Port** | 8000 | 8001 |
| **Clients** | Browser / frontend | Claude, VS Code, Cursor, etc. |
| **Transport** | HTTP REST | stdio or Streamable HTTP |
| **Auth** | Supabase JWT | None (local trust) / future OAuth |
