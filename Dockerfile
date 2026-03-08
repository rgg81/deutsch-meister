FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create data and workspace directories
RUN mkdir -p /app/data /app/workspace

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "nanobot", "gateway", "--config", "/app/config.json"]
