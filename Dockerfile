FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source
COPY . .

# Create data directory for SQLite
RUN mkdir -p /app/data

ENV PYTHONUNBUFFERED=1

CMD ["python", "-m", "nanobot.channels.telegram"]
