from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Optional, List
import uuid

from db.database import get_db
from models.hr_jobs import HrJob
from models.job_applications import JobApplication
from schemas.job_schemas import JobCreatedResponse, JobSummary, JobDetailResponse
from services.storage import StorageService
from services.slug import generate_unique_slug
from core.config import settings

# APIRouter = a group of related routes
# prefix="/jobs" → all routes here start with /jobs
# tags=["jobs"] → groups them in the OpenAPI docs UI (Swagger)
router = APIRouter(prefix="/jobs", tags=["jobs"])


# ─── POST /jobs/create ────────────────────────────────────────────────────────
@router.post("/create", response_model=JobCreatedResponse, status_code=201)
async def create_job(
    title: str = Form(...),                          # Required text field
    description: Optional[str] = Form(None),         # Optional text
    jd_pdf: Optional[UploadFile] = File(None),       # Optional file upload
    jd_image: Optional[UploadFile] = File(None),     # Optional file upload
    db: Session = Depends(get_db),                   # DB session injected
):
    """
    Creates a new job posting and returns a shareable candidate link.
    
    Why Form(...) and not a Pydantic body?
    → When uploading FILES, HTTP requires "multipart/form-data" content-type.
    → You CANNOT send JSON + files in the same request.
    → So text fields also come as Form() fields in the same multipart request.
    
    Why is this async?
    → File reading (await file.read()) is I/O bound.
    → async lets FastAPI handle other requests while waiting for file I/O.
    """

    # 1. Generate unique slug FIRST (we need it for storage path)
    unique_slug = generate_unique_slug(db)

    # 2. Create a temporary UUID for the job (used in storage paths)
    job_id = uuid.uuid4()

    # 3. Handle file uploads
    jd_pdf_path = None
    jd_image_path = None

    if jd_pdf and jd_pdf.filename:
        # Upload PDF to Supabase Storage
        jd_pdf_path = await StorageService.upload_jd_file(jd_pdf, str(job_id))

    if jd_image and jd_image.filename:
        # Upload image to Supabase Storage
        jd_image_path = await StorageService.upload_jd_file(jd_image, str(job_id))

    # 4. Validate: at least one of description, pdf, or image must be provided
    if not description and not jd_pdf_path and not jd_image_path:
        raise HTTPException(
            status_code=400,
            detail="Please provide at least one of: description text, PDF file, or image file."
        )

    # 5. Create DB record
    # Note: jd_extracted is None for now — LLM extraction happens in background worker
    new_job = HrJob(
        id=job_id,
        unique_slug=unique_slug,
        title=title,
        description=description,
        jd_pdf_url=jd_pdf_path,
        jd_image_url=jd_image_path,
        jd_extracted=description,  # Use typed text as extracted for now
        status="active",
    )

    db.add(new_job)
    db.commit()
    db.refresh(new_job)  # Reload from DB to get server_default values (created_at etc.)

    # 6. Return response with the shareable URL
    return JobCreatedResponse(
        id=new_job.id,
        unique_slug=new_job.unique_slug,
        title=new_job.title,
        status=new_job.status,
        created_at=new_job.created_at,
        apply_url=f"/apply/{new_job.unique_slug}",
    )


# ─── GET /jobs/my-jobs ────────────────────────────────────────────────────────
@router.get("/my-jobs", response_model=List[JobSummary])
def get_my_jobs(db: Session = Depends(get_db)):
    """
    Returns all jobs (for HR history tab).
    
    Note: No auth filter for now (as per requirements).
    In future: filter by hr_user_id = current_user.id
    
    Includes application_count — how many candidates applied.
    Using a SQL subquery via SQLAlchemy for this count.
    """
    # Subquery: count applications per job
    # This is more efficient than loading all applications and counting in Python
    app_count_subq = (
        db.query(
            JobApplication.job_id,
            func.count(JobApplication.id).label("application_count")
        )
        .group_by(JobApplication.job_id)
        .subquery()
    )

    # Main query: join jobs with application counts
    jobs_with_counts = (
        db.query(HrJob, app_count_subq.c.application_count)
        .outerjoin(app_count_subq, HrJob.id == app_count_subq.c.job_id)
        .order_by(HrJob.created_at.desc())  # Most recent first
        .all()
    )

    # Build response list
    result = []
    for job, count in jobs_with_counts:
        result.append(JobSummary(
            id=job.id,
            unique_slug=job.unique_slug,
            title=job.title,
            status=job.status,
            created_at=job.created_at,
            application_count=count or 0,
        ))

    return result


# ─── GET /jobs/slug/{slug} ────────────────────────────────────────────────────
@router.get("/slug/{slug}", response_model=JobDetailResponse)
def get_job_by_slug(slug: str, db: Session = Depends(get_db)):
    """
    PUBLIC endpoint — no auth required.
    Used by the candidate form page to load job details.
    
    Returns 404 if job not found.
    Returns 410 Gone if job is closed (position filled).
    """
    job = db.query(HrJob).filter(HrJob.unique_slug == slug).first()

    if not job:
        raise HTTPException(status_code=404, detail=f"Job '{slug}' not found.")

    if job.status == "closed":
        raise HTTPException(
            status_code=410,  # 410 = Gone (position closed)
            detail="This position is no longer accepting applications."
        )

    return job


# ─── PATCH /jobs/{job_id}/close ───────────────────────────────────────────────
@router.patch("/{job_id}/close")
def close_job(job_id: str, db: Session = Depends(get_db)):
    """HR closes a job — stops accepting new applications."""
    job = db.query(HrJob).filter(HrJob.id == job_id).first()

    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")

    job.status = "closed"
    db.commit()

    return {"message": f"Job '{job.title}' has been closed.", "status": "closed"}
