import random
import string
from sqlalchemy.orm import Session
from models.hr_jobs import HrJob


def _generate_raw_slug(length: int = 8) -> str:
    """
    Generates a random alphanumeric string.
    Example: "A3F9K2X7"
    
    Uses only uppercase + digits (no lowercase) for readability.
    No ambiguous chars: removed O (oh) and 0 (zero), I (eye) and 1 (one).
    """
    # Remove visually ambiguous characters
    chars = string.ascii_uppercase.replace("O", "").replace("I", "") + \
            string.digits.replace("0", "").replace("1", "")
    return "".join(random.choices(chars, k=length))


def generate_unique_slug(db: Session) -> str:
    """
    Generates a unique job slug that doesn't already exist in the DB.
    
    Format: "JOB-XXXXXXXX"
    
    Algorithm:
    1. Generate random 8-char string
    2. Check if it exists in DB
    3. If exists → try again (collision is VERY rare: ~2.8 trillion combos)
    4. Return unique slug
    
    Why check DB instead of just trusting randomness?
    → Murphy's Law: if it CAN collide, it WILL collide at the worst moment
    → DB has UNIQUE constraint as final safety net
    → This function is the first line of defense
    
    Args:
        db: SQLAlchemy session (needed to query existing slugs)
    
    Returns:
        Unique slug string like "JOB-A3F9K2X7"
    """
    max_attempts = 10  # Safeguard against infinite loop (shouldn't happen)

    for attempt in range(max_attempts):
        slug = f"JOB-{_generate_raw_slug()}"

        # Check if slug already exists
        existing = db.query(HrJob).filter(HrJob.unique_slug == slug).first()

        if not existing:
            return slug  # Found a unique one!

        # Very unlikely to reach here, but log if it does
        print(f"[SlugGenerator] Collision on attempt {attempt + 1}, retrying...")

    # This should never happen in practice
    raise RuntimeError(
        "Failed to generate unique slug after 10 attempts. "
        "This is extremely unlikely — check if the DB has millions of jobs."
    )
