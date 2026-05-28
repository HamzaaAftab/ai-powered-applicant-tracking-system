import json
from openai import AsyncOpenAI
from pydantic import BaseModel, Field, AliasChoices
from typing import List
from core.config import settings

class CVEvaluationResult(BaseModel):
    score: float = Field(..., description="Score from 0.0 to 100.0 based on how well the CV matches the JD.")
    reasoning: str = Field(..., description="A single detailed paragraph explaining the reasoning behind the score.")
    strengths: List[str] = Field(
        ..., 
        validation_alias=AliasChoices('strengths', 'key_strengths'), 
        description="List of the candidate's strengths relevant to the job requirements."
    )
    weaknesses: List[str] = Field(
        ..., 
        validation_alias=AliasChoices('weaknesses', 'key_weaknesses'), 
        description="List of the candidate's weaknesses or missing requirements."
    )

class LLMService:
    """
    Service for interacting with Large Language Models (LLMs).
    We use NVIDIA NIM (NVIDIA Inference Microservices) via the standard OpenAI Python client.
    This gives us blazing fast inference speeds and access to state-of-the-art models like Llama 3.1.
    """

    @staticmethod
    def get_client() -> AsyncOpenAI:
        """
        Initializes the async OpenAI client pointed to the NVIDIA endpoint.
        """
        return AsyncOpenAI(
            base_url="https://integrate.api.nvidia.com/v1",
            api_key=settings.NVIDIA_API_KEY
        )

    @staticmethod
    async def evaluate_cv(jd_text: str, cv_text: str) -> dict:
        """
        Evaluates a CV against a Job Description using NVIDIA NIM and returns a structured JSON response.
        
        Args:
            jd_text: The extracted text of the Job Description.
            cv_text: The extracted text of the Candidate's CV.
            
        Returns:
            A dictionary containing score, reasoning, strengths, and weaknesses.
        """
        client = LLMService.get_client()

        # ── Pydantic to JSON Schema ──
        # We generate the JSON Schema automatically from our Pydantic model.
        # This keeps our code DRY and utilizes Pydantic's powerful type checking.
        schema = CVEvaluationResult.model_json_schema()

        prompt = f"""You are an expert technical HR recruiter. 
Your task is to objectively evaluate a candidate's CV against a Job Description.

--- JOB DESCRIPTION ---
{jd_text}

--- CANDIDATE CV ---
{cv_text}

--- INSTRUCTIONS ---
Analyze the CV against the Job Description carefully. Be critical but fair.
Provide:
1. "score": A float between 0.0 and 100.0.
2. "reasoning": A detailed reasoning paragraph.
3. "strengths": Array of strengths.
4. "weaknesses": Array of weaknesses.

IMPORTANT: You MUST return ONLY valid JSON using the exact keys above. Do not include markdown code blocks (```json) or any other text before or after the JSON.
"""

        try:
            print("[LLMService] Sending evaluation request to NVIDIA NIM LLM... ")
            response = await client.chat.completions.create(
                model="meta/llama-3.3-70b-instruct",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.2,  # Low temperature for more analytical/consistent responses
                top_p=0.7,
                max_tokens=1024,
                # NVIDIA's powerful extension for guaranteed JSON schema:
                extra_body={"guided_json": schema}
            )

            # The response will be a JSON string that perfectly matches our schema
            raw_content = response.choices[0].message.content
            print(f"[LLMService] Raw LLM Response: {raw_content}")

            if not raw_content:
                raise ValueError("LLM returned an empty response.")

            # Sometimes LLMs wrap JSON in markdown block: ```json ... ```
            # We need to strip that out just in case
            cleaned_content = raw_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            # Use Pydantic to parse and validate the response
            # This ensures that even if LLM misses a key, Pydantic catches it (or applies defaults)
            validated_data = CVEvaluationResult.model_validate_json(cleaned_content)
            
            print(f"[LLMService] Evaluation complete! Score: {validated_data.score}")
            return validated_data.model_dump()

        except Exception as e:
            print(f"[LLMService] Failed to evaluate CV with LLM: {e}")
            # Return a fallback response so the system doesn't completely break
            return {
                "score": 0.0,
                "reasoning": f"Automated scoring failed due to an LLM error: {str(e)}",
                "strengths": [],
                "weaknesses": []
            }
