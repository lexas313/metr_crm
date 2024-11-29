from datetime import timedelta

from django.core.files import File
from django.core.management import BaseCommand, call_command
from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
import os
from metrouchet_crm.models import Order, District, Address, Service, Client
from django.conf import settings

class Command(BaseCommand):
    help = 'Load test data into database'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        self.stdout.write('Загрузка данных...')
        call_command('loaddata', 'metrouchet_crm/fixtures/initial_data.json')

        # Добавляем районы
        with open(os.path.join(settings.BASE_DIR, 'metrouchet_crm', 'fixtures', 'districts.txt'), 'r', encoding='utf-8') as file:
            for line in file:
                district_name = line.strip()
                if district_name:
                    District.objects.create(district=district_name)

        # Получаем районы
        district1 = District.objects.get(pk=4)
        district2 = District.objects.get(pk=101)
        # Получаем адреса
        addres1 = Address.objects.get(pk=1)
        addres1.district = district1
        addres1.save()

        addres2 = Address.objects.get(pk=2)
        addres2.district = district2
        addres2.save()

        # Получаем услугу
        service1 = Service.objects.get(pk=1)
        service2 = Service.objects.get(pk=2)

        # Получаем клинта
        client1 = Client.objects.get(pk=1)
        client2 = Client.objects.get(pk=2)

        # Создаем 1ю заявку
        order1 = get_object_or_404(Order, pk=1)
        order1.service.add(service1)
        order1.client.add(client1)

        # Устанавливаем текущую дату создания рецепта
        order1.date_of_creation = timezone.now()
        order1.execution_date = timezone.now() + timedelta(days=2)
        order1.save()  # Сохраняем изменения в базе данных


        # Создаем 2ю заявку
        order2 = get_object_or_404(Order, pk=2)
        order2.service.add(service2)
        order2.client.add(client2)

        # Устанавливаем дату
        order2.date_of_creation = timezone.now()
        order2.execution_date = timezone.now() + timedelta(days=2)
        order2.save()  # Сохраняем изменения в базе данных


        # Статус загрузки
        self.stdout.write('Загрузка завершена успешно!')
