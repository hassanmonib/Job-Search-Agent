"""
AI Job Signal Detection System – Streamlit frontend.
No business logic in layout; orchestration and filtering in services.
"""

import asyncio
import io
import csv
from collections import Counter
from typing import List

import streamlit as st

from agents.search_agent import run_search_agent
from agents.extractor_agent import run_extractor_agent
from config import (
    SERPAPI_KEY,
    OPENAI_API_KEY,
    MAX_RESULTS_MIN,
    MAX_RESULTS_MAX,
    AVAILABLE_SOURCES,
    AVAILABLE_LOCATIONS,
)
from schemas.structured_job import StructuredJob
from services.filter_service import filter_by_date, filter_by_source

# Posting date filter options (job board standard)
DATE_FILTER_MAP = {
    "All Time": None,
    "Last 24 Hours": 1,
    "Last 3 Days": 3,
    "Last 7 Days": 7,
    "Last 14 Days": 14,
    "Last 30 Days": 30,
    "Last 90 Days": 90,
}
DATE_FILTER_OPTIONS = list(DATE_FILTER_MAP.keys())

# Source labels from centralized config (for post-filter and cards)
SOURCE_DISPLAY = {k: v["label"] for k, v in AVAILABLE_SOURCES.items()}
# Pre-search options: "All" (UI convenience) + every source key; "All" never passed to Search Agent
ALL_SOURCES_KEY = "All"
PRE_SEARCH_SOURCE_OPTIONS = [ALL_SOURCES_KEY] + list(AVAILABLE_SOURCES.keys())
PRE_SEARCH_SOURCE_DEFAULT = [ALL_SOURCES_KEY]


def _effective_sources_for_search(selected: List[str]) -> List[str]:
    """Compute sources to pass to Search Agent. 'All' means every AVAILABLE_SOURCES key."""
    if not selected:
        return []
    if ALL_SOURCES_KEY in selected:
        return list(AVAILABLE_SOURCES.keys())
    return [s for s in selected if s in AVAILABLE_SOURCES]


