FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy everything needed for install
COPY pyproject.toml .
COPY classifier/ classifier/
COPY db/ db/
COPY web.py main.py ./

# Install Python dependencies
RUN uv pip install --system -e .

# Copy runtime data
COPY data/wc2026.db data/wc2026.db
COPY data/FC26_20250921.csv data/FC26_20250921.csv
COPY data/intl_results/ data/intl_results/
COPY data/wc_history/ data/wc_history/

# Copy pre-built frontend (optional, for serving from backend)
COPY static/ static/

EXPOSE 8000

CMD ["uvicorn", "web:app", "--host", "0.0.0.0", "--port", "8000"]
