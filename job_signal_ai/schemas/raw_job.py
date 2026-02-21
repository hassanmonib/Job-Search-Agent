"""Raw job signal schema from search results."""

from pydantic import BaseModel, Field


class RawJobSignal(BaseModel):
    """Unstructured job signal from search engine results."""

    source: str = Field(..., description="Source name (e.g. LinkedIn, Indeed)")
    url: str = Field(..., description="URL of the job post or page")
    title_snippet: str = Field(default="", description="Title or headline snippet from search")
    description_snippet: str = Field(default="", description="Description snippet from search result")
