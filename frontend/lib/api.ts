// lib/api.ts

// In production, route through Next.js rewrite proxy (/api) to avoid
// cross-origin requests being blocked by ad blockers / browser extensions.
// In development, hit the backend directly for faster iteration.
const BASE =
  typeof window !== "undefined" && process.env.NODE_ENV === "production"
    ? "/api"
    : (process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000");

function authHeaders(token?: string | null): HeadersInit {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

// ── Types ─────────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  gemini_configured: boolean;
  model: string;
  supabase_configured: boolean;
  timestamp: string;
}

export interface SkillsData {
  technical_skills: string[];
  soft_skills: string[];
  tools_technologies: string[];
  experience_level: string;
}

export interface SkillsComparison {
  matching_technical: string[];
  missing_technical:  string[];
  matching_soft:      string[];
  missing_soft:       string[];
  matching_tools:     string[];
  missing_tools:      string[];
  skills_match_score: number;
  experience_fit:     string;
  overall_assessment: string;
  raw_llm_output:     string;
}

export interface ResumeResult {
  name:               string;
  candidate_name:     string | null;
  college_name:       string | null;
  score_pct:          number;
  verdict:            "Strong Match" | "Moderate Match" | "Weak Match";
  keyword_overlap:    number;
  vector_similarity:  number;
  skills_match_score: number | null;
  matched_keywords:   string[];
  missing_keywords:   string[];
  skills_comparison:  SkillsComparison | null;
  resume_skills_data: SkillsData | null;
  ai_summary:         string | null;
  nltk_skills:        { word: string; count: number }[];
  nltk_orgs:          { word: string; count: number }[];
  raw_llm_output:     string;
}

export interface AnalyzeResponse {
  ai_enabled:        boolean;
  jd_skills:         SkillsData | null;
  jd_keywords:       { word: string; count: number }[];
  results:           ResumeResult[];
  ranking_analysis:  string | null;
  executive_summary: string | null;
  session_id:        string;
  saved_to_db:       boolean;
  stats: {
    total: number; avg: number;
    strong: number; moderate: number; weak: number;
  };
}

export interface AnalysisSession {
  id:                  string;
  created_at:          string;
  jd_filename:         string | null;
  jd_experience_level: string | null;
  jd_technical_skills: string[];
  jd_soft_skills:      string[];
  jd_tools:            string[];
  total_candidates:    number;
  avg_score:           number;
  strong_count:        number;
  moderate_count:      number;
  weak_count:          number;
  ranking_analysis:    string | null;
  executive_summary:   string | null;
  ai_enabled:          boolean;
}

export interface Candidate {
  id:                  string;
  created_at:          string;
  session_id:          string;
  file_name:           string;
  candidate_name:      string | null;
  college_name:        string | null;
  score_pct:           number;
  verdict:             string;
  keyword_overlap:     number;
  vector_similarity:   number;
  skills_match_score:  number | null;
  matched_keywords:    string[];
  missing_keywords:    string[];
  matching_technical:  string[];
  missing_technical:   string[];
  matching_soft:       string[];
  missing_soft:        string[];
  matching_tools:      string[];
  missing_tools:       string[];
  experience_fit:      string | null;
  overall_assessment:  string | null;
  resume_technical:    string[];
  resume_soft:         string[];
  resume_tools:        string[];
  experience_level:    string | null;
  ai_summary:          string | null;
  jd_experience_level: string | null;
  jd_technical_skills: string[];
}

// ── API calls ─────────────────────────────────────────────────────────────────

export async function fetchHealth(): Promise<HealthResponse> {
  const MAX_RETRIES = 3;
  const TIMEOUT_MS  = 15_000; // 15s per attempt (Render cold start can take 30-60s)

  for (let attempt = 1; attempt <= MAX_RETRIES; attempt++) {
    try {
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);

      const res = await fetch(`${BASE}/health`, { signal: controller.signal });
      clearTimeout(timer);

      if (!res.ok) throw new Error("Backend unreachable");
      return res.json();
    } catch (err) {
      if (attempt === MAX_RETRIES) throw err;
      // Wait 2s before retrying (give Render time to spin up)
      await new Promise((r) => setTimeout(r, 2000));
    }
  }
  throw new Error("Backend unreachable after retries");
}

export async function analyzeResumes(
  jdFile: File, resumeFiles: File[], enableAi: boolean, token?: string | null
): Promise<AnalyzeResponse> {
  const form = new FormData();
  form.append("jd_file", jdFile);
  resumeFiles.forEach((f) => form.append("resumes", f));
  form.append("enable_ai", String(enableAi));
  const res = await fetch(`${BASE}/analyze`, {
    method: "POST", body: form, headers: authHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Analysis failed");
  }
  return res.json();
}

export async function fetchSessions(token: string): Promise<AnalysisSession[]> {
  const res = await fetch(`${BASE}/sessions`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error("Failed to load sessions");
  const data = await res.json();
  return data.sessions as AnalysisSession[];
}

export async function fetchSessionCandidates(sessionId: string, token: string): Promise<Candidate[]> {
  const res = await fetch(`${BASE}/sessions/${sessionId}/candidates`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error("Failed to load candidates");
  const data = await res.json();
  return data.candidates as Candidate[];
}

export async function deleteSession(sessionId: string, token: string): Promise<void> {
  const res = await fetch(`${BASE}/sessions/${sessionId}`, {
    method: "DELETE", headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Delete failed");
}

export async function fetchCandidates(token: string): Promise<Candidate[]> {
  const res = await fetch(`${BASE}/candidates`, { headers: authHeaders(token) });
  if (!res.ok) throw new Error("Failed to load candidates");
  return (await res.json()).candidates as Candidate[];
}

export async function deleteCandidate(id: string, token: string): Promise<void> {
  const res = await fetch(`${BASE}/candidates/${id}`, {
    method: "DELETE", headers: authHeaders(token),
  });
  if (!res.ok) throw new Error("Delete failed");
}

export function buildExportUrl(
  jdFile: File, resumeFiles: File[], enableAi: boolean, token?: string | null
): { download: () => Promise<void> } {
  return {
    async download() {
      const form = new FormData();
      form.append("jd_file", jdFile);
      resumeFiles.forEach((f) => form.append("resumes", f));
      form.append("enable_ai", String(enableAi));
      const res = await fetch(`${BASE}/export`, {
        method: "POST", body: form, headers: authHeaders(token),
      });
      if (!res.ok) throw new Error("Export failed");
      const blob = await res.blob();
      const url  = URL.createObjectURL(blob);
      const a    = document.createElement("a");
      a.href = url; a.download = `resume_analysis_${Date.now()}.xlsx`;
      a.click(); URL.revokeObjectURL(url);
    },
  };
}