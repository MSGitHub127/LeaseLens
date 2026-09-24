FROM python:3.12-slim

# Run as a non-root user -- a document-handling service shouldn't run as root.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app

RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV LEASELENS_DATABASE_URL=sqlite:////app/data/leaselens.db
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health')" || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
