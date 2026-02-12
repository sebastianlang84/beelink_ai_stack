FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt /app/requirements.txt
RUN apt-get update \
  && apt-get install -y --no-install-recommends nodejs npm \
  && npm install -g @google/gemini-cli \
  && pip install --no-cache-dir -r /app/requirements.txt \
  && rm -rf /var/lib/apt/lists/*

COPY app /app/app

ENV PYTHONUNBUFFERED=1

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
