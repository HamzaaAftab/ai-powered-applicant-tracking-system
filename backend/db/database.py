from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from core.config import settings


# ─── Engine ─────────────────────────────────────────────────────────────────
# Engine = low-level connection to the database.
# Think of it as the "phone line" between Python and PostgreSQL.
#
# pool_pre_ping  → Before using a connection, send a tiny "are you alive?" ping.
#                  Prevents "connection closed" errors after long idle periods.
# pool_recycle   → Force-replace connections older than 30 min.
#                  Supabase drops idle connections, so we recycle before they die.
# pool_size      → Keep 10 connections open permanently (the connection pool).
# max_overflow   → Allow up to 20 EXTRA connections during traffic spikes.
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
    pool_recycle=1800,
    pool_size=10,
    max_overflow=20,
)

# ─── Session Factory ─────────────────────────────────────────────────────────
# SessionLocal is a "factory" — call it to create a new session.
# autocommit=False → we manually control when to save (db.commit())
# autoflush=False  → don't auto-send SQL before every query
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


# ─── Base Class ──────────────────────────────────────────────────────────────
# All SQLAlchemy models (tables) will inherit from this Base.
# It tracks all models so we can do: Base.metadata.create_all(engine)
# to create all tables at once.
class Base(DeclarativeBase):
    pass


# ─── Dependency ──────────────────────────────────────────────────────────────
# FastAPI "dependency injection" — inject a DB session into any route.
#
# Usage in a route:
#   def my_route(db: Session = Depends(get_db)):
#       ...
#
# Flow:
#   1. FastAPI calls get_db()
#   2. db = SessionLocal() → open connection
#   3. yield db → give session to the route function
#   4. finally: db.close() → ALWAYS close, even if route throws an error
def get_db():
    db = SessionLocal()
    try:
        yield db          # ← route gets this db object
    finally:
        db.close()        # ← always runs, guaranteed cleanup
