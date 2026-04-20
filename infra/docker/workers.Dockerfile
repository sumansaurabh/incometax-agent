FROM python:3.11-slim
WORKDIR /app
COPY apps/workers /app/apps/workers
CMD ["python", "-c", "print('workers-ready')"]
