from sqlalchemy.orm import Session
from sqlalchemy import desc
from db.database import SessionLocal
from models.job_applications import JobApplication
from models.hr_jobs import HrJob
from services.pdf import PDFParsingService
from services.llm import LLMService

async def process_new_application(application_id: str):
    """
    Background worker task to evaluate a candidate's CV against the Job Description.
    This runs asynchronously without blocking the main API response.
    """
    print(f"\n[Worker] Started processing application {application_id}")
    
    # We must create our own DB session since this runs outside the request lifecycle
    db = SessionLocal()
    try:
        # 1. Fetch the application
        application = db.query(JobApplication).filter(JobApplication.id == application_id).first()
        if not application:
            print(f"[Worker] Error: Application {application_id} not found.")
            return

        # Fetch the job to get JD text
        job = db.query(HrJob).filter(HrJob.id == application.job_id).first()
        if not job:
            print(f"[Worker] Error: Job for application {application_id} not found.")
            return

        # 2. Extract CV text if not already extracted
        if not application.cv_extracted:
            print(f"[Worker] Extracting text from candidate CV (LlamaParse)...")
            application.status = "parsing_cv"
            db.commit()
            
            cv_text = await PDFParsingService.extract_text_from_supabase_file(
                bucket="candidate-cvs",
                path=application.cv_url
            )
            application.cv_extracted = cv_text
            db.commit()

        # Extract JD text if needed (if it's a PDF or Image and not plain text)
        jd_text = job.description or job.jd_extracted
        if not jd_text:
            if job.jd_pdf_url:
                print(f"[Worker] Extracting text from Job Description PDF...")
                jd_text = await PDFParsingService.extract_text_from_supabase_file(
                    bucket="job-descriptions",
                    path=job.jd_pdf_url
                )
                job.jd_extracted = jd_text
                db.commit()
            elif job.jd_image_url:
                print(f"[Worker] Extracting text from Job Description Image...")
                jd_text = await PDFParsingService.extract_text_from_supabase_file(
                    bucket="job-descriptions",
                    path=job.jd_image_url
                )
                job.jd_extracted = jd_text
                db.commit()

        cv_text = application.cv_extracted
        
        if not cv_text or not jd_text:
            print(f"[Worker] Failed to get texts for evaluation. CV: {bool(cv_text)}, JD: {bool(jd_text)}")
            application.status = "failed_extraction"
            db.commit()
            return

        # 3. LLM Evaluation
        print(f"[Worker] Running NVIDIA NIM LLM evaluation...")
        application.status = "scoring"
        db.commit()

        llm_result = await LLMService.evaluate_cv(jd_text=jd_text, cv_text=cv_text)

        # 4. Save results to DB
        application.llm_score = llm_result.get("score", 0.0)
        application.llm_reasoning = llm_result.get("reasoning", "")
        application.llm_strengths = llm_result.get("strengths", [])
        application.llm_weaknesses = llm_result.get("weaknesses", [])
        application.status = "scored"
        db.commit()

        # 5. Re-compute rankings for this job
        print(f"[Worker] Re-computing ranks for job {job.id}...")
        all_scored_apps = db.query(JobApplication)\
            .filter(JobApplication.job_id == job.id)\
            .filter(JobApplication.status == "scored")\
            .order_by(desc(JobApplication.llm_score))\
            .all()

        # Assign ranks based on score ordering (highest score gets rank 1)
        for rank, app in enumerate(all_scored_apps, start=1):
            app.rank = rank
            
        db.commit()
        print(f"[Worker] Successfully processed application {application_id}! Score: {application.llm_score}")

    except Exception as e:
        print(f"[Worker] Unexpected error processing application {application_id}: {e}")
        # Try to mark it as failed if we still have access to the object
        try:
            application.status = "failed"
            db.commit()
        except:
            pass
    finally:
        db.close()
