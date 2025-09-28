# Python 3.11 slim image ব্যবহার করা হলো
FROM python:3.11-slim

# ওয়ার্কিং ডিরেক্টরি সেট করুন
WORKDIR /app

# সব ফাইল কপি করুন container এ
COPY . .

# dependencies install করুন
RUN pip install --no-cache-dir -r requirements.txt

# বট রান করার কমান্ড
CMD ["python", "main.py"]
