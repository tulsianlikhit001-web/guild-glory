FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1 PIP_NO_CACHE_DIR=1
WORKDIR /app
COPY requirements-web.txt .
RUN pip install -r requirements-web.txt
COPY . .
ENV PORT=10000
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn web.app:app --host 0.0.0.0 --port ${PORT:-10000}"]
