# Smart HR System - Frontend Implementation Guide

Welcome, Frontend Agent! 
This document contains the complete architectural overview and API contract for the **Smart HR System**. Read this carefully before writing any frontend code.

## 🏗️ Architecture Overview
The system is an AI-powered HR platform that parses candidate CVs using **LlamaParse** and scores them against Job Descriptions using **NVIDIA NIM (Llama 3.1 70B)**. 

- **Backend:** FastAPI (Python)
- **Database:** PostgreSQL (Supabase)
- **Storage:** Supabase Storage (`job-descriptions` and `candidate-cvs` buckets)
- **Frontend Stack (Your Job):** Next.js (React), TailwindCSS, Shadcn UI / Framer Motion.

---

## 🧠 Core Architectural Concepts (CRITICAL)

### 1. The Background Worker (Asynchronous AI)
When a candidate submits their CV, the backend **DOES NOT** score the CV synchronously. 
AI processing takes 10-30 seconds, so the backend immediately returns a `201 Created` with a status of `pending`.
**Frontend Implication:** 
- The Candidate should see a success message immediately.
- The HR Dashboard should probably implement polling (or a refresh button) when viewing candidates for a job, because a candidate's status will change from `pending` -> `scoring` -> `scored` in the background.

### 2. Payload Formats (`multipart/form-data`)
Because the API handles file uploads (CV PDFs, JD PDFs), **all `POST` and `PATCH` endpoints expect Form Data**, NOT JSON. 
**Frontend Implication:** 
You must use `FormData()` in JavaScript/TypeScript for requests. Do NOT use `JSON.stringify()`.

---

## 📡 API Endpoints Contract
Base URL: `http://localhost:8000` (or proxy via `/api/` in Next.js)

### 🟢 1. Job Management (HR Side)

#### Create a Job
- **URL:** `POST /jobs/create`
- **Payload (FormData):**
  - `title` (string, required)
  - `description` (string, optional)
  - `jd_pdf` (File, optional)
  - `jd_image` (File, optional)
- **Response (201):**
  ```json
  {
    "id": "uuid",
    "unique_slug": "JOB-ABCDE123",
    "title": "Senior Python Developer",
    "status": "active",
    "created_at": "2023-10-12T...",
    "apply_url": "/apply/JOB-ABCDE123"
  }
  ```
  *(Note: `apply_url` is the relative path you should use to generate the public link for the candidate).*

#### Get HR Dashboard Jobs
- **URL:** `GET /jobs/my-jobs`
- **Response:** Array of jobs with `application_count`.
  ```json
  [
    {
      "id": "uuid",
      "unique_slug": "JOB-ABCDE123",
      "title": "Senior Python Developer",
      "status": "active",
      "created_at": "...",
      "application_count": 5
    }
  ]
  ```

#### Close a Job
- **URL:** `PATCH /jobs/{job_id}/close`
- **Response:** `{"message": "...", "status": "closed"}`

---

### 🔵 2. Candidate Application Flow

#### Get Job Details (Public Form)
- **URL:** `GET /jobs/slug/{slug}` (e.g., `/jobs/slug/JOB-ABCDE123`)
- **Response (200):** Job details to render the public application form.
- **Error (410 Gone):** If the job is closed, show a "Position Closed" screen.

#### Submit Application
- **URL:** `POST /applications/submit`
- **Payload (FormData):**
  - `job_slug` (string, required)
  - `candidate_name` (string, required)
  - `candidate_email` (string, required)
  - `candidate_phone` (string, optional)
  - `experience_years` (integer, optional)
  - `linkedin_url` (string, optional)
  - `portfolio_url` (string, optional)
  - `cover_letter` (string, optional)
  - `cv_file` (File, required) - MUST BE PDF.
- **Response (201):**
  ```json
  {
    "id": "uuid",
    "candidate_name": "Hamza Khan",
    "status": "pending",
    "message": "Application submitted successfully! We will review it shortly."
  }
  ```

---

### 🟡 3. Application Review (HR Side)

#### Get All Candidates for a Job
- **URL:** `GET /applications/job/{job_id}`
- **Response:** Array of candidates. The backend **automatically sorts** them: Top ranked AI scores first, pending/unscored applications at the bottom.
  ```json
  [
    {
      "id": "uuid",
      "rank": 1,
      "candidate_name": "Hamza Khan",
      "candidate_email": "hamza@example.com",
      "experience_years": 6,
      "llm_score": 87.5,
      "status": "scored",
      "submitted_at": "...",
      "cv_url": "https://<supabase-url>/storage/v1/object/sign/candidate-cvs/..."
    }
  ]
  ```
  *(Note: `cv_url` is a pre-signed 1-hour URL. You can directly put this in an `<a href>` tag to let HR download the CV).*

#### Get Specific Application Detail (Expanded View)
- **URL:** `GET /applications/{app_id}`
- **Response:** Detailed view including AI reasoning.
  ```json
  {
    "id": "uuid",
    "rank": 1,
    "candidate_name": "Hamza Khan",
    ...
    "llm_score": 87.5,
    "llm_reasoning": "The candidate has strong Python skills...",
    "llm_strengths": ["FastAPI", "PostgreSQL", "LLMs"],
    "llm_weaknesses": ["No React experience"],
    "status": "scored",
    ...
  }
  ```

#### Manually Update Status (Shortlist / Reject)
- **URL:** `PATCH /applications/{app_id}/status`
- **Payload (FormData):**
  - `new_status`: Must be one of `"reviewed"`, `"shortlisted"`, `"rejected"`.
- **Response:** Success message.

---

## 🎨 Recommended UI/UX Approach

1. **Dashboard (HR)**
   - Use a Sidebar for navigation (Jobs, Settings).
   - "Jobs" view should be a grid or table of cards.
   - Clicking a Job opens a detailed view showing the ranked list of candidates.
   - Show nice badges for status: e.g., AI Scoring (`yellow/pulse`), Scored (`blue`), Shortlisted (`green`), Rejected (`red`).

2. **Public Application Page**
   - Clean, minimalistic form.
   - Show the Job Title and Description prominently.
   - File drag-and-drop zone for the CV.
   - Loading spinner on submit, transitioning to a Confetti/Success screen.

Good luck! Build a visually stunning and robust frontend.