def _run_pipeline(
    job_title: str,
    locations: List[str],
    max_results: int,
    selected_sources: List[str],
) -> List[StructuredJob]:
    """Run Search Agent (per location × source) then Extractor Agent; return structured jobs."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw_signals = loop.run_until_complete(
            run_search_agent(
                job_title=job_title,
                locations=locations,
                max_results=max_results,
                selected_sources=selected_sources,
            )
        )
        if not raw_signals:
            return []
        jobs = loop.run_until_complete(run_extractor_agent(raw_signals))
        return jobs or []
    finally:
        loop.close()


def _skill_frequency_summary(jobs: List[StructuredJob], top_n: int = 5) -> List[tuple]:
    """Top N skills by frequency across valid jobs."""
    skills = []
    for j in jobs:
        if j.is_valid_job and j.skills:
            skills.extend(s.strip() for s in j.skills if s and str(s).strip())
    return Counter(skills).most_common(top_n)


def _export_csv(jobs: List[StructuredJob]) -> bytes:
    """Export jobs to CSV bytes."""
    out = io.StringIO()
    writer = csv.writer(out)
    headers = [
        "title", "company", "location", "employment_type", "experience_required",
        "skills", "salary", "contact_email", "description_summary", "source", "source_url",
        "is_valid_job", "posted_date", "posted_days_ago", "searched_location",
    ]
    writer.writerow(headers)
    for j in jobs:
        row = [
            j.title or "",
            j.company or "",
            j.location or "",
            j.employment_type or "",
            j.experience_required or "",
            "; ".join(j.skills) if j.skills else "",
            j.salary or "",
            j.contact_email or "",
            (j.description_summary or "")[:500],
            j.source or "",
            j.source_url or "",
            j.is_valid_job,
            str(j.posted_date) if j.posted_date else "",
            j.posted_days_ago if j.posted_days_ago is not None else "",
            j.searched_location or "",
        ]
        writer.writerow(row)
    return out.getvalue().encode("utf-8")


def _source_display_label(key: str) -> str:
    """Label for source in multiselect (from centralized config). 'All' is UI-only."""
    if key == ALL_SOURCES_KEY:
        return "All"
    return SOURCE_DISPLAY.get(key, key.replace("_", " ").title())


def render_layout() -> None:
    """Streamlit page layout; filters and display use services layer."""
    st.set_page_config(page_title="AI Job Signal Detection System", layout="wide")
    st.title("AI Job Signal Detection System")
    st.markdown("*Search LinkedIn and Indeed job signals using AI-powered extraction.*")
    st.divider()

    # ----- Pre-search: source selection (controls which sources are queried) -----
    st.subheader("Select Job Sources")
    selected_sources_pre = st.multiselect(
        "Select Job Sources",
        options=PRE_SEARCH_SOURCE_OPTIONS,
        default=PRE_SEARCH_SOURCE_DEFAULT,
        format_func=_source_display_label,
        key="pre_search_sources",
        help="Choose All to search every source, or pick specific sources. Change before clicking Search.",
    )
    effective_sources = _effective_sources_for_search(selected_sources_pre)

    # ----- Locations (multi-city) -----
    locations_selected = st.multiselect(
        "Select Locations",
        options=AVAILABLE_LOCATIONS,
        default=["Lahore"],
        key="locations",
        help="Search in all selected cities. At least one required.",
    )

    # ----- Input section -----
    with st.container():
        col1, col2 = st.columns([3, 1])
        with col1:
            job_title = st.text_input("Job Title", placeholder="e.g. AI Engineer", key="job_title")
        with col2:
            max_results = st.slider(
                "Max results",
                min_value=MAX_RESULTS_MIN,
                max_value=MAX_RESULTS_MAX,
                value=25,
                key="max_results",
            )
        search_clicked = st.button("Search", type="primary", key="search_btn")

    # Session state: original_jobs (immutable after search), error
    if "original_jobs" not in st.session_state:
        st.session_state["original_jobs"] = []
    if "error" not in st.session_state:
        st.session_state["error"] = None
    if "show_invalid" not in st.session_state:
        st.session_state["show_invalid"] = False
    if "searched_locations" not in st.session_state:
        st.session_state["searched_locations"] = []

    # ----- Run search (only on button click) -----
    if search_clicked:
        if not job_title or not job_title.strip():
            st.session_state["error"] = "Please enter a job title."
            st.session_state["original_jobs"] = []
        elif not locations_selected:
            st.session_state["error"] = "Please select at least one location."
            st.session_state["original_jobs"] = []
        elif not effective_sources:
            st.session_state["error"] = "Select at least one job source (e.g. All, or specific sources) before searching."
            st.session_state["original_jobs"] = []
        elif not SERPAPI_KEY:
            st.session_state["error"] = "SERPAPI_KEY is not set. Add it to your .env file."
            st.session_state["original_jobs"] = []
        elif not OPENAI_API_KEY:
            st.session_state["error"] = "OPENAI_API_KEY is not set. Add it to your .env file."
            st.session_state["original_jobs"] = []
        else:
            st.session_state["error"] = None
            with st.spinner("Searching job signals and extracting structured data…"):
                try:
                    jobs = _run_pipeline(
                        job_title=job_title.strip(),
                        locations=locations_selected,
                        max_results=max_results,
                        selected_sources=effective_sources,
                    )
                    st.session_state["original_jobs"] = jobs
                    st.session_state["searched_locations"] = locations_selected
                except Exception as e:
                    st.session_state["error"] = f"Search failed: {str(e)}"
                    st.session_state["original_jobs"] = []

    if st.session_state.get("error"):
        st.error(st.session_state["error"])

    original_jobs: List[StructuredJob] = st.session_state.get("original_jobs") or []

    # ----- Filter section: always visible so users see the updated UI -----
    st.subheader("Filters")
    with st.container():
        fcol1, fcol2 = st.columns(2)
        with fcol1:
            date_filter_label = st.selectbox(
                "Posting Date Filter",
                options=DATE_FILTER_OPTIONS,
                index=0,
                key="date_filter",
            )
            days_limit = DATE_FILTER_MAP[date_filter_label]
        with fcol2:
            available_sources = sorted(set(j.source for j in original_jobs))
            if available_sources:
                selected_sources = st.multiselect(
                    "Filter by Source",
                    options=available_sources,
                    default=available_sources,
                    format_func=_source_display_label,
                    key="source_filter",
                )
            else:
                st.multiselect(
                    "Filter by Source",
                    options=[],
                    default=[],
                    key="source_filter",
                    help="Run a search to see sources (LinkedIn, Indeed, etc.).",
                )
                selected_sources = []

    # Apply pipeline only when we have jobs (no mutation of original_jobs)
    if original_jobs:
        filtered_jobs = filter_by_source(original_jobs, selected_sources)
        filtered_jobs = filter_by_date(filtered_jobs, days_limit)
    else:
        filtered_jobs = []

    st.divider()

    # ----- Results section (based on filtered_jobs) -----
    st.subheader("Results")
    valid_jobs = [j for j in filtered_jobs if j.is_valid_job]
    invalid_jobs = [j for j in filtered_jobs if not j.is_valid_job]

    if not original_jobs:
        if not search_clicked and not st.session_state.get("error"):
            st.info("Enter a job title, select at least one location, then click **Search** to find job signals.")
        elif search_clicked and not st.session_state.get("error"):
            st.warning("No job signals found. Try different keywords or locations.")
    else:
        searched_locations = st.session_state.get("searched_locations") or []
        if searched_locations:
            st.markdown(f"**Searched in:** {', '.join(searched_locations)}")
        st.markdown(f"**Total (filtered):** {len(filtered_jobs)} · **Valid jobs:** {len(valid_jobs)}")
        show_invalid = st.checkbox(
            "Show invalid / non-job results",
            value=st.session_state["show_invalid"],
            key="show_invalid_cb",
        )
        st.session_state["show_invalid"] = show_invalid

        skill_summary = _skill_frequency_summary(valid_jobs, 5)
        if skill_summary:
            with st.expander("Top 5 skills (frequency)"):
                for skill, count in skill_summary:
                    st.markdown(f"- **{skill}** ({count})")

        buf = _export_csv(valid_jobs if not show_invalid else filtered_jobs)
        st.download_button(
            "Export to CSV",
            data=buf,
            file_name="job_signals.csv",
            mime="text/csv",
            key="export_csv",
        )

        to_show = valid_jobs + (invalid_jobs if show_invalid else [])

        for job in to_show:
            with st.container():
                st.markdown("---")
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.markdown(f"### {job.title or 'Untitled'}")
                    st.caption(f"**Company:** {job.company or '—'} · **Location:** {job.location or '—'}")
                    if job.employment_type or job.experience_required:
                        st.caption(f"*{job.employment_type or ''} {job.experience_required or ''}*".strip())
                    if job.skills:
                        badges = " ".join(f"`{s}`" for s in job.skills[:12] if s and str(s).strip())
                        if badges:
                            st.markdown(badges)
                    st.caption(f"**Source:** {_source_display_label(job.source)}")
                    if job.searched_location:
                        st.caption(f"**Matched location:** {job.searched_location}")
                    if job.posted_days_ago is not None:
                        st.caption(f"Posted {job.posted_days_ago} days ago")
                with col_b:
                    st.link_button("Open Job", url=job.source_url, type="secondary")
                    if not job.is_valid_job:
                        st.caption("⚠️ Invalid/non-job")
                if job.description_summary:
                    with st.expander("Description"):
                        st.markdown(job.description_summary)
                if job.salary:
                    st.caption(f"Salary: {job.salary}")
                if job.contact_email:
                    st.caption(f"Contact: {job.contact_email}")


if __name__ == "__main__":
    render_layout()
