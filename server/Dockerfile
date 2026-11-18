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
# 액션 배틀의 웹 화면 (2.6.0) - 서버가 /action/play 로 내보낸다 (config.ACTION_WEB)
COPY server/web /app/web

EXPOSE 8080
# Render 같은 곳은 PORT 로 포트를 알려준다. 없으면 8080 을 쓴다.
# (도커 컴포즈로 직접 띄울 때는 PORT 가 없으므로 그대로 8080 이다)
# --ws-max-size: 웹소켓 한 줄은 1MB 까지 (uvicorn 기본은 16MB). 앱 · 웹 화면이 보내는 줄은 다 1KB 도 안 된다 -
#   압축해 보낸 큰 줄을 풀어 읽느라 메모리 · 이벤트 루프를 붙잡지 않게 (/ws/action 은 입장권 줄도 MSG_MAX 로 거른다).
ENV PORT=8080
CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8080} --ws-max-size 1048576"]
