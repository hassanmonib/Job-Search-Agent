"""Query strategy layer: Title-based (user intent) vs Resume-based (skill-driven) search."""

from abc import ABC, abstractmethod
from typing import List, Tuple

from config import AVAILABLE_SOURCES
from utils.logger import get_logger

logger = get_logger(__name__)

# (source_key, location, query)
QueryTuple = Tuple[str, str, str]

# Max queries for resume mode to avoid API overload
RESUME_MAX_QUERIES = 10
RESUME_MAX_ROLES = 8


# Skill → inferred job roles (extensible; future-ready for career path inference)
SKILL_TO_ROLE_MAP: dict[str, list[str]] = {
    "tensorflow": ["Machine Learning Engineer", "AI Engineer"],
    "pytorch": ["Machine Learning Engineer", "Deep Learning Engineer"],
    "nlp": ["NLP Engineer", "AI Engineer"],
    "natural language processing": ["NLP Engineer", "AI Engineer"],
    "react": ["Frontend Developer", "React Developer"],
    "vue": ["Frontend Developer"],
    "angular": ["Frontend Developer"],
    "aws": ["Cloud Engineer", "DevOps Engineer"],
    "azure": ["Cloud Engineer", "DevOps Engineer"],
    "gcp": ["Cloud Engineer", "DevOps Engineer"],
    "kubernetes": ["DevOps Engineer", "Cloud Engineer"],
    "docker": ["DevOps Engineer", "Software Engineer"],
    "python": ["Python Developer", "Software Engineer", "Data Engineer"],
    "java": ["Java Developer", "Software Engineer"],
    "javascript": ["JavaScript Developer", "Frontend Developer"],
    "typescript": ["Frontend Developer", "Full Stack Developer"],
    "node": ["Backend Developer", "Full Stack Developer"],
    "node.js": ["Backend Developer", "Full Stack Developer"],
    "sql": ["Data Engineer", "Backend Developer"],
    "spark": ["Data Engineer", "Big Data Engineer"],
    "machine learning": ["Machine Learning Engineer", "AI Engineer"],
    "deep learning": ["Machine Learning Engineer", "Deep Learning Engineer"],
    "computer vision": ["Computer Vision Engineer", "ML Engineer"],
    "data science": ["Data Scientist", "Data Analyst"],
    "scikit-learn": ["Machine Learning Engineer", "Data Scientist"],
    "pandas": ["Data Scientist", "Data Engineer"],
    "fastapi": ["Backend Developer", "Python Developer"],
    "django": ["Backend Developer", "Python Developer"],
    "flask": ["Backend Developer", "Python Developer"],
    "rest api": ["Backend Developer", "Software Engineer"],
    "graphql": ["Backend Developer", "Full Stack Developer"],
    "react native": ["Mobile Developer", "Frontend Developer"],
    "flutter": ["Mobile Developer"],
    "terraform": ["DevOps Engineer", "Cloud Engineer"],
    "ci/cd": ["DevOps Engineer"],
    "jenkins": ["DevOps Engineer"],
    "github actions": ["DevOps Engineer"],
}


class BaseQueryStrategy(ABC):
    """Abstract base for search query construction. Keeps query logic isolated from Search Agent."""

    @abstractmethod
    def build_queries(self) -> List[QueryTuple]:
        """Return list of (source_key, location, query) for SerpAPI."""
        pass


class TitleQueryStrategy(BaseQueryStrategy):
    """User-driven intent: build queries from job title and locations (existing behavior)."""

    def __init__(
        self,
        job_title: str,
        locations: List[str],
        selected_sources: List[str],
    ) -> None:
        self._title = (job_title or "").strip() or "job"
        self._locations = [loc.strip() for loc in locations if loc and str(loc).strip()]
        self._sources = [s for s in selected_sources if s in AVAILABLE_SOURCES]

    def build_queries(self) -> List[QueryTuple]:
        result: List[QueryTuple] = []
        for loc in self._locations:
            for key in self._sources:
                pattern = AVAILABLE_SOURCES[key]["query_pattern"]
                query = pattern.format(job_title=self._title, location=loc)
                result.append((key, loc, query))
        logger.info(
            "TitleQueryStrategy: title=%s locations=%s sources=%s -> %s queries",
            self._title,
            len(self._locations),
            len(self._sources),
            len(result),
        )
        return result


