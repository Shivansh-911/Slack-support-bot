FROM python:3.12-slim

# Postgres client headers (psycopg[binary] carries its own libpq, but
# build tools are still needed for a couple of transitive C extensions).
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential libpq-dev \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets $PORT at runtime; default to 8000 for local `docker run`.
ENV PORT=8000
EXPOSE 8000

# migrate on every boot, then serve. Fine for a single-service deploy;
# move to a Railway pre-deploy command instead if you ever run >1 replica.
CMD python manage.py migrate --noinput && \
    gunicorn config.wsgi:application --bind 0.0.0.0:${PORT} --workers 3
