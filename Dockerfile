FROM python:3.12-slim

# GDAL für geopandas (wird beim Regionalatlas-Import gebraucht)
RUN apt-get update && apt-get install -y \
    libgdal-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .