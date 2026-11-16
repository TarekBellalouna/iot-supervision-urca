FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY lorawan_crypto.py gateway.py simulator.py ./
CMD ["python", "-u", "simulator.py"]