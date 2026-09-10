FROM python:3.12.12-slim-bookworm
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gdal-bin libgdal-dev build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt requirements-lock.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY geoai ./geoai
RUN useradd --uid 10001 --create-home geoai
USER geoai
CMD ["uvicorn", "geoai.main:app", "--host", "0.0.0.0", "--port", "8080"]
