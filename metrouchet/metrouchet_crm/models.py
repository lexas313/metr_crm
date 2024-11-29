from django.db import models
from django.contrib.auth.models import User
from decimal import Decimal
from simple_history.models import HistoricalRecords
from transliterate import translit
from django.db.models.signals import pre_save
from django.dispatch import receiver


class WaterPhoto(models.Model):
    CHOICES = [
        ('', '---------'),  # Добавьте пустой выбор в начало списка
        ('ХВ', 'ХВС'),
        ('ГВ', 'ГВС')
    ]

    cold_or_hot = models.CharField(max_length=2, verbose_name='Холодный или горячий', choices=CHOICES)
    water_photo = models.ImageField(upload_to='photos/%Y/%m/%d/', default=None, blank=True, null=True, verbose_name='Фото счетчика')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Фото счетчика'
        verbose_name_plural = 'Фото счетчиков'


@receiver(pre_save, sender=WaterPhoto)
def transliterate_water_photo_filename(sender, instance, **kwargs):
    # Транслитерация имени файла перед сохранением
    if instance.water_photo:
        filename = instance.water_photo.name
        transliterated_filename = translit(filename, 'ru', reversed=True)
        instance.water_photo.name = transliterated_filename


class DocumentPhoto(models.Model):
    document_photo = models.ImageField(upload_to='photos/%Y/%m/%d/', default=None, blank=True, null=True, verbose_name='Фото документа')
    history = HistoricalRecords()

    class Meta:
        verbose_name = 'Фото документа'
        verbose_name_plural = 'Фото документа'


@receiver(pre_save, sender=DocumentPhoto)
def transliterate_document_photo_filename(sender, instance, **kwargs):
    # Транслитерация имени файла перед сохранением
    if instance.document_photo:
        filename = instance.document_photo.name
        transliterated_filename = translit(filename, 'ru', reversed=True)
        instance.document_photo.name = transliterated_filename


class Status(models.Model):
    status = models.CharField(max_length=15, verbose_name='Статус', blank=True)

    def __str__(self):
        return f'{self.status}'

    class Meta:
        verbose_name = 'Статус заказа'
        verbose_name_plural = 'Статусы заказа'


class OrderHistory(models.Model):
    order = models.ForeignKey('Order', on_delete=models.CASCADE, related_name='history_entries', verbose_name='Заказ')
    date_added = models.DateTimeField(auto_now_add=True, verbose_name='Дата добавления')
    change_description = models.TextField(verbose_name='Описание изменения')

    def __str__(self):
        return f'{self.order} - {self.date_added}'

    class Meta:
        verbose_name = 'История изменений заказа'
        verbose_name_plural = 'История изменений заказов'


class WaterName(models.Model):
    water_name = models.CharField(max_length=64, verbose_name='Модель счетчиков')
    water_price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Цена счетчика с заменой")
    history = HistoricalRecords()

    def __str__(self):
        return f'Модель счетчика: {self.water_name}, Цена: {self.water_price}'

    class Meta:
        verbose_name = 'Модель счетчика'
        verbose_name_plural = 'Модели счетчиков'


class CompanyService(models.Model):
    company_service = models.CharField(max_length=64, verbose_name='Услуги компании')
    service_price = models.PositiveIntegerField(verbose_name="Цена услуги", null=True)
    history = HistoricalRecords()

    def __str__(self):
        return '%s' % (self.company_service,)

    class Meta:
        verbose_name = 'Услуга компании'
        verbose_name_plural = 'Услуги компании'


