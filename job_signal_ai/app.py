"""
AI Job Signal Detection System – Streamlit frontend.
No business logic in layout; orchestration delegated to agents and services.
"""

import asyncio
import io
from collections import Counter
from typing import List

import streamlit as st

from agents.search_agent import run_search_agent
from agents.extractor_agent import run_extractor_agent
from config import SERPAPI_KEY, OPENAI_API_KEY, MAX_RESULTS_MIN, MAX_RESULTS_MAX
from schemas.structured_job import StructuredJob


def _run_pipeline(job_title: str, location: str, max_results: int) -> List[StructuredJob]:
    """Run Search Agent then Extractor Agent; return structured jobs. Sync wrapper for Streamlit."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        raw_signals = loop.run_until_complete(
            run_search_agent(job_title=job_title, location=location, max_results=max_results)
        )
        if not raw_signals:
            return []
        jobs = loop.run_until_complete(run_extractor_agent(raw_signals))
        return jobs or []
    finally:
        loop.close()


def _skill_frequency_summary(jobs: List[StructuredJob], top_n: int = 5) -> List[tuple[str, int]]:
    """Top N skills by frequency across valid jobs."""
    skills: List[str] = []
    for j in jobs:
        if j.is_valid_job and j.skills:
            skills.extend(s.strip() for s in j.skills if s and s.strip())
    return Counter(skills).most_common(top_n)


def _export_csv(jobs: List[StructuredJob]) -> bytes:
    """Export jobs to CSV bytes."""
    import csv
    out = io.StringIO()
    writer = csv.writer(out)
    headers = [
        "title", "company", "location", "employment_type", "experience_required",
        "skills", "salary", "contact_email", "description_summary", "source", "source_url", "is_valid_job"
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
        ]
        writer.writerow(row)
    return out.getvalue().encode("utf-8")


def render_layout() -> None:
    """Streamlit page layout only; state and handlers are applied here."""
    st.set_page_config(page_title="AI Job Signal Detection System", layout="wide")
    st.title("AI Job Signal Detection System")
    st.markdown("*Search LinkedIn and Indeed job signals using AI-powered extraction.*")
    st.divider()

    # ----- Input section -----
    input_section = st.container()
    with input_section:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            job_title = st.text_input("Job Title", placeholder="e.g. AI Engineer", key="job_title")
        with col2:
            location = st.text_input("Location", placeholder="e.g. Lahore", key="location")
        with col3:
            max_results = st.slider(
                "Max results",
                min_value=MAX_RESULTS_MIN,
                max_value=MAX_RESULTS_MAX,
                value=25,
                key="max_results",
            )
        search_clicked = st.button("Search", type="primary", key="search_btn")

    # Session state init
    if "jobs" not in st.session_state:
        st.session_state["jobs"] = []
    if "error" not in st.session_state:
        st.session_state["error"] = None
    if "show_invalid" not in st.session_state:
        st.session_state["show_invalid"] = False

    # ----- Handle search (business logic in pipeline, not in layout) -----
    if search_clicked:
        if not job_title or not job_title.strip():
            st.session_state["error"] = "Please enter a job title."
            st.session_state["jobs"] = []
        elif not SERPAPI_KEY:
            st.session_state["error"] = "SERPAPI_KEY is not set. Add it to your .env file."
            st.session_state["jobs"] = []
        elif not OPENAI_API_KEY:
            st.session_state["error"] = "OPENAI_API_KEY is not set. Add it to your .env file."
            st.session_state["jobs"] = []
        else:
            st.session_state["error"] = None
            with st.spinner("Searching job signals and extracting structured data…"):
                try:
                    jobs = _run_pipeline(
                        job_title=job_title.strip(),
                        location=(location or "").strip(),
                        max_results=max_results,
                    )
                    st.session_state["jobs"] = jobs
                except Exception as e:
                    st.session_state["error"] = f"Search failed: {str(e)}"
                    st.session_state["jobs"] = []

    # ----- Error message -----
    if st.session_state.get("error"):
        st.error(st.session_state["error"])

    # ----- Results section -----
    jobs: List[StructuredJob] = st.session_state.get("jobs") or []
    valid_jobs = [j for j in jobs if j.is_valid_job]
    invalid_jobs = [j for j in jobs if not j.is_valid_job]

    st.divider()
    st.subheader("Results")

    if not jobs:
        if not search_clicked and not st.session_state.get("error"):
            st.info("Enter a job title and location, then click **Search** to find job signals.")
        elif search_clicked and not st.session_state.get("error"):
            st.warning("No job signals found. Try different keywords or location.")
        return

    # Summary row
    st.markdown(f"**Total signals processed:** {len(jobs)} · **Valid jobs:** {len(valid_jobs)}")
    show_invalid = st.checkbox(
        "Show invalid / non-job results",
        value=st.session_state["show_invalid"],
        key="show_invalid_cb",
    )
    st.session_state["show_invalid"] = show_invalid

    # Top 5 skills
    skill_summary = _skill_frequency_summary(valid_jobs, 5)
    if skill_summary:
        with st.expander("Top 5 skills (frequency)"):
            for skill, count in skill_summary:
                st.markdown(f"- **{skill}** ({count})")

    # Export CSV
    buf = _export_csv(valid_jobs if not show_invalid else jobs)
    st.download_button(
        "Export to CSV",
        data=buf,
        file_name="job_signals.csv",
        mime="text/csv",
        key="export_csv",
    )

    # Job cards: show valid always; add invalid if toggle on
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
                st.caption(f"**Source:** {job.source}")
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
