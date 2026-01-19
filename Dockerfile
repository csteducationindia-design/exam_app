# 1. Use Python
FROM python:3.9-slim

# 2. Set the working folder
WORKDIR /app

# 3. Copy the requirements file first
COPY requirements.txt .

# 4. Install dependencies (This installs gunicorn!)
RUN pip install --no-cache-dir -r requirements.txt

# 5. Copy the rest of your code
COPY . .

# 6. Create the data folder for your database
VOLUME ["/app/data"]

# 7. Open the port
EXPOSE 8000

# 8. The Start Command
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8000", "exam_server:app"]