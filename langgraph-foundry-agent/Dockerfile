FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY agent/ agent/
COPY agent365_server.py .

EXPOSE 8000

CMD ["python", "agent365_server.py"]
