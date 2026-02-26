"""Personalized job ranking: embedding similarity + heuristics; skill gap detection."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Tuple

from schemas.cv_profile import CVProfile
from schemas.structured_job import StructuredJob
from utils.logger import get_logger

if TYPE_CHECKING:
    from embeddings.embedding_service import EmbeddingService
    from ranking.vector_index import JobVectorIndex

logger = get_logger(__name__)

# Weights for final score
WEIGHT_EMBEDDING = 0.7
WEIGHT_LOCATION = 0.1
WEIGHT_RECENCY = 0.1
WEIGHT_SKILL_OVERLAP = 0.1


def _cv_summary_text(profile: CVProfile) -> str:
    """Build a single text blob for embedding from CV profile."""
    parts = []
    if profile.skills:
        parts.append("Skills: " + ", ".join(profile.skills))
    if profile.domain:
        parts.append("Domain: " + profile.domain)
    if profile.tools:
        parts.append("Tools: " + ", ".join(profile.tools))
    if profile.experience_years:
        parts.append("Experience: " + profile.experience_years)
    return " | ".join(parts) if parts else ""


def _job_text_for_embedding(job: StructuredJob) -> str:
    """Build a single text for embedding from job."""
    parts = []
    if job.title:
        parts.append(job.title)
    if job.company:
        parts.append(job.company)
    if job.skills:
        parts.append(", ".join(job.skills))
    if job.description_summary:
        parts.append(job.description_summary[:2000])
    return " | ".join(parts) if parts else ""


def _location_match_score(job: StructuredJob, user_locations: List[str]) -> float:
    """1.0 if job location matches any user location (or Remote), else 0.0."""
    if not user_locations:
        return 0.5
    job_loc = (job.location or "").lower() + " " + (job.searched_location or "").lower()
    for loc in user_locations:
        if loc and loc.lower() in job_loc:
            return 1.0
        if "remote" in loc.lower() and "remote" in job_loc:
            return 1.0
    return 0.0


def _recency_score(job: StructuredJob) -> float:
    """1.0 for fresh, decay over 90 days; 1.0 if no date."""
    if job.posted_days_ago is None:
        return 1.0
    if job.posted_days_ago <= 0:
        return 1.0
    return max(0.0, 1.0 - (job.posted_days_ago / 90.0))


def _skill_overlap_score(job: StructuredJob, cv_skills: List[str]) -> float:
    """Overlap: proportion of job skills that appear in CV skills (or vice versa for coverage)."""
    job_skills = set((s or "").strip().lower() for s in (job.skills or []) if (s or "").strip())
    cv_set = set((s or "").strip().lower() for s in cv_skills if (s or "").strip())
    if not job_skills:
        return 1.0
    overlap = len(job_skills & cv_set) / len(job_skills)
    return min(1.0, overlap)


def rank_jobs(
    jobs: List[StructuredJob],
    cv_profile: CVProfile,
    user_locations: List[str],
    embedding_service: EmbeddingService,
    vector_index: JobVectorIndex,
) -> List[Tuple[StructuredJob, float]]:
    """
    Rank jobs by combined score: 0.7 * embedding_similarity + 0.1 * location + 0.1 * recency + 0.1 * skill_overlap.
    Expects vector_index to be already built with job embeddings; job_id in index must match job.source_url.
    Returns list of (job, final_score) sorted descending.
    """
    if not jobs:
        return []
    cv_text = _cv_summary_text(cv_profile)
    cv_vec = embedding_service.embed_text(cv_text)
    # Search index by CV embedding to get similarity per job
    id_to_score = dict(vector_index.search(cv_vec, top_k=len(jobs) + 100))
    cv_skills = cv_profile.skills or []

    scored: List[Tuple[StructuredJob, float]] = []
    for job in jobs:
        emb_score = id_to_score.get(job.source_url, 0.0)
        # Clamp embedding similarity to [0,1]; FAISS cosine can be in [-1,1]
        emb_score = max(0.0, min(1.0, (emb_score + 1.0) / 2.0)) if emb_score else 0.0
        loc_score = _location_match_score(job, user_locations)
        rec_score = _recency_score(job)
        skill_score = _skill_overlap_score(job, cv_skills)
        final = (
            WEIGHT_EMBEDDING * emb_score
            + WEIGHT_LOCATION * loc_score
            + WEIGHT_RECENCY * rec_score
            + WEIGHT_SKILL_OVERLAP * skill_score
        )
        scored.append((job, final))
    scored.sort(key=lambda x: -x[1])
    return scored


def compute_skill_gaps(
    top_jobs: List[StructuredJob],
    cv_profile: CVProfile,
    top_n_skills_per_job: int = 10,
) -> Tuple[List[str], List[str]]:
    """
    From top jobs, extract required skills and compare with CV.
    Returns (missing_skills, recommended_skills_to_learn).
    missing_skills: skills required by jobs but not in CV.
    recommended_skills_to_learn: same as missing, or deduplicated list for learning suggestions.
    """
    cv_set = set((s or "").strip().lower() for s in (cv_profile.skills or []) if (s or "").strip())
    all_required: List[str] = []
    for job in top_jobs:
        for s in (job.skills or [])[:top_n_skills_per_job]:
            if (s or "").strip():
                all_required.append((s or "").strip())
    required_set = set(s.lower() for s in all_required)
    missing = sorted(required_set - cv_set, key=str.lower)
    # Normalize display: use title case or first occurrence
    missing_display = list(dict.fromkeys(s.strip() for s in all_required if s.lower() in missing))
    return missing_display, list(missing_display)


def build_job_index_and_embed(
    jobs: List[StructuredJob],
    embedding_service: EmbeddingService,
) -> JobVectorIndex:
    """
    Build FAISS index from job list: embed each job text, add to index with job_id = source_url.
    Call this when jobs change (e.g. after new search); cache the index in Streamlit with @st.cache_resource.
    """
    from ranking.vector_index import JobVectorIndex

    if not jobs:
        return JobVectorIndex(embedding_service.dimension)
    texts = [_job_text_for_embedding(j) for j in jobs]
    vectors = embedding_service.batch_embed(texts)
    index = JobVectorIndex(embedding_service.dimension)
    job_ids = [j.source_url for j in jobs]
    index.add_embeddings(vectors, job_ids)
    return index
