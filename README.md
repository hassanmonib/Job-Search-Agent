# AI Job Signal Detection System

Production-ready AI system that discovers job signals from **public** LinkedIn and Indeed content via search, then extracts structured job data using an LLM. No Selenium, Playwright, or scraping behind authentication.

## Architecture

- **Search Agent**: Builds Google queries (LinkedIn posts, LinkedIn jobs, Indeed), calls SerpAPI, deduplicates and returns up to 25 raw job signals.
- **Extractor Agent**: Fetches public HTML asynchronously, cleans text, sends to LLM for structured extraction, validates schema, deduplicates.

Flow: **User Input (Streamlit) → Search Agent → Raw Job Signals → Extractor Agent → Structured Jobs → Display in Streamlit.**

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
   - `OPENAI_API_KEY` – OpenAI API key
   - `MODEL_NAME` – optional, default `gpt-4o-mini`

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

1. Enter **Job Title** (e.g. *AI Engineer*) and **Location** (e.g. *Lahore*).
2. Set **Max results** (5–30).
3. Click **Search**. The app runs the Search Agent then the Extractor Agent and shows structured job cards.
4. Use **Show invalid / non-job results** to include rejected posts.
5. Use **Export to CSV** to download results. **Top 5 skills** shows skill frequency across valid jobs.

## Project Structure

```
job_signal_ai/
├── agents/           # Search Agent, Extractor Agent
├── services/         # SerpAPI, page fetcher, text cleaner
├── schemas/          # RawJobSignal, StructuredJob
├── utils/            # Logger, helpers (dedup, email extraction)
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

- Ranking Agent, CV similarity, embeddings
- Daily job alerts, PostgreSQL storage
- Skill trend analytics, multi-country search
