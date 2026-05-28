from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Optional, List
import uuid

from db.database import get_db
from models.hr_jobs import HrJob
from models.job_applications import JobApplication
from schemas.application_schemas import (
    ApplicationSubmittedResponse,
    ApplicationRankedItem,
    ApplicationDetailResponse,
)
from services.storage import StorageService
from core.config import settings
from worker.tasks import process_new_application

router = APIRouter(prefix="/applications", tags=["applications"])


# ─── POST /applications/submit ────────────────────────────────────────────────
@router.post("/submit", response_model=ApplicationSubmittedResponse, status_code=201)
async def submit_application(
    # The job slug comes from the URL params — we pass it as a form field
    # (since this is multipart/form-data for file upload)
    background_tasks: BackgroundTasks,
    job_slug: str = Form(...),
    candidate_name: str = Form(...),
    candidate_email: str = Form(...),
    candidate_phone: Optional[str] = Form(None),
    experience_years: Optional[int] = Form(None),
    linkedin_url: Optional[str] = Form(None),
    portfolio_url: Optional[str] = Form(None),
    cover_letter: Optional[str] = Form(None),
    cv_file: UploadFile = File(...),               # CV is required
    db: Session = Depends(get_db),
):
    """
    Candidate submits their application.
    
    Steps:
    1. Validate job exists and is active
    2. Upload CV to Supabase Storage
    3. Save application to DB with status="pending"
    4. [Future] Trigger background LLM scoring worker
    5. Return confirmation
    
    Note: LLM scoring happens ASYNCHRONOUSLY.
    We don't make the candidate wait 10-30 seconds for AI to score them.
    Response is immediate; scoring happens in background.
    """

    # Step 1: Validate the job exists and is open
    job = db.query(HrJob).filter(HrJob.unique_slug == job_slug).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{job_slug}' not found.")

    if job.status == "closed":
        raise HTTPException(
            status_code=410,
            detail="This position is no longer accepting applications."
        )

    # Step 2: Create application ID first (needed for storage path)
    application_id = uuid.uuid4()

    # Step 3: Upload CV to Supabase Storage
    cv_path = await StorageService.upload_cv(cv_file, str(job.id), str(application_id))

    # Step 4: Save to DB
    application = JobApplication(
        id=application_id,
        job_id=job.id,
        candidate_name=candidate_name,
        candidate_email=candidate_email,
        candidate_phone=candidate_phone,
        experience_years=experience_years,
        linkedin_url=linkedin_url,
        portfolio_url=portfolio_url,
        cover_letter=cover_letter,
        cv_url=cv_path,
        cv_extracted=None,      # Worker will fill this
        llm_score=None,         # Worker will fill this
        llm_reasoning=None,     # Worker will fill this
        llm_strengths=None,     # Worker will fill this
        llm_weaknesses=None,    # Worker will fill this
        rank=None,              # Worker will compute this
        status="pending",
    )

    db.add(application)
    db.commit()
    db.refresh(application)

    # Step 5: Trigger background worker for LLM scoring
    background_tasks.add_task(process_new_application, str(application.id))

    return ApplicationSubmittedResponse(
        id=application.id,
        candidate_name=application.candidate_name,
        status=application.status,
    )


# ─── GET /applications/job/{job_id} ───────────────────────────────────────────
@router.get("/job/{job_id}", response_model=List[ApplicationRankedItem])
def get_applications_for_job(job_id: str, db: Session = Depends(get_db)):
    """
    Returns all candidates for a specific job, ranked by LLM score.
    
    Used in HR's Tab 2 (History) when they click on a job.
    
    Ordering logic:
    - Scored candidates first (rank ASC = best first)
    - Unscored candidates last (rank is NULL → sorted by submission time)
    
    Why this ordering? 
    → HR should see best candidates immediately
    → Recently submitted (unscored yet) go to bottom
    """
    # Verify job exists
    job = db.query(HrJob).filter(HrJob.id == job_id).first()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    # Fetch all applications, ranked candidates first
    applications = (
        db.query(JobApplication)
        .filter(JobApplication.job_id == job_id)
        .order_by(
            JobApplication.rank.asc().nullslast(),  # ranked first, nulls last
            JobApplication.submitted_at.desc(),     # then by newest submission
        )
        .all()
    )

    # Build response — include signed CV download URL if available
    result = []
    for app in applications:
        cv_download_url = None
        if app.cv_url:
            # Generate a 1-hour signed URL for CV download
            cv_download_url = StorageService.get_signed_url(
                bucket=settings.BUCKET_CV,
                path=app.cv_url,
                expires_in_seconds=3600,
            )

        result.append(ApplicationRankedItem(
            id=app.id,
            rank=app.rank,
            candidate_name=app.candidate_name,
            candidate_email=app.candidate_email,
            experience_years=app.experience_years,
            llm_score=app.llm_score,
            status=app.status,
            submitted_at=app.submitted_at,
            cv_url=cv_download_url,  # Signed URL, not raw storage path
        ))

    return result


# ─── GET /applications/{app_id} ───────────────────────────────────────────────
@router.get("/{app_id}", response_model=ApplicationDetailResponse)
def get_application_detail(app_id: str, db: Session = Depends(get_db)):
    """
    Full candidate detail — shown in the expanded "View" panel in HR dashboard.
    Includes LLM reasoning, strengths, weaknesses.
    """
    app = db.query(JobApplication).filter(JobApplication.id == app_id).first()

    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")

    # Generate fresh signed URL for CV
    cv_download_url = None
    if app.cv_url:
        cv_download_url = StorageService.get_signed_url(
            bucket=settings.BUCKET_CV,
            path=app.cv_url,
        )

    return ApplicationDetailResponse(
        id=app.id,
        rank=app.rank,
        candidate_name=app.candidate_name,
        candidate_email=app.candidate_email,
        candidate_phone=app.candidate_phone,
        experience_years=app.experience_years,
        linkedin_url=app.linkedin_url,
        portfolio_url=app.portfolio_url,
        cover_letter=app.cover_letter,
        cv_url=cv_download_url,
        llm_score=app.llm_score,
        llm_reasoning=app.llm_reasoning,
        llm_strengths=app.llm_strengths,
        llm_weaknesses=app.llm_weaknesses,
        status=app.status,
        submitted_at=app.submitted_at,
    )


# ─── PATCH /applications/{app_id}/status ─────────────────────────────────────
@router.patch("/{app_id}/status")
def update_application_status(
    app_id: str,
    new_status: str = Form(...),  # "shortlisted" or "rejected" or "reviewed"
    db: Session = Depends(get_db),
):
    """HR manually updates candidate status after reviewing."""
    allowed_statuses = {"pending", "scored", "reviewed", "shortlisted", "rejected"}

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid status. Must be one of: {', '.join(allowed_statuses)}"
        )

    app = db.query(JobApplication).filter(JobApplication.id == app_id).first()
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")

    app.status = new_status
    db.commit()

    return {"message": f"Status updated to '{new_status}'", "application_id": app_id}
