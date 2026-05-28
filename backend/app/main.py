from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from db.database import Base, engine
from models import hr_jobs, job_applications  # noqa: F401 — import so Base registers them
from api import jobs, applications


# ─── Lifespan (replaces deprecated @app.on_event) ────────────────────────────
# 'lifespan' is the modern FastAPI way to run startup/shutdown code.
# Everything BEFORE 'yield' runs at startup.
# Everything AFTER 'yield' runs at shutdown.
#
# Why @asynccontextmanager?
# FastAPI lifespan must be an async context manager — this decorator makes it one.
@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── STARTUP ──
    print("[startup] Starting Smart HR API...")
    print("[startup] Creating database tables if they don't exist...")
    try:
        # create_all looks at every model that inherits from Base
        # and creates its table in PostgreSQL if it doesn't exist yet.
        # SAFE: it never drops or modifies existing tables.
        Base.metadata.create_all(bind=engine)
        print("[startup] Database connected! All tables verified.")
    except Exception as e:
        # Warn but don't crash — useful during development
        print(f"[startup] WARNING: DB connection failed: {e}")
        print("[startup] Check your DATABASE_URL in .env")

    yield  # ← app runs here (handling requests)

    # ── SHUTDOWN ──
    print("[shutdown] Shutting down...")


# ─── App Instance ─────────────────────────────────────────────────────────────
app = FastAPI(
    title="Smart HR API",
    description="AI-powered HR platform for job posting and candidate ranking",
    version="1.0.0",
    lifespan=lifespan,   # attach our startup/shutdown logic
    # OpenAPI docs:
    # Swagger UI → http://localhost:8000/docs
    # ReDoc      → http://localhost:8000/redoc
)


# ─── CORS Middleware ──────────────────────────────────────────────────────────
# CORS = Cross-Origin Resource Sharing
# Without this, browser BLOCKS requests from frontend (port 3000) to backend (port 8000)
# because they are on DIFFERENT origins (different ports = different origin)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── Include Routers ─────────────────────────────────────────────────────────
# All job routes:         /jobs/create, /jobs/my-jobs, /jobs/slug/{slug}
# All application routes: /applications/submit, /applications/job/{id}
app.include_router(jobs.router)
app.include_router(applications.router)


# ─── Health Check ─────────────────────────────────────────────────────────────
@app.get("/health", tags=["system"])
def health_check():
    """
    Simple ping endpoint — use this to verify the server is running.
    Returns 200 OK if server is up, regardless of DB status.
    """
    return {"status": "ok", "message": "Smart HR API is running"}
