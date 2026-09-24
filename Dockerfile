FROM python:3.12-slim

# Run as a non-root user -- a document-handling service shouldn't run as root.
RUN useradd --create-home --uid 1000 appuser
WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY frontend ./frontend
COPY assets ./assets
COPY index.html ./index.html

RUN mkdir -p /app/data && chown -R appuser:appuser /app
USER appuser

ENV LEASELENS_DATABASE_URL=sqlite:////app/data/leaselens.db
ENV PORT=8000
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=3s CMD python -c "import urllib.request, os; port = os.environ.get('PORT', '8000'); urllib.request.urlopen(f'http://localhost:{port}/api/health')" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
