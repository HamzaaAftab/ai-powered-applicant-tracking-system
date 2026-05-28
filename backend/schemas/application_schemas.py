from pydantic import BaseModel, EmailStr, HttpUrl, Field
from typing import Optional, List
from datetime import datetime
from uuid import UUID


# ─── Request Schema (What API receives from Candidate) ────────────────────────

class ApplicationSubmitRequest(BaseModel):
    """
    Candidate fills this form on the public /apply/[slug] page.
    
    Note: CV file comes as multipart form-data (UploadFile).
    This schema handles text fields only.
    
    Why EmailStr? Pydantic automatically validates email format.
    "notanemail" will fail validation → 422 error returned automatically.
    """
    candidate_name: str = Field(..., min_length=2, max_length=255)
    candidate_email: EmailStr                            # auto-validated
    candidate_phone: Optional[str] = Field(None, max_length=20)
    experience_years: Optional[int] = Field(None, ge=0, le=60)  # 0-60 years
    linkedin_url: Optional[str] = Field(None, max_length=500)
    portfolio_url: Optional[str] = Field(None, max_length=500)
    cover_letter: Optional[str] = None

    class Config:
        json_schema_extra = {
            "example": {
                "candidate_name": "Ahmed Ali",
                "candidate_email": "ahmed@example.com",
                "candidate_phone": "+92-300-1234567",
                "experience_years": 3,
                "linkedin_url": "https://linkedin.com/in/ahmedali",
                "cover_letter": "I am excited to apply for this position..."
            }
        }


# ─── Response Schemas (What API returns) ──────────────────────────────────────

class ApplicationSubmittedResponse(BaseModel):
    """Returned immediately after candidate submits — before LLM scoring."""
    id: UUID
    candidate_name: str
    status: str               # Will be "pending" at this point
    message: str = "Application submitted successfully! We will review it shortly."


class ApplicationRankedItem(BaseModel):
    """
    One row in the HR ranking table (Tab 2).
    Contains just enough info to display in the table.
    """
    id: UUID
    rank: Optional[int]
    candidate_name: str
    candidate_email: str
    experience_years: Optional[int]
    llm_score: Optional[float]
    status: str
    submitted_at: datetime
    cv_url: Optional[str]         # HR can download from this

    class Config:
        from_attributes = True


class ApplicationDetailResponse(BaseModel):
    """
    Full candidate details — shown when HR clicks "View" on a candidate.
    Includes LLM analysis breakdown.
    """
    id: UUID
    rank: Optional[int]
    candidate_name: str
    candidate_email: str
    candidate_phone: Optional[str]
    experience_years: Optional[int]
    linkedin_url: Optional[str]
    portfolio_url: Optional[str]
    cover_letter: Optional[str]
    cv_url: Optional[str]
    llm_score: Optional[float]
    llm_reasoning: Optional[str]
    llm_strengths: Optional[List[str]]
    llm_weaknesses: Optional[List[str]]
    status: str
    submitted_at: datetime

    class Config:
        from_attributes = True
