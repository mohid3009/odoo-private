# Backend-only image for Render (the React app is deployed separately on Vercel, which proxies /api here).
FROM python:3.12-slim
ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY . ./
RUN python manage.py collectstatic --noinput
EXPOSE 8000
# migrate on boot (idempotent), then serve on Render's $PORT
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi -b 0.0.0.0:${PORT:-8000} --workers 3 --access-logfile -"]
