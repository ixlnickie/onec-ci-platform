FROM python:3.12-slim

WORKDIR /app
COPY app.py /app/app.py

RUN useradd --system --uid 10001 app
USER 10001

ENV PYTHONUNBUFFERED=1 \
    PORT=8099

EXPOSE 8099

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD python3 -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8099/health', timeout=3).status == 200 else 1)"

CMD ["python3", "/app/app.py"]
