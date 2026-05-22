"""
resume_analyzer.py
------------------
Text extraction, NLP scoring, ChromaDB vector store, name/college extraction,
and per-resume pipeline.
"""

import io
import os
import re
import logging
from collections import Counter
from datetime import datetime
from pathlib import Path

import chromadb
import nltk
import numpy as np
import spacy
import urllib3
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from nltk import pos_tag
from PyPDF2 import PdfReader
import docx2txt

import llm_service

logger = logging.getLogger(__name__)
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
os.environ["TOKENIZERS_PARALLELISM"] = "false"

# ── spaCy ─────────────────────────────────────────────────────────────────────
nlp = spacy.load("en_core_web_md")

# ── NLTK ──────────────────────────────────────────────────────────────────────
nltk.data.path.append(str(Path.cwd() / "nltk"))
for _name, _path in [
    ("punkt_tab",                  "tokenizers/punkt_tab"),
    ("stopwords",                  "corpora/stopwords"),
    ("averaged_perceptron_tagger", "taggers/averaged_perceptron_tagger"),
]:
    try:
        nltk.data.find(_path)
    except LookupError:
        nltk.download(_name)

# ── ChromaDB ──────────────────────────────────────────────────────────────────
# Use in-memory mode on cloud (Render free tier has ephemeral storage anyway)
if os.getenv("CHROMADB_EPHEMERAL", "false").lower() in ("true", "1", "yes"):
    _chroma = chromadb.EphemeralClient()
else:
    _chroma = chromadb.PersistentClient(path="./resume_database")
collection = _chroma.get_or_create_collection(name="resumes_and_jd")


# ── Text extraction ───────────────────────────────────────────────────────────

def extract_text_from_bytes(file_bytes: bytes, content_type: str) -> str:
    if "pdf" in content_type:
        try:
            reader = PdfReader(io.BytesIO(file_bytes))
            return "".join(p.extract_text() or "" for p in reader.pages)
        except Exception as e:
            logger.error(f"PDF extraction error: {e}")
            return ""
    if "wordprocessingml" in content_type or "docx" in content_type:
        try:
            return docx2txt.process(io.BytesIO(file_bytes))
        except Exception as e:
            logger.error(f"DOCX extraction error: {e}")
            return ""
    logger.warning(f"Unsupported content type: {content_type}")
    return ""


# ── Name & College extraction ─────────────────────────────────────────────────

# Common college/university keywords
_EDU_KEYWORDS = [
    "university", "college", "institute", "institution", "school",
    "iit", "nit", "bits", "iiit", "iim", "academy", "polytechnic",
    "mit", "stanford", "harvard", "oxford", "cambridge",
]

# Sections that signal we've moved past the header into experience
_STOP_SECTIONS = [
    "experience", "work experience", "employment", "internship",
    "projects", "skills", "certifications", "achievements",
    "objective", "summary", "profile",
]

def extract_candidate_name(text: str) -> str | None:
    """
    Extract candidate name from resume text.
    Strategy: look at the first 10 non-empty lines — the name is almost always
    the very first prominent line (all caps, title case, short, no digits).
    Falls back to spaCy PERSON NER on the first 500 chars.
    """
    lines = [l.strip() for l in text.split("\n") if l.strip()][:15]

    for line in lines[:6]:
        # Skip lines that look like contact info, headers, or objective text
        if any(x in line.lower() for x in ["@", "http", "phone", "email", "mobile",
                                             "address", "linkedin", "github", "resume",
                                             "curriculum", "objective", "summary"]):
            continue
        # Skip lines with digits (phone numbers, dates, zip codes)
        if re.search(r"\d", line):
            continue
        # Name is usually 2–4 words, title-case or all-caps, no special chars
        words = line.split()
        if 2 <= len(words) <= 5:
            clean = re.sub(r"[^a-zA-Z\s\-\.]", "", line).strip()
            if len(clean) >= 4 and (line.istitle() or line.isupper() or
                                     re.match(r"^[A-Z][a-z]+ [A-Z]", line)):
                return clean.title()

    # spaCy fallback on first 500 chars
    doc = nlp(text[:500])
    for ent in doc.ents:
        if ent.label_ == "PERSON" and 2 <= len(ent.text.split()) <= 4:
            return ent.text.strip().title()

    return None


