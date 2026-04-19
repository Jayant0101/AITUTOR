FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PORT=8000
ENV PYTHONPATH=/app

# Copy requirements and install python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && python -m spacy download en_core_web_sm

# Copy the rest of the backend application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

EXPOSE 8000

# Use gunicorn with uvicorn workers; PORT defaults to 8000 if not set by platform
CMD sh -c "gunicorn -w ${WEB_CONCURRENCY:-4} -k uvicorn.workers.UvicornWorker app.main:app --bind 0.0.0.0:${PORT:-8000}"
