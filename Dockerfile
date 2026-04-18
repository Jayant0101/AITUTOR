FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PYTHONPATH=/app

# Copy requirements and install python dependencies
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

# Copy the backend application code
COPY backend/ .

# Create uploads directory
RUN mkdir -p uploads

EXPOSE 8000

# Start the application
# Use uvicorn directly; PORT is injected by Railway/cloud platform
CMD sh -c "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"