def extract_college_name(text: str) -> str | None:
    """
    Extract college/university name from resume text.
    Strategy:
    1. Find lines containing education keywords
    2. spaCy ORG NER filtered by edu keywords
    3. Regex for known patterns like "B.Tech from XYZ University"
    """
    lines = text.split("\n")

    # Find where education section is — look for "Education" header
    edu_start = 0
    for i, line in enumerate(lines):
        if re.search(r"\beducation\b", line, re.IGNORECASE):
            edu_start = i
            break

    # Search in education section first (lines around the "Education" header)
    search_lines = lines[edu_start: edu_start + 20] if edu_start else lines[:60]

    for line in search_lines:
        line_clean = line.strip()
        if not line_clean:
            continue
        ll = line_clean.lower()
        if any(kw in ll for kw in _EDU_KEYWORDS):
            # Remove degree info, keep institution name
            # e.g. "B.Tech | Computer Science | IIT Bombay" → "IIT Bombay"
            parts = re.split(r"[|,\-–]", line_clean)
            for part in reversed(parts):
                part = part.strip()
                if any(kw in part.lower() for kw in _EDU_KEYWORDS) and len(part) > 4:
                    return re.sub(r"\s+", " ", part).strip()
            # Return the whole line if it contains edu keyword
            if len(line_clean) < 100:
                return line_clean

    # spaCy ORG NER fallback
    excerpt = "\n".join(lines[edu_start: edu_start + 30]) if edu_start else text[:1500]
    doc = nlp(excerpt)
    for ent in doc.ents:
        if ent.label_ == "ORG":
            if any(kw in ent.text.lower() for kw in _EDU_KEYWORDS):
                return ent.text.strip()

    # Regex pattern fallback: "from XYZ University" or "at XYZ College"
    match = re.search(
        r"(?:from|at|,)\s+([A-Z][A-Za-z\s\-\.]{5,60}(?:University|College|Institute|School|IIT|NIT|BITS|IIIT))",
        text[:2000]
    )
    if match:
        return match.group(1).strip()

    return None


# ── NLTK keyword analysis ─────────────────────────────────────────────────────

def get_keyword_counts(text: str, tags=("NN", "NNS")) -> list[dict]:
    try:
        tokens   = word_tokenize(text)
        stops    = set(stopwords.words("english"))
        filtered = [w for w in tokens if w.isalpha() and w.lower() not in stops]
        counts   = Counter(w for w, t in pos_tag(filtered) if t in tags)
        return [{"word": w, "count": c} for w, c in counts.most_common(50)]
    except LookupError:
        return []


def get_org_counts(text: str) -> list[dict]:
    try:
        tokens   = word_tokenize(text)
        stops    = set(stopwords.words("english"))
        filtered = [w for w in tokens if w.isalpha() and w.lower() not in stops]
        counts   = Counter(w for w, t in pos_tag(filtered) if t == "NNP")
        return [{"word": w, "count": c} for w, c in counts.most_common(20)]
    except LookupError:
        return []


# ── Vector DB ─────────────────────────────────────────────────────────────────

def store_document(doc_id: str, content: str, metadata: dict) -> bool:
    try:
        collection.add(ids=[doc_id], documents=[content], metadatas=[metadata])
        return True
    except Exception as e:
        logger.error(f"ChromaDB store error: {e}")
        return False


def search_documents(query: str, n_results: int = 5):
    try:
        return collection.query(query_texts=[query], n_results=n_results)
    except Exception as e:
        logger.error(f"ChromaDB search error: {e}")
        return None


# ── NLP scoring ───────────────────────────────────────────────────────────────

def _content_tokens(doc):
    return [
        t for t in doc
        if t.is_alpha and not t.is_stop and t.has_vector
        and t.pos_ in ("NOUN", "VERB", "ADJ", "PROPN")
    ]


