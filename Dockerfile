FROM python:3.11-slim
WORKDIR /app
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY paperfeed paperfeed
COPY scripts scripts
COPY db db
RUN useradd --create-home app
USER app
CMD ["uvicorn","paperfeed.main:app","--host","0.0.0.0","--port","8000"]
