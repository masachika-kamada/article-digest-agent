from pydantic import BaseModel, Field


class ArticleDocument(BaseModel):
    url: str
    title: str
    author: str | None = None
    published_at: str | None = None
    content: str
    truncated: bool = False
    character_count: int = Field(ge=0)
