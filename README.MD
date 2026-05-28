# 🚀 Smart HR: AI-Powered Applicant Tracking System

A modern, intelligent HR and Applicant Tracking System (ATS) that automates candidate screening. The system uses **Vision Language Models (VLMs)** and **Large Language Models (LLMs)** to parse candidate CVs and objectively score them against Job Descriptions.

## ✨ Key Features

- **🧠 AI-Powered Scoring:** Automatically evaluates CVs against Job Descriptions and provides a score (0-100) along with detailed reasoning, strengths, and weaknesses.
- **📄 Advanced Document Parsing:** Uses **LlamaParse** to handle complex CV structures (tables, columns, PDFs, and images) with high accuracy.
- **⚡ Asynchronous Processing:** Heavy AI evaluations run securely in a background worker, ensuring instant API responses for end-users.
- **🛡️ Strict Type Safety:** Uses **Pydantic** and NVIDIA NIM's `guided_json` to strictly enforce and validate structured JSON outputs from the LLM.
- **☁️ Cloud Storage:** Seamlessly uploads and manages candidate CVs and Job Descriptions using **Supabase Storage**.

## 🛠️ Technology Stack

- **Backend:** FastAPI (Python), SQLAlchemy, Uvicorn
- **Database:** PostgreSQL (Supabase)
- **AI / LLM:** NVIDIA NIM (Llama 3.1 70B Instruct), `openai` python client
- **OCR / Parsing:** LlamaParse (LlamaIndex)
- **Frontend (Upcoming):** Next.js, TailwindCSS

## ⚙️ Environment Variables (`.env`)

To run this project, you need to configure the following environment variables in your backend root:

```env
# Database
DATABASE_URL="postgresql://<user>:<password>@<supabase-host>:6543/postgres?sslmode=require"

# AI API Keys
NVIDIA_API_KEY="nvapi-..."
LLAMA_PARSE_API_KEY="llx-..."

# Supabase Storage Keys (Legacy Service Role / Anon)
NEXT_PUBLIC_SUPABASE_URL="https://<your-project>.supabase.co"
NEXT_PUBLIC_SUPABASE_ANON_KEY="eyJ..."
```

## 🚀 How to Run Locally

1. **Activate Virtual Environment:**
   ```bash
   # Windows
   .\venv\Scripts\activate
   ```
2. **Install Dependencies:**
   ```bash
   pip install -r requirements.txt
   ```
3. **Start the FastAPI Server:**
   ```bash
   cd backend
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```
4. **Access the API Documentation:**
   Open your browser and navigate to the interactive Swagger UI:
   `http://localhost:8000/docs`

## 📡 Core API Flow

1. **HR Creates a Job (`POST /jobs/create`)**: Upload a Job Description text, PDF, or Image.
2. **Candidate Applies (`POST /applications/submit`)**: Uploads their CV. The API instantly returns a `pending` status.
3. **Background Worker**: Kicks in automatically, downloads the CV, parses it via LlamaParse, evaluates it via NVIDIA NIM, and saves the final JSON result.
4. **HR Views Rankings (`GET /applications/job/{job_id}`)**: Fetches a pre-sorted list of top candidates.