class Service(models.Model):
    service_name = models.ForeignKey(CompanyService, on_delete=models.SET_NULL, null=True, verbose_name='Услуга', blank=True)
    water_name = models.ForeignKey(WaterName, on_delete=models.SET_NULL, null=True, verbose_name='Модель счетчиков', blank=True)
    cold_water = models.PositiveIntegerField(verbose_name="Холодных счетчиков", blank=True, default=0)
    hot_water = models.PositiveIntegerField(verbose_name="Горячих счетчиков", blank=True, default=0)
    price = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Сумма", blank=True)
    payment_master = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), verbose_name="Оплата мастеру", blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return f'{self.water_name}, {self.service_name}, (Холодных счетчиков: {self.cold_water}, Горячих счетчиков: {self.hot_water}), Сумма: {self.price}, Оплата мастеру: {self.payment_master}'

    class Meta:
        verbose_name = 'Услуга'
        verbose_name_plural = 'Услуги'

    def total_water(self):
        # Считаем сумму счетчиков
        return self.cold_water + self.hot_water


class District(models.Model):
    district = models.CharField(max_length=64, verbose_name='Район')

    def __str__(self):
        return f'{self.district}'


class Address(models.Model):
    district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, verbose_name='Район', blank=True)
    street_house = models.CharField(max_length=255, verbose_name='Улица', null=True, blank=True)
    apartment = models.PositiveIntegerField(verbose_name="Квартира", null=True, blank=True)
    entrance = models.PositiveIntegerField(verbose_name="Подъезд", null=True, blank=True)
    floor = models.PositiveIntegerField(verbose_name="Этаж", null=True, blank=True)
    intercom = models.CharField(max_length=24, verbose_name='Домофон', null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        return '%s' % (self.street_house,)

    class Meta:
        verbose_name = 'Адрес'
        verbose_name_plural = 'Адреса'

    def format_change_history(self, history_instance):
        return (
            f'Дата изменения: {history_instance.history_date},\n'
            f'Поле: Улица,\n'
            f'Старое значение: {history_instance.prev_record.street_house},\n'
            f'Новое значение: {history_instance.street_house}'
        )


class Client(models.Model):
    phone = models.CharField(max_length=20, verbose_name='Телефон')
    client_name = models.CharField(max_length=100, verbose_name='ФИО клиента')
    history = HistoricalRecords()

    def __str__(self):
        return '%s %s' % (self.phone, self.client_name)

    class Meta:
        verbose_name = 'Клиент'
        verbose_name_plural = 'Клиенты'


class Order(models.Model):
    author = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, verbose_name='Принял', blank=True)
    date_of_creation = models.DateTimeField(auto_now_add=True, verbose_name='Дата создания')
    execution_date = models.DateField(verbose_name='Дата исполнения', null=True)
    start_time = models.TimeField(verbose_name='Время от', null=True, blank=True)
    end_time = models.TimeField(verbose_name='Время до', null=True, blank=True)
    address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, verbose_name='Адрес клиента', blank=True)
    master = models.ForeignKey(User, on_delete=models.SET_NULL, related_name='master', null=True, verbose_name='Мастер', blank=True)
    client = models.ManyToManyField(Client, verbose_name='Клиент', blank=True)
    service = models.ManyToManyField(Service, verbose_name='Услуга', blank=True)
    comments = models.TextField(verbose_name='Комментарий', null=True, blank=True)
    status = models.ForeignKey(Status, on_delete=models.SET_NULL, null=True, verbose_name='Статус', blank=True)
    water_photo = models.ManyToManyField(WaterPhoto, verbose_name='Фото счетчика', blank=True, default=None)
    document_photo = models.ManyToManyField(DocumentPhoto, verbose_name='Фото документа', blank=True, default=None)
    comments_masters = models.TextField(verbose_name='Комментарий мастера', null=True, blank=True)
    history = HistoricalRecords()

    def __str__(self):
        services_str = ", ".join(str(service) for service in self.service.all())
        return f'Дата исполнения: {self.execution_date}, Адрес клиента: {self.address}, Услуга: {services_str}'

    class Meta:
        verbose_name = 'Заявка'
        verbose_name_plural = 'Заявки'

    def total_price(self):
        # Считаем сумму цен всех услуг в заказе
        total = 0
        for service in self.service.all():
            total += service.price
        return total

    def total_payment_master(self):
        # Считаем сумму оплаты мастеру
        total = 0
        for service in self.service.all():
            total += service.payment_master
        return total