# ================================================
# Dockerfile — Panther Cloud Air web service
# Builds a lightweight Python 3.11 image that
# runs the Flask REST API and serves the front-end.
#
# Build:  docker compose up --build
# ================================================

FROM python:3.11-slim

# Set /app as the working directory inside the container
WORKDIR /app

# Install Python dependencies before copying source code
# so Docker can cache this layer and skip it on code-only changes
COPY requirements.txt .
RUN pip install -r requirements.txt

# Copy all project source files into the container
COPY . .

# 1. seed_users.py creates the default Admin/Employee accounts (idempotent)
# 2. app.py starts the Flask development server on port 5000
CMD ["sh", "-c", "python seed_users.py && python app.py"]
