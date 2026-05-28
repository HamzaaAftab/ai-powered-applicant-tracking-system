import uuid
from supabase import create_client, Client
from core.config import settings
from fastapi import UploadFile, HTTPException


# ─── Supabase Client (Lazy Singleton) ────────────────────────────────────────
# We DON'T create the client at import time.
# Instead, we create it on first use via get_supabase_client().
#
# Why lazy initialization?
# - Fails FAST with clear error when first storage call is made
# - Doesn't crash the entire app on startup if key is misconfigured
# - Easier to test (can mock before first call)
_supabase_client: Client | None = None


def get_supabase_client() -> Client:
    """
    Returns the Supabase client, creating it on first call (lazy singleton).
    
    Why singleton pattern?
    → Creating a new client per request is wasteful (connection overhead)
    → One client handles connection pooling internally
    """
    global _supabase_client
    if _supabase_client is None:
        _supabase_client = create_client(
            settings.SUPABASE_URL,
            settings.SUPABASE_SECRET_KEY,
        )
    return _supabase_client


class StorageService:
    """
    Handles all file operations with Supabase Storage.
    
    Why a class and not just functions?
    - Groups related functionality together
    - Easy to mock in tests: replace StorageService with a fake one
    - Can hold state (e.g., bucket names) cleanly
    """

    # ── Allowed file types ────────────────────────────────────────────────────
    ALLOWED_JD_TYPES = {"application/pdf", "image/jpeg", "image/png", "image/webp"}
    ALLOWED_CV_TYPES = {"application/pdf"}
    MAX_FILE_SIZE_MB = 10  # 10 MB limit

    @staticmethod
    def _validate_file(file: UploadFile, allowed_types: set, field_name: str) -> None:
        """
        Validates file type. Raises HTTPException if invalid.
        
        Why validate here and not in the route?
        → Service layer validates business rules.
        → Route layer handles HTTP (request/response).
        → Separation of concerns!
        """
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"{field_name} must be one of: {', '.join(allowed_types)}. "
                       f"Got: {file.content_type}"
            )

    @staticmethod
    async def upload_jd_file(file: UploadFile, job_id: str) -> str:
        """
        Uploads a Job Description file (PDF or image) to Supabase Storage.
        
        Returns: Public storage path (stored in DB as jd_pdf_url or jd_image_url)
        
        Storage path format: job-descriptions/{job_id}/{uuid}.{ext}
        
        Why include job_id in the path?
        → Organizes files by job — easy to find and delete all files for a job
        → Prevents filename collisions between different jobs
        
        Why add a uuid to filename?
        → If HR re-uploads a new JD, old file isn't overwritten (we keep history)
        → Prevents caching issues
        """
        StorageService._validate_file(file, StorageService.ALLOWED_JD_TYPES, "JD file")

        # Get file extension from content type
        ext_map = {
            "application/pdf": "pdf",
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        ext = ext_map.get(file.content_type, "bin")

        # Unique filename inside the job's folder
        filename = f"{uuid.uuid4()}.{ext}"
        storage_path = f"{job_id}/{filename}"

        # Read file bytes
        contents = await file.read()

        try:
            # Upload to Supabase Storage
            # storage.from_(bucket).upload(path, data, options)
            get_supabase_client().storage.from_(settings.BUCKET_JD).upload(
                path=storage_path,
                file=contents,
                file_options={"content-type": file.content_type},
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload JD file to storage: {str(e)}"
            )

        # Return the path we store in DB
        # We don't return the full URL here — we generate signed URLs on demand
        return storage_path

    @staticmethod
    async def upload_cv(file: UploadFile, job_id: str, application_id: str) -> str:
        """
        Uploads a candidate's CV PDF to Supabase Storage.
        
        Storage path: candidate-cvs/{job_id}/{application_id}.pdf
        
        Why {application_id} as filename (not random uuid)?
        → Each application has exactly ONE cv
        → application_id is already unique
        → Easy to find: "give me CV for application X" → path is predictable
        """
        StorageService._validate_file(file, StorageService.ALLOWED_CV_TYPES, "CV")

        storage_path = f"{job_id}/{application_id}.pdf"
        contents = await file.read()

        try:
            get_supabase_client().storage.from_(settings.BUCKET_CV).upload(
                path=storage_path,
                file=contents,
                file_options={"content-type": "application/pdf"},
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to upload CV to storage: {str(e)}"
            )

        return storage_path

    @staticmethod
    def get_signed_url(bucket: str, path: str, expires_in_seconds: int = 3600) -> str:
        """
        Generates a temporary signed URL for downloading a private file.
        
        Why signed URLs instead of public URLs?
        → Buckets are PRIVATE — direct URL returns 403
        → Signed URL is valid for `expires_in_seconds` (default: 1 hour)
        → After expiry, link breaks — security!
        → HR gets fresh link every time they click "Download CV"
        
        Args:
            bucket: "candidate-cvs" or "job-descriptions"
            path: Storage path from DB (e.g. "job-id/application-id.pdf")
            expires_in_seconds: How long the URL is valid
        
        Returns: Temporary HTTPS URL to download the file
        """
        try:
            response = get_supabase_client().storage.from_(bucket).create_signed_url(
                path=path,
                expires_in=expires_in_seconds,
            )
            return response["signedURL"]
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to generate download URL: {str(e)}"
            )
