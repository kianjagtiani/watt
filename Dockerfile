FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY assistant/ assistant/
ENV DB_PATH=/data/assistant.db
VOLUME /data
EXPOSE 8000
CMD ["python", "-m", "assistant.serve"]
