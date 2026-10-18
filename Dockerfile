FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN playwright install chromium
RUN playwright install-deps

# Note: A containerized browser will not automatically appear on the developer's desktop.
# Playwright headless=False in Docker requires X11 forwarding or VNC setup.
# This Dockerfile runs the backend; browser UI will only be visible if run locally.

# Copy project files
COPY . .

# Set default port
ENV PORT=3000
EXPOSE 3000

# Run uvicorn server
CMD ["sh", "-c", "uvicorn athena.server:app --host 0.0.0.0 --port ${PORT:-3000}"]
