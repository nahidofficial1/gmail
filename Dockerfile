# Python 3.11 slim image
FROM python:3.11-slim

WORKDIR /app
COPY . .

RUN pip install --no-cache-dir -r requirements.txt

# ✅ সরাসরি main.py চালাও
CMD ["python", "main.py"]
