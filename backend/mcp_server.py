"""
mcp_server.py
─────────────
MCP (Model Context Protocol) server for the AI Resume Screener.

Exposes the screener's core capabilities as MCP tools so that AI assistants
(Claude Desktop, VS Code Copilot, Cursor, etc.) can directly analyze resumes,
query candidates, and interact with the screening pipeline.

Supports two transport modes:
  stdio            — for local MCP clients (Claude Desktop, VS Code, Cursor)
  streamable-http  — for remote access (deploy on Render, access from any device)

Run:
    python mcp_server.py                    # stdio mode (default, local)
    python mcp_server.py --transport http   # HTTP mode (remote, port 8001)
    mcp dev mcp_server.py                   # interactive MCP Inspector
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime

# ── Load .env before anything else ────────────────────────────────────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

from mcp.server.fastmcp import FastMCP

# Import the existing backend modules (no logic duplication)
import llm_service
import resume_analyzer as ra
import supabase_client as supa
import chat_service as chat

# ── Logging (must go to stderr, NOT stdout — stdio transport uses stdout) ─────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger("mcp_server")

# ── FastMCP instance ──────────────────────────────────────────────────────────
# Host/port are configurable via env vars for cloud deployment (e.g. Render)

MCP_HOST = os.getenv("MCP_HOST", "0.0.0.0")
MCP_PORT = int(os.getenv("MCP_PORT", "8001"))

mcp = FastMCP(
    "resume-screener",
    host=MCP_HOST,
    port=MCP_PORT,
    stateless_http=True,   # no sticky sessions — works behind load balancers
)


# ══════════════════════════════════════════════════════════════════════════════
#  RESOURCES
# ══════════════════════════════════════════════════════════════════════════════

@mcp.resource("resume-screener://status")
def get_status() -> str:
    """Live system status — Gemini config, Supabase config, model name, timestamp."""
    return json.dumps({
        "status":              "ok",
        "gemini_configured":   llm_service.is_gemini_configured(),
        "model":               os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "supabase_configured": supa.is_configured(),
        "timestamp":           datetime.now().isoformat(),
    }, indent=2)


# ══════════════════════════════════════════════════════════════════════════════
#  TOOLS
# ══════════════════════════════════════════════════════════════════════════════

# ── 1. Health check ───────────────────────────────────────────────────────────

@mcp.tool()
def health_check() -> str:
    """
    Check the health of the Resume Screener system.

    Returns the current status including whether Gemini AI and Supabase
    are properly configured, the active model name, and a timestamp.
    """
    return json.dumps({
        "status":              "ok",
        "gemini_configured":   llm_service.is_gemini_configured(),
        "model":               os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
        "supabase_configured": supa.is_configured(),
        "timestamp":           datetime.now().isoformat(),
    }, indent=2)


# ── 2. Extract JD skills ─────────────────────────────────────────────────────

@mcp.tool()
def extract_jd_skills(jd_text: str) -> str:
    """
    Extract required skills from a job description.

    Parses the job description text and returns structured data including
    technical skills, soft skills, tools & technologies, and experience level.

    Args:
        jd_text: The full text of the job description.
    """
    if not llm_service.is_gemini_configured():
        return json.dumps({"error": "Gemini API key is not configured. Set GEMINI_API_KEY in .env"})

    if not jd_text.strip():
        return json.dumps({"error": "Job description text is empty."})

    skills = llm_service.extract_jd_skills(jd_text)
    return json.dumps(skills, indent=2)


# ── 3. Analyze resume ────────────────────────────────────────────────────────

@mcp.tool()
def analyze_resume(resume_text: str, jd_text: str, resume_name: str = "resume") -> str:
    """
    Analyze a single resume against a job description.

    Returns a comprehensive analysis including:
    - Composite match score (0-100%)
    - Verdict (Strong/Moderate/Weak Match)
    - Keyword overlap and semantic similarity scores
    - AI skills comparison (matching/missing skills)
    - Candidate name and college extracted from the resume
    - AI-generated summary

    Args:
        resume_text: The full text content of the resume.
        jd_text: The full text of the job description to match against.
        resume_name: Optional filename or label for the resume (default: "resume").
    """
    if not resume_text.strip():
        return json.dumps({"error": "Resume text is empty."})
    if not jd_text.strip():
        return json.dumps({"error": "Job description text is empty."})

    ai_enabled = llm_service.is_gemini_configured()
    jd_skills_data = llm_service.extract_jd_skills(jd_text) if ai_enabled else None

    try:
        result = ra.analyze_resume(
            name=resume_name,
            text=resume_text,
            jd_text=jd_text,
            jd_skills_data=jd_skills_data,
            ai_enabled=ai_enabled,
        )
        # Remove non-serializable or overly verbose fields
        result.pop("raw_llm_output", None)
        result.pop("nltk_skills", None)
        result.pop("nltk_orgs", None)
        return json.dumps(result, indent=2, default=str)
    except Exception as e:
        logger.error(f"analyze_resume error: {e}")
        return json.dumps({"error": f"Analysis failed: {str(e)}"})


# ── 4. Search resumes ────────────────────────────────────────────────────────

@mcp.tool()
def search_resumes(query: str, num_results: int = 5) -> str:
    """
    Semantic search over all previously stored resumes and job descriptions
    using the ChromaDB vector database.

    Useful for finding resumes that match specific skills, technologies,
    or qualifications.

    Args:
        query: Natural language search query (e.g. "Python machine learning experience").
        num_results: Number of results to return (default: 5, max: 20).
    """
    num_results = min(max(1, num_results), 20)
    results = ra.search_documents(query, n_results=num_results)
    if results is None:
        return json.dumps({"error": "Vector database search failed."})
    return json.dumps({"query": query, "results": results}, indent=2, default=str)


# ── 5. List sessions ─────────────────────────────────────────────────────────

@mcp.tool()
def list_sessions(user_id: str) -> str:
    """
    List all analysis sessions for a user.

    Each session represents one analysis run (one JD + multiple resumes).
    Returns session metadata including JD info, candidate counts, scores,
    and AI summaries.

    Requires Supabase to be configured.

    Args:
        user_id: The Supabase user UUID.
    """
    if not supa.is_configured():
        return json.dumps({"error": "Supabase is not configured. Set SUPABASE_URL and SUPABASE_SERVICE_KEY in .env"})

    sessions = supa.get_sessions(user_id)
    return json.dumps({
        "user_id": user_id,
        "total": len(sessions),
        "sessions": sessions,
    }, indent=2, default=str)


# ── 6. Get session candidates ────────────────────────────────────────────────

@mcp.tool()
def get_session_candidates(session_id: str, user_id: str) -> str:
    """
    Get all candidates from a specific analysis session.

    Returns detailed results for each resume analyzed in the session,
    including scores, verdicts, skills comparisons, and AI summaries.

    Requires Supabase to be configured.

    Args:
        session_id: The UUID of the analysis session.
        user_id: The Supabase user UUID (for access scoping).
    """
    if not supa.is_configured():
        return json.dumps({"error": "Supabase is not configured."})

    candidates = supa.get_session_candidates(session_id, user_id)
    return json.dumps({
        "session_id": session_id,
        "total": len(candidates),
        "candidates": candidates,
    }, indent=2, default=str)


# ── 7. List candidates ───────────────────────────────────────────────────────

@mcp.tool()
def list_candidates(user_id: str, limit: int = 50) -> str:
    """
    List all candidates across all sessions for a user.

    Returns a flat list of every candidate ever analyzed, sorted by date
    (newest first). Useful for cross-session comparisons.

    Requires Supabase to be configured.

    Args:
        user_id: The Supabase user UUID.
        limit: Maximum number of candidates to return (default: 50, max: 200).
    """
    if not supa.is_configured():
        return json.dumps({"error": "Supabase is not configured."})

    limit = min(max(1, limit), 200)
    candidates = supa.get_candidates(user_id, limit)
    return json.dumps({
        "user_id": user_id,
        "total": len(candidates),
        "candidates": candidates,
    }, indent=2, default=str)


# ── 8. Ask recruiter AI ──────────────────────────────────────────────────────

@mcp.tool()
def ask_recruiter_ai(question: str, user_id: str = "") -> str:
    """
    Ask the ResumeAI recruiter assistant a question about candidates.

    The AI assistant has access to all candidate data and analysis sessions
    in the database and can answer questions like:
    - "Who is the best candidate for this role?"
    - "Compare the top 3 candidates"
    - "What skills are most candidates missing?"
    - "Summarize the last analysis run"

    If user_id is provided and Supabase is configured, the assistant will
    have access to stored candidate data for context-aware answers.

    Args:
        question: Your question about candidates, hiring, or recruitment.
        user_id: Optional Supabase user UUID for accessing stored data.
    """
    if not llm_service.is_gemini_configured():
        return json.dumps({"error": "Gemini API key is not configured."})

    # Load candidate context if user_id provided
    candidates: list[dict] = []
    sessions: list[dict] = []

    if user_id and supa.is_configured():
        candidates = supa.get_candidates(user_id, limit=50)
        sessions = supa.get_sessions(user_id, limit=10)

    system_prompt = chat.build_system_prompt(candidates, sessions)

    # Use synchronous Gemini call (not streaming) for MCP tool response
    from google import genai

    try:
        client = genai.Client(api_key=os.getenv("GEMINI_API_KEY", ""))
        response = client.models.generate_content(
            model=os.getenv("GEMINI_MODEL", "gemini-2.0-flash"),
            contents=[{"role": "user", "parts": [{"text": question}]}],
            config={
                "system_instruction": system_prompt,
                "temperature": 0.7,
                "max_output_tokens": 1024,
            },
        )
        return response.text.strip()
    except Exception as e:
        logger.error(f"ask_recruiter_ai error: {e}")
        return json.dumps({"error": f"AI chat failed: {str(e)}"})


# ══════════════════════════════════════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Resume Screener MCP Server")
    parser.add_argument(
        "--transport", "-t",
        choices=["stdio", "http"],
        default=os.getenv("MCP_TRANSPORT", "stdio"),
        help="Transport mode: 'stdio' for local clients, 'http' for remote access (default: stdio)",
    )
    args = parser.parse_args()

    if args.transport == "http":
        logger.info(f"Starting Resume Screener MCP Server (Streamable HTTP on {MCP_HOST}:{MCP_PORT}/mcp)")
        mcp.run(transport="streamable-http")
    else:
        logger.info("Starting Resume Screener MCP Server (stdio transport)")
        mcp.run(transport="stdio")
