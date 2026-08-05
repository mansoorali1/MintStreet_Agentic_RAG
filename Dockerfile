# Slim Python base - this app has no need for the full image, and a
# smaller image means faster Render builds and cold starts.
FROM python:3.11-slim

# Prevents .pyc files and forces stdout/stderr to be unbuffered so logs
# show up in the Render build/runtime logs immediately, not batched.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install dependencies first, separately from the app code, so Docker
# can cache this layer and skip the (slow) reinstall when only app code
# changes between deploys.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Now bring in the actual application. ingestion/ and notebooks are
# excluded via .dockerignore - they're not needed at runtime.
COPY app/ ./app/
COPY artifacts/ ./artifacts/
COPY main.py .

# Render expects the app to be reachable on 7860.
EXPOSE 7860

# Render injects Space secrets as environment variables automatically,
# so nothing extra needed here for GROQ_API_KEY etc - app/config.py picks
# them straight up from the environment.
CMD ["python", "main.py"]

