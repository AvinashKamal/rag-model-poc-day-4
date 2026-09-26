FROM python:3.12-slim

WORKDIR /app

RUN pip install --no-cache-dir uv

COPY backend/pyproject.toml ./
COPY shared/domain_lib /shared/domain_lib
COPY config /config
RUN uv pip install --system --no-cache -r pyproject.toml

COPY backend/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
