from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from uuid import UUID


# ─── Request Schemas (What API receives) ─────────────────────────────────────

class JobCreateRequest(BaseModel):
    """
    What HR sends when creating a job.
    
    Note: PDF/Image files come as form-data (multipart), NOT in this JSON schema.
    This schema handles only the text fields.
    FastAPI handles files separately via UploadFile.
    """
    title: str = Field(..., min_length=3, max_length=255, description="Job title")
    description: Optional[str] = Field(None, description="Typed job description text")

    class Config:
        # Allow examples in OpenAPI docs
        json_schema_extra = {
            "example": {
                "title": "Senior Backend Engineer",
                "description": "We are looking for a Python developer with 3+ years experience..."
            }
        }


# ─── Response Schemas (What API returns) ──────────────────────────────────────

class JobCreatedResponse(BaseModel):
    """
    Returned after successfully creating a job.
    HR uses this to get the shareable link.
    """
    id: UUID
    unique_slug: str           # e.g. "JOB-A3F9K2"
    title: str
    status: str
    created_at: datetime
    apply_url: str             # Full candidate URL: "/apply/JOB-A3F9K2"

    class Config:
        from_attributes = True  # Allows converting SQLAlchemy model → this schema


class JobSummary(BaseModel):
    """
    Lightweight job info — used in HR's history tab list.
    Doesn't include full JD text (saves bandwidth).
    """
    id: UUID
    unique_slug: str
    title: str
    status: str
    created_at: datetime
    application_count: int = 0  # How many candidates applied

    class Config:
        from_attributes = True


class JobDetailResponse(BaseModel):
    """
    Full job details — used on the public candidate form page.
    Only shows what a candidate needs to see.
    """
    unique_slug: str
    title: str
    description: Optional[str]
    jd_extracted: Optional[str]
    status: str

    class Config:
        from_attributes = True
