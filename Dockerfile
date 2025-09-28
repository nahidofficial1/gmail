# Python 3.11 slim image ব্যবহার করা হলো
FROM python:3.11-slim

# ওয়ার্কিং ডিরেক্টরি সেট করুন
WORKDIR /app

# সব ফাইল কপি করুন container এ
COPY . .

# dependencies install করুন
RUN pip install --no-cache-dir -r requirements.txt

# ✅ uvicorn দিয়ে FastAPI সার্ভার চালানো হবে (Telegram Bot + Webhook)
CMD ["uvicorn", "main:app_webhook", "--host", "0.0.0.0", "--port", "10000"]