def compute_scores(resume_text: str, jd_text: str,
                   skills_comparison: dict | None = None) -> dict:
    r_doc = nlp(resume_text)
    j_doc = nlp(jd_text)

    jd_tokens     = _content_tokens(j_doc)
    resume_tokens = _content_tokens(r_doc)

    jd_lemmas     = {t.lemma_.lower() for t in jd_tokens}
    resume_lemmas = {t.lemma_.lower() for t in resume_tokens}

    keyword_overlap = len(jd_lemmas & resume_lemmas) / len(jd_lemmas) if jd_lemmas else 0.0

    jd_counts = Counter(t.lemma_.lower() for t in jd_tokens)
    total_jd  = sum(jd_counts.values()) or 1
    vec_len   = j_doc.vocab.vectors_length
    jd_vec    = sum(
        t.vector * (jd_counts[t.lemma_.lower()] / total_jd)
        for t in jd_tokens
    ) if jd_tokens else np.zeros(vec_len)

    resume_vec = (
        np.mean([t.vector for t in resume_tokens], axis=0)
        if resume_tokens else np.zeros(vec_len)
    )

    norm_r, norm_j = np.linalg.norm(resume_vec), np.linalg.norm(jd_vec)
    vector_sim = (
        float(np.dot(resume_vec, jd_vec) / (norm_r * norm_j))
        if norm_r > 0 and norm_j > 0 else 0.0
    )

    ai_score  = (skills_comparison or {}).get("skills_match_score", 0.0)
    composite = (
        0.4 * keyword_overlap + 0.3 * vector_sim + 0.3 * ai_score
        if skills_comparison and ai_score > 0
        else 0.6 * keyword_overlap + 0.4 * vector_sim
    )

    return {
        "keyword_overlap_score": round(keyword_overlap, 4),
        "vector_similarity":     round(vector_sim, 4),
        "composite_score":       round(composite, 4),
        "matched_keywords":      sorted(jd_lemmas & resume_lemmas),
        "missing_keywords":      sorted(jd_lemmas - resume_lemmas),
        "skills_match_score":    round(ai_score, 4),
    }


# ── Full resume pipeline ──────────────────────────────────────────────────────

def analyze_resume(name: str, text: str, jd_text: str,
                   jd_skills_data: dict | None, ai_enabled: bool) -> dict:
    """
    Full analysis for a single resume. Returns a dict with all results
    needed by the FastAPI response model.
    """
    skills_comparison  = None
    resume_skills_data = None
    ai_summary         = None

    if ai_enabled and jd_skills_data:
        skills_comparison  = llm_service.compare_resume_to_jd(jd_skills_data, jd_text, text)
        resume_skills_data = llm_service.extract_resume_skills(text)
        ai_summary         = llm_service.generate_resume_summary(text, jd_text)

    scores    = compute_scores(text, jd_text, skills_comparison)
    score_pct = round(scores["composite_score"] * 100, 1)

    verdict = (
        "Strong Match"   if score_pct >= 70 else
        "Moderate Match" if score_pct >= 45 else
        "Weak Match"
    )

    # Extract name and college
    candidate_name = extract_candidate_name(text)
    college_name   = extract_college_name(text)

    logger.info(f"Extracted — name: {candidate_name!r}, college: {college_name!r}")

    store_document(f"resume_{name}", text, {
        "type":        "resume",
        "upload_date": datetime.now().isoformat(),
        "score":       score_pct,
        "verdict":     verdict,
        "word_count":  len(text.split()),
    })

    return {
        "name":                name,
        "candidate_name":      candidate_name,
        "college_name":        college_name,
        "score_pct":           score_pct,
        "verdict":             verdict,
        "keyword_overlap":     round(scores["keyword_overlap_score"] * 100, 1),
        "vector_similarity":   round(scores["vector_similarity"] * 100, 1),
        "skills_match_score":  round(scores["skills_match_score"] * 100, 1) if ai_enabled and skills_comparison else None,
        "matched_keywords":    scores["matched_keywords"],
        "missing_keywords":    scores["missing_keywords"][:20],
        "skills_comparison":   skills_comparison,
        "resume_skills_data":  resume_skills_data,
        "ai_summary":          ai_summary,
        "nltk_skills":         get_keyword_counts(text),
        "nltk_orgs":           get_org_counts(text),
        "raw_llm_output":      (skills_comparison or {}).get("raw_llm_output", ""),
    }