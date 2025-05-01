FROM node:18-alpine as frontend-builder
WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim
WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY backend/app/ ./app/

COPY --from=frontend-builder /frontend/dist /app/static
CMD ["uvicorn", "app.api:app", "--host", "0.0.0.0", "--port", "8000"]