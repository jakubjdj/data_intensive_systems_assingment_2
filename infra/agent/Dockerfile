FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends iptables && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi==0.115.6 uvicorn==0.34.0
WORKDIR /app
COPY agent.py .
CMD ["uvicorn", "agent:app", "--host", "0.0.0.0", "--port", "8002"]
