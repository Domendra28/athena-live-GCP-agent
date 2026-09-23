FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Set default port
ENV PORT=8000
EXPOSE 8000

# Run uvicorn server
CMD ["sh", "-c", "uvicorn athena.server:app --host 0.0.0.0 --port ${PORT:-8000}"]
