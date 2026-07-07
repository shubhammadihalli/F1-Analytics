FROM python:3.11-slim

WORKDIR /app

COPY requirements/ requirements/
RUN pip install --no-cache-dir --prefer-binary \
    -r requirements/backend.txt \
    -r requirements/etl.txt

COPY . .

ENV PYTHONPATH=/app

EXPOSE 8080

CMD ["sh", "-c", "alembic -c database/alembic.ini upgrade head && exec uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
