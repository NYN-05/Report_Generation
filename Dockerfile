FROM python:3.11-slim

WORKDIR /app

# Install system dependencies for python-docx and PDF support
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first for layer caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create required directories
RUN mkdir -p output logs cache

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "from src.core.config import check_dependencies; deps = check_dependencies(); exit(0 if deps.get('python-docx') else 1)" || exit 1

ENTRYPOINT ["python", "-m", "src.main"]
CMD ["--help"]
