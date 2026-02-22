"""Filter jobs by date and source. No UI logic; used by app layer."""

from typing import List, Optional

from schemas.structured_job import StructuredJob


def filter_by_source(
    jobs: List[StructuredJob],
    selected_sources: List[str],
) -> List[StructuredJob]:
    """
    Filter jobs by source. Does not mutate the input list.
    If selected_sources is empty, return all jobs.
    """
    if not selected_sources:
        return list(jobs)
    selected_set = set(selected_sources)
    return [j for j in jobs if j.source in selected_set]


def filter_by_date(
    jobs: List[StructuredJob],
    days_limit: Optional[int],
) -> List[StructuredJob]:
    """
    Filter jobs by posting date. Does not mutate the input list.
    If days_limit is None (All Time), return all jobs.
    Exclude jobs with posted_days_ago is None.
    Include jobs where posted_days_ago <= days_limit.
    """
    if days_limit is None:
        return list(jobs)
    return [
        j for j in jobs
        if j.posted_days_ago is not None and j.posted_days_ago <= days_limit
    ]
