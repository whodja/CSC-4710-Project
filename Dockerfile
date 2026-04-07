FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
# Seed hashed users then start the API server
CMD ["sh", "-c", "python seed_users.py && python app.py"]
