# PeerWire Cloud Server Dockerfile
FROM python:3.12-slim

WORKDIR /app

# Copy application files
COPY src/ /app/src/

# Expose standard TCP socket port
EXPOSE 5000

ENV PYTHONUNBUFFERED=1

CMD ["python", "src/server.py", "5000"]
