FROM python:3.11-slim

WORKDIR /app
COPY . .

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

RUN apt-get update && apt-get install -y \
    gcc \
    python3-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

COPY app/ ./app/

RUN mkdir -p /app/app/data && chmod 777 /app/app/data

# WhatsApp environment variables
ENV WHATSAPP_TOKEN=""
ENV WHATSAPP_APP_SECRET=""
ENV WHATSAPP_PHONE_ID=""
ENV WHATSAPP_VERSION="v17.0"
ENV EXPOSE_CONFIDENCE_SCORE=true
ENV INCLUDE_CONFIDENCE_REASON=true
ENV ENABLE_DATABASE_STORAGE=true
ENV CONFIDENCE_THRESHOLD=70.0

EXPOSE 8000
ENV PORT=8000
CMD ["sh", "-c", "uvicorn app.api:app --host 0.0.0.0 --port ${PORT:-8000}"]
