import os
import tempfile
from typing import Optional
from fastapi import HTTPException
from llama_parse import LlamaParse
from core.config import settings
from services.storage import get_supabase_client


class PDFParsingService:
    """
    Service responsible for extracting text from documents.
    Uses LlamaParse for highly accurate, state-of-the-art OCR and table extraction.
    """

    @staticmethod
    async def extract_text_from_supabase_file(bucket: str, path: str) -> Optional[str]:
        """
        Downloads a file from Supabase storage and uses LlamaParse to extract its text.
        
        Args:
            bucket: The Supabase storage bucket (e.g., 'candidate-cvs').
            path: The path of the file in the bucket (e.g., 'job-uuid/cv-uuid.pdf').
            
        Returns:
            The extracted markdown text as a string, or None if extraction fails.
        """
        if not path:
            return None

        # 1. Download file bytes from Supabase
        try:
            file_bytes = get_supabase_client().storage.from_(bucket).download(path)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"Failed to download file from storage for parsing: {str(e)}"
            )

        if not file_bytes:
            return None

        # 2. Extract extension to help LlamaParse (default to .pdf)
        ext = os.path.splitext(path)[1]
        if not ext:
            ext = ".pdf"

        # 3. Use a NamedTemporaryFile to feed bytes to LlamaParse
        # On Windows, a NamedTemporaryFile cannot be opened by a second process
        # if it's still open in the 'with' block. So we set delete=False,
        # close the block, let LlamaParse read it, and then delete manually.
        parsed_text = None
        tmp_path = None
        
        try:
            with tempfile.NamedTemporaryFile(suffix=ext, delete=False) as tmp:
                tmp.write(file_bytes)
                tmp.flush()  # Ensure data is written to disk
                tmp_path = tmp.name

            # Initialize LlamaParse
            # We use result_type="markdown" because LLMs understand markdown formatting
            # like tables and headings much better than raw text.
            parser = LlamaParse(
                api_key=settings.LLAMA_PARSE_API_KEY,
                result_type="markdown",
                verbose=False
            )

            # Retry logic: Heavy images (PNG) might cause LlamaParse httpx client to timeout ("Client Closed Request")
            documents = None
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # Parse the file asynchronously
                    documents = await parser.aload_data(tmp_path)
                    break  # Success
                except Exception as e:
                    print(f"[Worker] Warning: LlamaParse async attempt {attempt + 1} failed: {e}")
                    if attempt == max_retries - 1:
                        # Fallback to synchronous load_data on the last attempt
                        print("[Worker] Falling back to synchronous LlamaParse load_data...")
                        documents = parser.load_data(tmp_path)
            
            # Combine all pages if it's a multi-page document
            if documents:
                parsed_text = "\n\n".join([doc.text for doc in documents])

        except Exception as e:
            print(f"[Worker] Error parsing document with LlamaParse: {e}")
            # Do not raise HTTPException here, just return None so the worker can handle it gracefully
            return None
        finally:
            # Clean up the temporary file
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.remove(tmp_path)
                except Exception as cleanup_err:
                    print(f"[Worker] Warning: Failed to clean up temp file {tmp_path}: {cleanup_err}")

        return parsed_text
