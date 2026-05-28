import uuid
from sqlalchemy import Column, String, Text, Float, Integer, DateTime, ForeignKey, func, ARRAY
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from db.database import Base


class JobApplication(Base):
    """
    Represents a Candidate's job application.
    
    Table name: job_applications
    
    Relationship to hr_jobs:
    - One HrJob can have MANY JobApplications (One-to-Many)
    - job_id is the ForeignKey linking them together
    
    LLM Scoring fields:
    - llm_score: 0.0 to 100.0 float
    - llm_reasoning: paragraph explaining the score
    - llm_strengths: array of bullet points (PostgreSQL ARRAY)
    - llm_weaknesses: array of bullet points
    - rank: computed ranking (1 = best) among all applicants for the job
    
    These are nullable because scoring happens AFTER submission (async worker)
    So at submit time: score=None, rank=None
    After worker runs: score=87.5, rank=2
    """

    __tablename__ = "job_applications"

    # Primary Key
    id = Column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
        index=True,
    )

    # Foreign Key → links to hr_jobs.id
    # ondelete="CASCADE" → if a job is deleted, all its applications are auto-deleted
    job_id = Column(
        UUID(as_uuid=True),
        ForeignKey("hr_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,    # index because we filter by job_id very often
    )

    # Candidate Information (from the public form)
    candidate_name = Column(String(255), nullable=False)
    candidate_email = Column(String(255), nullable=False)
    candidate_phone = Column(String(20), nullable=True)
    experience_years = Column(Integer, nullable=True)
    linkedin_url = Column(String(500), nullable=True)
    portfolio_url = Column(String(500), nullable=True)
    cover_letter = Column(Text, nullable=True)

    # CV file stored in Supabase Storage
    cv_url = Column(String(500), nullable=True)

    # Text extracted from CV PDF (what LLM reads)
    cv_extracted = Column(Text, nullable=True)

    # ── LLM Scoring Results ──────────────────────────────────────────────────
    # All nullable because worker fills them AFTER submission
    llm_score = Column(Float, nullable=True)          # e.g. 87.5
    llm_reasoning = Column(Text, nullable=True)        # paragraph
    llm_strengths = Column(ARRAY(Text), nullable=True) # ["strong Python skills", ...]
    llm_weaknesses = Column(ARRAY(Text), nullable=True)

    # Rank among all applicants for this job (1 = highest score)
    # Recomputed every time a new application comes in
    rank = Column(Integer, nullable=True)

    # Application lifecycle status
    # pending → (worker runs) → scored → (HR reviews) → shortlisted / rejected
    status = Column(String(20), nullable=False, default="pending")

    # Timestamps
    submitted_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # ── ORM Relationship ─────────────────────────────────────────────────────
    # This lets us do: application.job → get the HrJob object
    # back_populates connects both sides of the relationship
    job = relationship("HrJob", back_populates="applications")
