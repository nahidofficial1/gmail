# Python এর stable version ব্যবহার করি
FROM python:3.11-slim

# container এর work directory
WORKDIR /app

# requirements copy করে install করি
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# সব ফাইল container এ কপি করি
COPY . .

# container start হলে main.py রান হবে
CMD ["python", "main.py"]
