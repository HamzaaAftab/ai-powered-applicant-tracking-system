# Use the official lightweight Python image
FROM python:3.12-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860 \
    PATH="/home/user/.local/bin:$PATH"

# HuggingFace Spaces require running as a non-root user
RUN useradd -m -u 1000 user

# Set the working directory
WORKDIR /app

# Change ownership of the working directory to the non-root user
RUN chown user:user /app

# Switch to the non-root user
USER user

# Copy requirements first (to leverage Docker cache)
COPY --chown=user:user requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the entire project code
COPY --chown=user:user . .

# Change working directory to where the FastAPI app is located
WORKDIR /app/backend

# Expose the port (HuggingFace defaults to 7860)
EXPOSE 7860

# Start the application
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
