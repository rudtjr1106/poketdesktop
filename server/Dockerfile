# 빌드 컨텍스트는 저장소 루트다 (common/ 을 같이 넣어야 해서).
#   docker compose build   또는   docker build -f server/Dockerfile .
FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONIOENCODING=utf-8

WORKDIR /app

COPY server/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY common /app/common
COPY server/app /app/app
COPY server/data /app/data

EXPOSE 8080
# Render 같은 곳은 PORT 로 포트를 알려준다. 없으면 8080 을 쓴다.
# (도커 컴포즈로 직접 띄울 때는 PORT 가 없으므로 그대로 8080 이다)
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080}"]
