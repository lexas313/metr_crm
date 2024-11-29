FROM python:3.10-slim

# Установите необходимые системы зависимости
RUN apt-get update && apt-get install -y gcc build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/*  # Удаляем кэш apt для уменьшения размера образа

ENV PYTHONUNBUFFERED=1

RUN mkdir app
WORKDIR /app

COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

COPY . /app/
COPY .env.docker /app/.env

# CMD python manage.py runserver 0.0.0.0:8000
# CMD ["gunicorn", "--bind", "0.0.0.0:8000", "culinary_heaven.wsgi:application"]

CMD python manage.py makemigrations \
    && python manage.py migrate \
    && python manage.py shell -c "from django.contrib.auth import get_user_model; User = get_user_model(); User.objects.filter(username='root').exists() or User.objects.create_superuser('root', 'root@example.com', 'root')" \
    && python manage.py load_test_data \
    && python manage.py collectstatic --no-input \
    && gunicorn metrouchet.wsgi:application --bind 0.0.0.0:8000