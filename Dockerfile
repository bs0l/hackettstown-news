FROM python:3.11-slim

WORKDIR /app

# lxml needs a compiler + libxml headers to build on arm; keep the image
# small by removing build deps afterward.
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libxml2-dev libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV NEWS_DB_PATH=/data/news.db
ENV FETCH_INTERVAL_MINUTES=30

VOLUME ["/data"]
EXPOSE 5000

CMD ["python", "app.py"]
