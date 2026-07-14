FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt classroom_monitor/requirements.txt
RUN pip install --no-cache-dir -r classroom_monitor/requirements.txt
COPY . /app/
ENV PYTHONPATH=/app
EXPOSE 8080
CMD ["python3", "classroom_monitor/run_server.py"]