def _infer_roles_from_skills(skills: List[str], max_roles: int = RESUME_MAX_ROLES) -> List[str]:
    """Deduplicate and return up to max_roles inferred job titles from skill list."""
    seen: set[str] = set()
    roles: List[str] = []
    for s in (skills or []):
        key = (s or "").strip().lower()
        if not key:
            continue
        for role in SKILL_TO_ROLE_MAP.get(key, []):
            if role not in seen:
                seen.add(role)
                roles.append(role)
                if len(roles) >= max_roles:
                    return roles
    return roles


def _build_or_query_part(terms: List[str]) -> str:
    """Build (\"A\" OR \"B\" OR \"C\") for search query."""
    if not terms:
        return ""
    escaped = [f'"{t}"' for t in terms if t and str(t).strip()]
    return "(" + " OR ".join(escaped) + ")" if escaped else ""


class ResumeQueryStrategy(BaseQueryStrategy):
    """Resume-driven: infer job roles from CV skills, generate OR-based expanded queries."""

    def __init__(
        self,
        extracted_skills: List[str],
        locations: List[str],
        optional_title: str | None = None,
        selected_sources: List[str] | None = None,
    ) -> None:
        self._skills = [s.strip() for s in extracted_skills if s and str(s).strip()]
        self._locations = [loc.strip() for loc in locations if loc and str(loc).strip()]
        self._optional_title = (optional_title or "").strip() or None
        self._sources = (
            [s for s in selected_sources if s in AVAILABLE_SOURCES]
            if selected_sources
            else list(AVAILABLE_SOURCES.keys())
        )

    def build_queries(self) -> List[QueryTuple]:
        roles = _infer_roles_from_skills(self._skills)
        # Optional title: combine with inferred roles
        if self._optional_title:
            role_terms = [self._optional_title]
            for r in roles:
                if r not in role_terms:
                    role_terms.append(r)
            role_terms = role_terms[:RESUME_MAX_ROLES]
        else:
            role_terms = roles[:RESUME_MAX_ROLES]

        if not role_terms and self._skills:
            # Fallback: use top skills as search terms
            role_terms = self._skills[:5]

        if not role_terms:
            role_terms = ["job"]

        or_part = _build_or_query_part(role_terms)
        if not or_part:
            or_part = '"job"'

        result: List[QueryTuple] = []
        # Build queries so OR clause is not double-quoted: site:linkedin.com/jobs ("A" OR "B") "Lahore"
        for loc in self._locations:
            for key in self._sources:
                if len(result) >= RESUME_MAX_QUERIES:
                    break
                pattern = AVAILABLE_SOURCES[key]["query_pattern"]
                if "{job_title}" in pattern and "{location}" in pattern:
                    site_part = pattern.split("{job_title}")[0].strip().rstrip('"').strip()
                    query = f'{site_part} {or_part} "{loc}"'
                else:
                    query = pattern.format(job_title=or_part, location=loc)
                result.append((key, loc, query))
            if len(result) >= RESUME_MAX_QUERIES:
                break

        # Optional: add one skill-based fallback query if we have room and multiple skills
        if len(result) < RESUME_MAX_QUERIES and len(self._skills) >= 2 and self._locations:
            skill_terms = self._skills[:5]
            skill_or = _build_or_query_part(skill_terms)
            if skill_or:
                loc = self._locations[0]
                key = self._sources[0] if self._sources else "linkedin_job"
                pattern = AVAILABLE_SOURCES[key]["query_pattern"]
                query = pattern.format(job_title=skill_or, location=loc)
                result.append((key, loc, query))

        result = result[:RESUME_MAX_QUERIES]
        logger.info(
            "ResumeQueryStrategy: skills=%s inferred_roles=%s -> %s queries",
            len(self._skills),
            len(roles),
            len(result),
        )
        return result
