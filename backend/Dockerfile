FROM python:3.12-slim

WORKDIR /app

# System dependencies for PDF, OCR, and Postgres
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev tesseract-ocr poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Install Poetry
RUN pip install poetry==1.8.2

# Copy dependency files
COPY pyproject.toml poetry.lock* ./
RUN poetry config virtualenvs.create false
RUN poetry install --no-interaction --no-ansi --no-root

# Runtime dependencies not fully captured in pyproject.toml
RUN pip install \
    pypdf \
    langchain langchain-google-genai langchain-community \
    chromadb reportlab groq \
    google-generativeai \
    pydantic-settings

# Copy application code
COPY . .

# Create data directories
RUN mkdir -p /app/uploads /app/data/laws /app/data/reports /app/data/chroma_db

# Production: no --reload; honor $PORT for Render
ENV PORT=8000
EXPOSE 8000

CMD uvicorn app.main:app --host 0.0.0.0 --port ${PORT}
