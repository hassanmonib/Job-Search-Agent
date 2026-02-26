# AI Career Intelligence System

Production-ready AI system that discovers job signals from **public** LinkedIn, Indeed and Glassdoor content via search, extracts structured job data using an LLM, and supports **personalized job ranking** using CV embeddings and vector similarity.

## Architecture

- **Search Agent**: Builds Google queries (LinkedIn posts, LinkedIn jobs, Indeed), calls SerpAPI, deduplicates and returns raw job signals.
- **Extractor Agent**: Fetches public HTML asynchronously, cleans text, sends to LLM for structured extraction, validates schema, deduplicates.
- **CV Pipeline**: Optional upload of PDF/DOCX CVs; text extraction and LLM-based extraction of skills, experience, domain, tools.
- **Embedding layer**: SentenceTransformers (e.g. all-MiniLM-L6-v2) or OpenAI embeddings (config toggle).
- **Ranking**: FAISS vector index over job embeddings; personalized score (embedding similarity + location + recency + skill overlap) and skill gap detection.

Flow: **User Input → Search Agent → Extractor Agent → Structured Jobs → (optional) CV Upload → Embed & Rank → Results with match scores and skill gaps.**

## Setup

**Clone the repo:**
```bash
git clone https://github.com/YOUR_USERNAME/Job-Search-Agent.git
cd Job-Search-Agent
```

1. **Python 3.11+**

2. **Use a virtual environment** (recommended, avoids pydantic/OpenAI version conflicts):
   ```bash
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   # source .venv/bin/activate     # macOS/Linux
   pip install -r requirements.txt
   ```

3. **Environment variables**  
   Copy `.env.example` to `.env` in the project root (or inside `job_signal_ai/`) and set:
   - `SERPAPI_KEY` – [SerpAPI](https://serpapi.com/)
   - `OPENAI_API_KEY` – OpenAI API key (for extraction and optional OpenAI embeddings)
   - `MODEL_NAME` – optional, default `gpt-4o-mini`
   - `EMBEDDING_PROVIDER` – optional, `sentence_transformers` (default) or `openai`
   - `SENTENCE_TRANSFORMERS_MODEL` – optional, default `all-MiniLM-L6-v2`
   - `OPENAI_EMBEDDING_MODEL` – optional when using OpenAI embeddings, default `text-embedding-3-small`

## Run

From the **project root**:

```bash
cd job_signal_ai
streamlit run app.py
```

Or from project root with module run:

```bash
python -m streamlit run job_signal_ai/app.py
```
(Requires project root on `PYTHONPATH` or installing the package.)

## Usage

1. **(Optional)** Upload your **CV** (PDF or DOCX) for personalized ranking and skill gap detection.
2. Enter **Job Title** (e.g. *AI Engineer*) and **Location** (e.g. *Lahore*).
3. Set **Max results** (5–30) and click **Search**. The app runs the Search Agent then the Extractor Agent.
4. If a CV was uploaded, results are **ranked by match score** and each card shows **Match Score %** and **Missing skills**.
5. Use **Show invalid / non-job results**, **Export to CSV**, and **Top 5 skills** / **Recommended skills to learn** as needed.

## Personalized AI Matching

When you upload a CV, the system:

- **CV embeddings**: Extracts text from your CV (PDF/DOCX), then uses an LLM to structure it into skills, experience, domain, and tools. A summary of this profile is embedded (SentenceTransformers or OpenAI, depending on config).
- **Vector similarity**: Job descriptions are embedded with the same model. Similarity between your CV summary and each job is computed via **cosine similarity** in embedding space.
- **FAISS indexing**: A FAISS index (IndexFlatIP over L2-normalized vectors) is built from the current job set. The index is **rebuilt only when new jobs are fetched**, and the embedding model is cached with `@st.cache_resource` for performance.
- **Final score**: Each job gets a combined score: **0.7 × embedding similarity + 0.1 × location match + 0.1 × recency + 0.1 × skill overlap**. Jobs are sorted by this score.
- **Skill gap detection**: For the top 10 ranked jobs, required skills are compared with your CV skills. **Missing skills** are shown per job card, and **Recommended skills to learn** are listed in an expander.

## Project Structure

```
job_signal_ai/
├── agents/           # Search Agent, Extractor Agent
├── services/         # SerpAPI, page fetcher, text cleaner
├── schemas/          # RawJobSignal, StructuredJob, CVProfile
├── utils/            # Logger, helpers (dedup, email extraction)
├── embeddings/       # Embedding service (SentenceTransformers / OpenAI)
├── ranking/          # FAISS vector index, personalized ranker, skill gap
├── cv_pipeline/      # CV text extraction (PDF/DOCX), LLM profile extraction
├── config.py
├── app.py            # Streamlit UI
├── requirements.txt
└── .env.example
```

## Troubleshooting

**`ImportError: cannot import name 'validate_core_schema' from 'pydantic_core'`**  
This is a version mismatch between `pydantic` and `pydantic_core`. Fix it by using a **virtual environment** (see Setup step 2) and installing deps there. If you must use the global Python:
```bash
pip install --upgrade pydantic pydantic_core openai
```
If you get permission errors, use a venv or run your terminal as Administrator.

## Future Extensibility

The design allows adding:

- Daily job alerts, PostgreSQL storage
- Skill trend analytics, multi-country search
- Stored CV profiles and job history
