from _decimal import Decimal
from django.shortcuts import render, redirect
from django.utils import timezone
from .models import Order, Client, Service, WaterName, CompanyService, OrderHistory, Status, District
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from .forms import OrderForm, AuthUserForm, RegisterUserForm, ClientFormSet, AddressForm, ServiceFormSet,\
    OrderFilterForm, WaterPhotoFormSet, DocumentPhotoFormSet, CompanyServiceForm, WaterNameForm, StatusForm, \
    OrderCountFilterForm, DistrictForm, DistrictListForm
from django.urls import reverse_lazy
from django.contrib import messages
from django.contrib.auth.views import LoginView, LogoutView
from django.contrib.auth.models import User
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from itertools import tee
from django.db.models import Count, Q, F, Value, Case, When
from datetime import datetime, date, timedelta
from django.db.models import Sum
from django.views.decorators.http import require_POST
from django.shortcuts import get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from .forms import ExcelImportForm
import pandas as pd
from django.http import Http404
from django.db import models
from django.views.generic.edit import FormView
from django.utils.timezone import now
import telegram
from django.conf import settings
import asyncio
from django.core.paginator import Paginator


class CustomSuccessMessageMixin:  # Класс для отображения сообщений (добавлена, удалена, изменина, ...)
    @property
    def success_msg(self):
        return False

    def form_valid(self, form):
        messages.success(self.request, self.success_msg)
        return super().form_valid(form)


def is_manager_or_superuser(user):  # Функция для запрета доступа на страницу всем кроме Менеджеров и Суперпользователя
    return user.groups.filter(name__in=['Менеджер']).exists() or user.is_superuser


def is_superuser(user):
    return user.is_authenticated and user.is_superuser


# Телеграм бот
async def send_telegram_message(message):
    if settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID:
        bot = telegram.Bot(token=settings.TELEGRAM_BOT_TOKEN)
        await bot.send_message(chat_id=settings.TELEGRAM_CHAT_ID, text=message)


class TodayOrdersListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'data-base.html'
    context_object_name = 'list_orders'
    login_url = 'login'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            queryset = Order.objects.all()
        else:
            queryset = Order.objects.filter(master=user)

        return queryset.filter(execution_date=date.today()).order_by('-execution_date', 'start_time', 'end_time',
                                                                     'address__district__district')


class TomorrowOrdersListView(LoginRequiredMixin, ListView):
    model = Order
    template_name = 'data-base.html'
    context_object_name = 'list_orders'
    login_url = 'login'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            queryset = Order.objects.all()
        else:
            queryset = Order.objects.filter(master=user)

        return queryset.filter(execution_date=date.today() + timedelta(days=1)).order_by('-execution_date',
                                                                                         'start_time', 'end_time',
                                                                                         'address__district__district')


class AllOrdersListView(LoginRequiredMixin, ListView):
    paginate_by = 20
    model = Order
    template_name = 'data-base.html'
    context_object_name = 'list_orders'
    login_url = 'login'

    def get_queryset(self):
        user = self.request.user
        if user.is_superuser:
            queryset = Order.objects.all()
        else:
            queryset = Order.objects.filter(master=user)

        return queryset.order_by('-execution_date', 'start_time', 'end_time', 'address__district__district')


class DetailsListView(LoginRequiredMixin, UpdateView):  # Детали заявки
    model = Order
    template_name = 'details.html'
    context_object_name = 'get_orders'
    form_class = OrderForm
    login_url = 'login'  # перенаправление на страницу входа, если пользователь не авторизован

    def get_object(self, queryset=None):
        """Переопределяем метод для получения объекта,
        проверяя, принадлежит ли он текущему пользователю."""
        obj = super(DetailsListView, self).get_object(queryset=queryset)
        if self.request.user.is_superuser or obj.master == self.request.user:
            return obj
        else:
            raise Http404("У вас нет доступа к этой заявке.")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = Status.objects.all()
        context['editing'] = True  # Устанавливаем значение True по умолчанию
        current_order = Order.objects.get(pk=self.object.pk)
        current_order = current_order.execution_date
        # Проверяем условия для установки значения False
        if not self.request.user.is_superuser and current_order:
            # Проверяем, что с момента execution_date прошло больше двух дней для обычного пользователя (не суперпользователя)
            if (now().date() - current_order).days > 2:
                context['editing'] = False  # Обновляем контекст, выключаем возможность редактирования

        # Обновление данных формсета фотографий
        if self.request.POST:
            context['water_photo_formset'] = WaterPhotoFormSet(
                self.request.POST, self.request.FILES, queryset=self.object.water_photo.all(), prefix='water_photo_form'
            )
            context['document_photo_formset'] = DocumentPhotoFormSet(
                self.request.POST, self.request.FILES, queryset=self.object.document_photo.all(), prefix='document_photo_form'
            )
        else:
            context['water_photo_formset'] = WaterPhotoFormSet(
                queryset=self.object.water_photo.all(), prefix='water_photo_form'
            )
            context['document_photo_formset'] = DocumentPhotoFormSet(
                queryset=self.object.document_photo.all(), prefix='document_photo_form'
            )
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        water_photo_formset = context['water_photo_formset']
        document_photo_formset = context['document_photo_formset']
        editing = context['editing']
        # Здесь мы перед сохранением получаем текущий объект из базы данных.
        current_order = Order.objects.get(pk=self.object.pk)

        # Для каждого поля, которое не представлено в форме, но должно сохранить своё текущее значение,
        # мы устанавливаем это значение из текущего объекта заказа:

        if 'execution_date' not in self.request.POST:
            form.instance.execution_date = current_order.execution_date
        if 'start_time' not in self.request.POST:
            form.instance.start_time = current_order.start_time
        if 'end_time' not in self.request.POST:
            form.instance.end_time = current_order.end_time
        if 'comments' not in self.request.POST:
            form.instance.comments = current_order.comments
        if 'comments_masters' not in self.request.POST:
            form.instance.comments_masters = current_order.comments_masters
        if 'master' not in self.request.POST:
            form.instance.master = current_order.master

        # Если прошло больше 2-х дней, все кроме суперползователя не смогут редактировать заявки
        if not editing:
            return self.handle_no_permission()

        if form.is_valid() and water_photo_formset.is_valid() and document_photo_formset.is_valid():
            # Присваиваем формсету water_photo_formset текущий заказ
            water_photo_formset.instance = self.object

            # Сохраняем связанные объекты WaterPhoto
            water_photo_formset.save()

            # Присваиваем формсету document_photo_formset текущий заказ
            document_photo_formset.instance = self.object

            # Сохраняем связанные объекты DocumentPhoto
            document_photo_formset.save()

            form.save()


            # Отправить уведомление в Telegram
            order_status = form.cleaned_data.get("status")
            order_id = current_order.id
            order_address = current_order.address.street_house
            order_apartment = current_order.address.apartment
            message = f'{order_status}! № {order_id}\nадрес: {order_address}, кв {order_apartment}'
            asyncio.run(send_telegram_message(message))  # Вызываем асинхронную функцию внутри asyncio.run


            water_photo_for_deletion = water_photo_formset.deleted_forms
            for water_photo_form in water_photo_for_deletion:

                # Удаляем связь счетчика с текущим заказом
                self.object.water_photo.remove(water_photo_form.instance)

            water_photo_for_saving = water_photo_formset.save(commit=False)
            for water_photo in water_photo_for_saving:
                # Сохраним каждое фото, если оно новое или было изменено
                water_photo.save()

                # Добавляем связь счетчика с текущим заказа
                self.object.water_photo.add(water_photo)


            document_photo_for_deletion = document_photo_formset.deleted_forms
            for document_photo_form in document_photo_for_deletion:

                # Удаляем связь документа с текущим заказом
                self.object.document_photo.remove(document_photo_form.instance)

            document_photo_for_saving = document_photo_formset.save(commit=False)
            for document_photo in document_photo_for_saving:
                # Сохраним каждое фото документа, если оно новое или было изменено
                document_photo.save()

                # Добавляем связь документа с текущим заказа
                self.object.document_photo.add(document_photo)

            return redirect('today_orders')
        else:
            return self.form_invalid(form)


@login_required
@require_POST
def update_master(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    master_id = request.POST.get('master')  # Значение из POST-запроса

    if master_id:
        user = User.objects.filter(groups__name__icontains='Мастер')
        master = get_object_or_404(user, pk=master_id)
        order.master = master
    else:
        order.master = None

    order.save()

    return JsonResponse({'status': 'ok'})


@login_required
@require_POST
def update_status(request, order_id):
    order = get_object_or_404(Order, pk=order_id)
    status_id = request.POST.get('status')  # Значение из POST-запроса

    if status_id:  # Если status_id не пустой
        status = get_object_or_404(Status, pk=status_id)
        order.status = status
    else:  # Если status_id пустой, устанавливаем статус заказа как None
        order.status = None

    order.save()

    # Возвращаем JSON-ответ без окна подтверждения
    return JsonResponse({'status': order.status.status})


class OrderEditView(LoginRequiredMixin, UserPassesTestMixin, CustomSuccessMessageMixin, CreateView):
    model = Order
    template_name = 'all-orders.html'
    form_class = OrderForm
    success_url = reverse_lazy('all-orders')
    success_msg = 'Заявка добавлена'
    login_url = 'login'  # перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):  # Проверка удовлетворяет ли пользователь условиям функции is_manager_or_superuser(user)
        return is_manager_or_superuser(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['statuses'] = Status.objects.all()
        context['masters'] = User.objects.filter(groups__name__icontains='Мастер')
        form = OrderFilterForm(self.request.GET)  # Используем GET-параметры для инициализации формы
        context['form'] = form
        # context['list_orders'] = self.get_filtered_orders(form)

        # Получаем отфильтрованный список заявок
        filtered_orders = self.get_filtered_orders(form)

        # Пагинация
        paginator = Paginator(filtered_orders, 25)  # Например, 10 заявок на страницу
        page = self.request.GET.get('page')
        context['list_orders'] = paginator.get_page(page)

        # Текущая дата
        today = timezone.now().date()
        context['today'] = today

        return context


    def get_filtered_orders(self, form):
        orders = Order.objects.all().order_by('-execution_date', 'start_time', 'end_time', 'address__district__district')

        if form.is_valid():
            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            master = form.cleaned_data.get('master')
            search_query = form.cleaned_data.get('search')

            if start_date:
                orders = orders.filter(execution_date__gte=start_date)
            if end_date:
                orders = orders.filter(execution_date__lte=end_date)
            if master:
                orders = orders.filter(master=master)

            # Добавьте обработку других критериев фильтрации здесь

            if search_query:
                orders = orders.filter(
                    Q(client__client_name__icontains=search_query) |  # Поиск по имени клиента
                    Q(client__phone__icontains=search_query) |  # Поиск по номеру телефона клиента
                    Q(address__street_house__icontains=search_query) |  # Поиск по улице
                    Q(service__service_name__company_service__icontains=search_query) |  # Поиск по названию услуги
                    Q(comments__icontains=search_query)  # Поиск в коменатиях
                    # Добавьте дополнительные поля для поиска по другим моделям
                )

            # Фильтрация уникальных записей на уровне Python
            unique_orders = {order.id: order for order in orders}
            unique_orders = list(unique_orders.values())

        return unique_orders

    def form_valid(self, form):
        self.object = form.save(commit=False)
        self.object.author = self.request.user
        self.object.save()
        return super().form_valid(form)


# Функция для создания zip объекта из функции check_delta_for_poll(order)
def pair_iterable_for_delta_changes(iterable):
    a, b = tee(iterable)
    next(b, None)
    return zip(a, b)

# Функция для отображения истории изменений заявки (старое и новое значение)
def check_delta_for_order(order):
    if order is None:
        return []
    field_name = {'water_name': 'Модель счетчиков', 'service_name': 'Услуга', 'cold_water': 'Холодных счетчиков',
                  'hot_water': 'Горячих счетчиков', 'price': 'Сумма', 'payment_master': 'Оплата мастеру', 'district': 'Район',
                  'street_house': 'Улица', 'apartment': 'Квартира', 'entrance': 'Подъезд', 'floor': 'Этаж', 'intercom': 'Домофон',
                  'phone': 'Телефон', 'client_name': 'ФИО клиента', 'execution_date': 'Дата исполнения', 'master': 'Мастер',
                  'address': 'Адрес клиента', 'comments': 'Комментарий', 'status': 'Статус заказа', 'start_time': 'Время от',
                  'end_time': 'Время до', 'comments_masters': 'Комментарий мастера'}

    poll_iterator = order.history.all().order_by('history_date').iterator()
    history_list = []
    for record_pair in pair_iterable_for_delta_changes(poll_iterator):
        old_record, new_record = record_pair
        delta = new_record.diff_against(old_record)
        for change in delta.changes:
            if change.field != 'address':

                if change.field == 'status':
                    old_status = Status.objects.filter(pk=change.old).first()
                    new_status = Status.objects.filter(pk=change.new).first()
                    field_name_value = field_name[change.field]
                    old_value = str(old_status) if old_status else None
                    new_value = str(new_status) if new_status else None

                elif change.field == 'master':
                    old_user = User.objects.filter(pk=change.old).first()
                    new_user = User.objects.filter(pk=change.new).first()
                    field_name_value = field_name[change.field]
                    old_value = str(old_user.get_full_name()) if old_user else None
                    new_value = str(new_user.get_full_name()) if new_user else None

                elif change.field == 'district':
                    old_user = District.objects.filter(pk=change.old).first()
                    new_user = District.objects.filter(pk=change.new).first()
                    field_name_value = field_name[change.field]
                    old_value = str(old_user) if old_user else None
                    new_value = str(new_user) if new_user else None

                elif change.field == 'service_name':
                    old_user = CompanyService.objects.filter(pk=change.old).first()
                    new_user = CompanyService.objects.filter(pk=change.new).first()
                    field_name_value = field_name[change.field]
                    old_value = str(old_user) if old_user else None
                    new_value = str(new_user) if new_user else None

                else:
                    field_name_value = field_name.get(change.field, change.field)
                    old_value = change.old
                    new_value = change.new

                hist = [new_record.history_date, field_name_value, old_value, new_value]
                history_list.append(hist)

    return history_list


class OrdersUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Order
    template_name = 'update.html'
    form_class = OrderForm
    context_object_name = 'get_orders'
    login_url = 'login'  # перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):  # Проверка удовлетворяет ли пользователь условиям функции is_manager_or_superuser(user)
        return is_manager_or_superuser(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['client_formset'] = ClientFormSet(self.request.POST, queryset=self.object.client.all(),
                                                      prefix='client_form')
            context['address_form'] = AddressForm(self.request.POST, instance=self.object.address,
                                                  prefix='address_form')
            context['service_formset'] = ServiceFormSet(self.request.POST, queryset=self.object.service.all(),
                                                        prefix='service_form')
            context['water_photo_formset'] = WaterPhotoFormSet(
                self.request.POST, self.request.FILES, queryset=self.object.water_photo.all(), prefix='water_photo_form'
            )
            context['document_photo_formset'] = DocumentPhotoFormSet(
                self.request.POST, self.request.FILES, queryset=self.object.document_photo.all(),
                prefix='document_photo_form'
            )

        else:
            context['client_formset'] = ClientFormSet(queryset=self.object.client.all(), prefix='client_form')
            context['address_form'] = AddressForm(instance=self.object.address, prefix='address_form')
            context['service_formset'] = ServiceFormSet(queryset=self.object.service.all(), prefix='service_form')
            context['water_photo_formset'] = WaterPhotoFormSet(
                queryset=self.object.water_photo.all(), prefix='water_photo_form'
            )
            context['document_photo_formset'] = DocumentPhotoFormSet(
                queryset=self.object.document_photo.all(), prefix='document_photo_form'
            )

        # Получение объекта Order
        order = self.object

        # Получение истории изменений для основной модели Order
        order_history = check_delta_for_order(order)

        # Получение истории изменений для связанных моделей
        address_history = check_delta_for_order(order.address if order.address else None)

        # История изменения клиентов
        clients_history = []
        for client in order.client.all():
            clients_history.extend(check_delta_for_order(client))

        # История изменения услуг
        services_history = []
        for service in order.service.all():
            services_history.extend(check_delta_for_order(service))

        # История изменения фото счетчиков
        water_photo_history = []
        for water_photo in order.water_photo.all():
            water_photo_history.extend(check_delta_for_order(water_photo))

        # История изменения фото документов
        document_photo_history = []
        for document_photo in order.document_photo.all():
            document_photo_history.extend(check_delta_for_order(document_photo))

        # Получение всех исторических записей добавления новых услуг и клиентов для заказа
        order_history_entries = OrderHistory.objects.filter(order=self.object)

        # Объединение всех изменений и исторических записей (добавление и удаление клиентов и услуг)
        all_changes_and_entries = order_history + address_history + clients_history + services_history\
                                  + water_photo_history + document_photo_history + list(order_history_entries)

        # Сортировка всех изменений и исторических записей по дате в обратном хронологическом порядке
        all_changes_and_entries = sorted(all_changes_and_entries, key=lambda x: x[0] if isinstance(x, (list, tuple)) else x.date_added, reverse=True)

        # Добавление отсортированных изменений и исторических записей в контекст для использования в шаблоне
        context['all_changes'] = all_changes_and_entries

        return context

    def form_valid(self, form):
        context = self.get_context_data()
        client_formset = context['client_formset']
        address_form = context['address_form']
        service_formset = context['service_formset']
        water_photo_formset = context['water_photo_formset']
        document_photo_formset = context['document_photo_formset']

        if form.is_valid() and client_formset.is_valid() and address_form.is_valid() and service_formset.is_valid() \
                and water_photo_formset.is_valid() and document_photo_formset.is_valid():
            # Присваиваем формсету текущий заказ
            form.instance = self.object
            self.object = form.save()

            clients_for_deletion = client_formset.deleted_forms
            for client_form in clients_for_deletion:
                # Создаем историческую запись для удаленного клиента
                history_entry = OrderHistory(
                    order=self.object,
                    date_added=datetime.now(),
                    change_description=f"Клиент удален: Имя: {client_form.cleaned_data['client_name']}, Тел.: {client_form.cleaned_data['phone']}"
                )
                history_entry.save()
                # Удаляем связь клиента с текущим заказом
                self.object.client.remove(client_form.instance)

            clients_for_saving = client_formset.save(commit=False)
            for client in clients_for_saving:
                # Сохраним каждого клиента, если он новый или был изменён
                client.save()

                if not self.object.client.filter(pk=client.pk).exists():
                    # Создаем историческую запись для заказа, отражающую добавление клиента
                    history_entry = OrderHistory(
                        order=self.object,
                        date_added=datetime.now(),
                        change_description=f"Добавлен клиент: Имя: {client.client_name} Тел.: {client.phone}"
                    )
                    history_entry.save()

                # Добавляем связь клиента с текущим заказа
                self.object.client.add(client)

            service_for_deletion = service_formset.deleted_forms
            for service_form in service_for_deletion:
                # Создаем историческую запись для удаленного заказа
                history_entry = OrderHistory(
                    order=self.object,
                    date_added=datetime.now(),
                    change_description=f"Услуга удалена: {service_form.cleaned_data['service_name']}, Сумма: {service_form.cleaned_data['price']} р."
                )
                history_entry.save()
                # Удаляем связь услуги с текущим заказом
                self.object.service.remove(service_form.instance)

            service_for_saving = service_formset.save(commit=False)
            for service in service_for_saving:
                print(
                    f'Service before save: hot_water={service.hot_water}, cold_water={service.cold_water}, price={service.price}')
                # Сохраним каждую услугу, если она новая или была изменена
                service.save()

                if not self.object.service.filter(pk=service.pk).exists():
                    # Создаем историческую запись для заказа, отражающую добавление клиента
                    history_entry = OrderHistory(
                        order=self.object,
                        date_added=datetime.now(),
                        change_description=f"Добавлена услуга: {service.service_name} Сумма: {service.price} р."
                    )
                    history_entry.save()

                # Добавляем связь услуги с текущим заказом
                self.object.service.add(service)

            water_photo_for_deletion = water_photo_formset.deleted_forms
            for water_photo_form in water_photo_for_deletion:
                # Удаляем связь счетчика с текущим заказом
                self.object.water_photo.remove(water_photo_form.instance)

            water_photo_for_saving = water_photo_formset.save(commit=False)
            for water_photo in water_photo_for_saving:
                # Сохраним каждое фото, если оно новое или было изменено
                water_photo.save()

                # Добавляем связь счетчика с текущим заказа
                self.object.water_photo.add(water_photo)

            document_photo_for_deletion = document_photo_formset.deleted_forms
            for document_photo_form in document_photo_for_deletion:
                # Удаляем связь документа с текущим заказом
                self.object.document_photo.remove(document_photo_form.instance)

            document_photo_for_saving = document_photo_formset.save(commit=False)
            for document_photo in document_photo_for_saving:
                # Сохраним каждое фото документа, если оно новое или было изменено
                document_photo.save()

                # Добавляем связь документа с текущим заказа
                self.object.document_photo.add(document_photo)

            address = address_form.save()
            self.object.address = address
            self.object.save()

            return redirect('all-orders')
        else:
            return self.form_invalid(form)


class OrderDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Order
    template_name = 'all-orders.html'
    success_url = reverse_lazy('all-orders')  # Убедитесь, что в urlpatterns у вас есть имя 'all-orders'
    success_msg = 'Заявка удалена'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Сообщение об успешном удалении
        order = self.get_object()
        messages.success(self.request, f'Заявка № {order.id} удалена')
        return super(OrderDeleteView, self).form_valid(form)

    def get_success_url(self):
        # Вы можете использовать метод, чтобы динамически определить success_url
        return self.success_url


# Функция для автозаполнения имени клиента по номеру телефона
def get_client_name(request):
    phone_number = request.GET.get('phone', None)
    data = {
        'client_name': ""  # начальное значение - пустая строка
    }
    # Поиск всех клиентов с заданным номером телефона
    clients = Client.objects.filter(phone=phone_number)
    # Если найден хотя бы один клиент
    if clients:
        # Берем имя первого клиента из списка
        data['client_name'] = clients.first().client_name
    else:
        # Или можно оставить пустое или вернуть сообщение о том, что клиент не найден
        data['client_name'] = ""
    return JsonResponse(data)


class OrderCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Order
    form_class = OrderForm
    address_form_class = AddressForm
    template_name = 'create.html'
    success_url = reverse_lazy('all-orders')
    login_url = 'login'  # перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):  # Проверка удовлетворяет ли пользователь условиям функции is_manager_or_superuser(user)
        return is_manager_or_superuser(self.request.user)

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if self.request.POST:
            context['client_formset'] = ClientFormSet(self.request.POST, prefix='client_form')
            context['address_form'] = self.address_form_class(self.request.POST, prefix='address_form')
            context['service_formset'] = ServiceFormSet(self.request.POST, prefix='service_form')
        else:
            context['client_formset'] = ClientFormSet(queryset=Client.objects.none(), prefix='client_form')
            context['address_form'] = self.address_form_class(prefix='address_form')
            context['service_formset'] = ServiceFormSet(queryset=Service.objects.none(), prefix='service_form')
        return context

    def form_valid(self, form):
        context = self.get_context_data()
        client_formset = context['client_formset']
        address_form = context['address_form']
        service_formset = context['service_formset']

        if form.is_valid() and client_formset.is_valid() and address_form.is_valid() and service_formset.is_valid():
            form.instance.author = self.request.user
            self.object = form.save()

            for client_form in client_formset.forms:
                if client_form.cleaned_data:
                    client = Client.objects.create(
                        phone=client_form.cleaned_data['phone'],
                        client_name=client_form.cleaned_data['client_name']
                    )
                    self.object.client.add(client)

            for service_form in service_formset.forms:
                if service_form.cleaned_data:
                    service = Service.objects.create(
                        service_name=service_form.cleaned_data['service_name'],
                        water_name=service_form.cleaned_data['water_name'],
                        cold_water=service_form.cleaned_data['cold_water'],
                        hot_water=service_form.cleaned_data['hot_water'],
                        price=service_form.cleaned_data['price'],
                        payment_master=service_form.cleaned_data['payment_master']
                    )
                    self.object.service.add(service)

            address = address_form.save()
            self.object.address = address
            self.object.save()

            return super().form_valid(form)
        else:
            return self.form_invalid(form)


# Функция для подставления цены в поля Сумма
def get_water_price(request):
    water_name_id = request.POST.get('water_name_id')
    cold_water = float(request.POST.get('cold_water', 0))
    hot_water = float(request.POST.get('hot_water', 0))
    try:
        water_name = WaterName.objects.get(pk=water_name_id)
        water_price = water_name.water_price
        total_price = float(water_price) * (cold_water + hot_water)

    except WaterName.DoesNotExist:
        total_price = 0.00

    return JsonResponse({'water_price': total_price})


def get_service_price(request):
    service_id = request.POST.get('service_id')
    cold_water = float(request.POST.get('cold_water', 0))
    hot_water = float(request.POST.get('hot_water', 0))

    try:
        service_price = CompanyService.objects.get(pk=service_id).service_price
        total_price = service_price * (cold_water + hot_water)

        return JsonResponse({'service_price': total_price})

    except CompanyService.DoesNotExist:
        return JsonResponse({'error': 'CompanyService does not exist'}, status=404)

    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


class LoginUserView(LoginView):  # Авторизация пользователя
    template_name = 'login.html'
    form_class = AuthUserForm
    success_url = reverse_lazy('today_orders')

    def get_success_url(self):
        return self.success_url


class RegisterUserView(LoginRequiredMixin, UserPassesTestMixin,  CreateView):  # Регистрация пользователя
    model = User
    template_name = 'register_page.html'
    form_class = RegisterUserForm
    success_url = reverse_lazy('today_orders')
    success_msg = 'Пользователь создан'
    login_url = 'login'  # перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    # def get(self, request, *args, **kwargs):  # Запретить регистрацию пользоваетелей, кроме сеперюзера
    #     if not self.request.user.is_superuser:
    #         return self.handle_no_permission()
    #     self.object = None
    #     return super().get(request, *args, **kwargs)

    # def form_valid(self, form):  # Автоматическая авторизация после регистрации
    #
    #     # if not self.request.user.is_superuser:  # Запретить регистрацию пользоваетелей, кроме сеперюзера
    #     #     return self.handle_no_permission()
    #
    #     form_valid = super().form_valid(form)
    #     username = form.cleaned_data["username"]
    #     password = form.cleaned_data["password"]
    #     aut_user = authenticate(username=username, password=password)
    #     login(self.request, aut_user)
    #     return form_valid


class LogoutUserView(LogoutView):  # Выход пользователя
    next_page = reverse_lazy('login')


class CreateCompanyServiceView(LoginRequiredMixin, UserPassesTestMixin, CreateView):  # Создания услуг и цен компании
    model = CompanyService
    template_name = 'company-service-price.html'
    form_class = CompanyServiceForm
    # context_object_name = 'company_service'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company_service'] = CompanyService.objects.all()

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('company_service_price')
        else:
            return self.form_invalid(form)


class UpdateCompanyServiceView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):  # Редактирование услуг и цен компании
    model = CompanyService
    template_name = 'company-service-price.html'
    form_class = CompanyServiceForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['company_service_update'] = True

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('company_service_price')
        else:
            return self.form_invalid(form)


class DeleteCompanyServiceView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):  # Удаление услуг и цен компании
    model = CompanyService
    template_name = 'company-service-price.html'
    success_url = reverse_lazy('company_service_price')
    success_msg = 'Запись удалена'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Сообщение об успешном удалении
        order = self.get_object()
        messages.success(self.request, f'Услуга "{order.company_service}" удалена')
        return super(DeleteCompanyServiceView, self).form_valid(form)

    def get_success_url(self):
        # Вы можете использовать метод, чтобы динамически определить success_url
        return self.success_url


class CreateWaterNameView(LoginRequiredMixin, UserPassesTestMixin, CreateView):  # Создания модели счетчика и цены
    model = WaterName
    template_name = 'water-name.html'
    form_class = WaterNameForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['water_name'] = WaterName.objects.all()

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('water_name')
        else:
            return self.form_invalid(form)


class UpdateWaterNameView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):  # Редактирование модели счетчика и цены
    model = WaterName
    template_name = 'water-name.html'
    form_class = WaterNameForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['water_name_update'] = True

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('water_name')
        else:
            return self.form_invalid(form)


class DeleteWaterNameView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):  # Удаление модели счетчика и цены
    model = WaterName
    template_name = 'water-name.html'
    success_url = reverse_lazy('water_name')
    success_msg = 'Запись удалена'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Сообщение об успешном удалении
        order = self.get_object()
        messages.success(self.request, f'Счетчик "{order.water_name}" удален')
        return super(DeleteWaterNameView, self).form_valid(form)

    def get_success_url(self):
        # Вы можете использовать метод, чтобы динамически определить success_url
        return self.success_url


class CreateStatusView(LoginRequiredMixin, UserPassesTestMixin, CreateView):  # Создания статуса
    model = Status
    template_name = 'status-name.html'
    form_class = StatusForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_all'] = Status.objects.all()

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('status_name')
        else:
            return self.form_invalid(form)


class UpdateStatusView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):  # Редактирование статуса
    model = Status
    template_name = 'status-name.html'
    form_class = StatusForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_name_update'] = True

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('status_name')
        else:
            return self.form_invalid(form)


class DeleteStatusView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):  # Удаление статуса
    model = Status
    template_name = 'status-name.html'
    success_url = reverse_lazy('status_name')
    success_msg = 'Запись удалена'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Сообщение об успешном удалении
        order = self.get_object()
        messages.success(self.request, f'Статус "{order.status}" удален')
        return super(DeleteStatusView, self).form_valid(form)

    def get_success_url(self):
        # Вы можете использовать метод, чтобы динамически определить success_url
        return self.success_url


class CreateDistrictView(LoginRequiredMixin, UserPassesTestMixin, FormView):  # Создания района
    model = District
    template_name = 'districts.html'
    form_class = DistrictListForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['districts_all'] = District.objects.all()

        return context

    def form_valid(self, form):
        district_list = form.cleaned_data['district_list']
        # Допустим, что районы вводятся через новую строку
        districts = district_list.split('\n')

        # Допустим, у нас есть проверка на уникальность названий районов
        for district_name in districts:
            # Убираем пробелы и игнорируем пустые строки
            district_name = district_name.strip()
            if district_name and not District.objects.filter(district=district_name).exists():
                District.objects.create(district=district_name)

        return redirect('districts_name')  # Или другой URL, куда вы хотите перенаправить пользователя после добавления


class UpdateDistrictView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):  # Редактирование района
    model = District
    template_name = 'districts.html'
    form_class = DistrictForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_name_update'] = True

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('districts_name')
        else:
            return self.form_invalid(form)


class DeleteDistrictView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):  # Удаление района
    model = District
    template_name = 'districts.html'
    success_url = reverse_lazy('districts_name')
    success_msg = 'Запись удалена'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Сообщение об успешном удалении
        order = self.get_object()
        messages.success(self.request, f'Район "{order.district}" удален')
        return super(DeleteDistrictView, self).form_valid(form)

    def get_success_url(self):
        # Вы можете использовать метод, чтобы динамически определить success_url
        return self.success_url


class CreateUserView(LoginRequiredMixin, UserPassesTestMixin, CreateView):  # Создания пользователя
    model = User
    template_name = 'users.html'
    form_class = RegisterUserForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['users_all'] = User.objects.all()

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('users_name')
        else:
            return self.form_invalid(form)


class UpdateUserView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):  # Редактирование пользователя
    model = User
    template_name = 'users.html'
    form_class = RegisterUserForm
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['status_name_update'] = True

        return context

    def form_valid(self, form):
        if form.is_valid():
            form.save()
            return redirect('users_name')
        else:
            return self.form_invalid(form)


class DeleteUserView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):  # Удаление пользователя
    model = User
    template_name = 'users.html'
    success_url = reverse_lazy('users_name')
    success_msg = 'Запись удалена'
    login_url = 'login'  # Перенаправление на страницу входа, если пользователь не авторизован

    def test_func(self):
        # Доступ к удалению разрешен только для суперпользователей
        return self.request.user.is_superuser

    def form_valid(self, form):
        # Сообщение об успешном удалении
        order = self.get_object()
        messages.success(self.request, f'Пользователь "{order}" удален')
        return super(DeleteUserView, self).form_valid(form)

    def get_success_url(self):
        # Вы можете использовать метод, чтобы динамически определить success_url
        return self.success_url



# Класс для импорта файла в базу данных
@user_passes_test(is_superuser)
def import_excel(request):
    if request.method == 'POST':
        form = ExcelImportForm(request.POST, request.FILES)
        if form.is_valid():
            excel_file = request.FILES['excel_file']
            if excel_file.name.endswith('.xlsx') or excel_file.name.endswith('.xls'):
                try:
                    df = pd.read_excel(excel_file)

                    for index, row in df.iterrows():
                        Order.objects.create(
                            execution_date=row['execution_date'],
                            start_time=row['start_time'],
                            end_time=row['end_time'],
                            comments=row['comments'],
                            # Другие поля и их значения из файла Excel
                            # ...
                        )

                    messages.success(request, 'Файл успешно загружен.')
                except Exception as e:
                    error_message = str(e)
                    messages.error(request, f'Ошибка при импорте: {error_message}')
            else:
                messages.error(request, 'Пожалуйста, загрузите файл Excel (.xlsx или .xls)')

    else:
        form = ExcelImportForm()

    return render(request, 'import-excel.html', {'form': form})


class ProfileView(LoginRequiredMixin, ListView):
    model = User
    template_name = 'user-profile.html'

    def get_context_data(self, **kwargs):
        context = super(ProfileView, self).get_context_data(**kwargs)
        user = self.request.user

        # Создание экземпляра формы с данными из запроса.
        form = OrderCountFilterForm(self.request.GET or None)
        context['filter_form'] = form

        # Подсчет выполненных поверок счетчиков
        filtered_orders = Order.objects.filter(status__status='Выполнено')

        if form.is_valid():
            if user.is_superuser:
                selected_user = form.cleaned_data.get('user')
                if selected_user:
                    user = selected_user
                    filtered_orders = filtered_orders.filter(master=selected_user)
            else:
                filtered_orders = filtered_orders.filter(master=user)

            start_date = form.cleaned_data.get('start_date')
            end_date = form.cleaned_data.get('end_date')
            if start_date:
                filtered_orders = filtered_orders.filter(execution_date__gte=start_date)
            if end_date:
                filtered_orders = filtered_orders.filter(execution_date__lte=end_date)

        else:
            filtered_orders = filtered_orders.filter(master=user)

        services = Service.objects.filter(order__in=filtered_orders)
        context['all_orders_count'] = filtered_orders.count()
        context['verifications_count'] = services.filter(service_name__company_service='Поверка счетчиков воды').count()
        context['replacements_count'] = services.filter(service_name__company_service='Замена счетчиков воды').count()

        # Получение количества и суммы выполненных поверок для ХВС.
        cold_water_verifications_sum = int(services.filter(
            service_name__company_service='Поверка счетчиков воды',
            cold_water__gt=0
        ).aggregate(Sum('cold_water'))['cold_water__sum'] or 0)

        context['cold_water_verifications_sum'] = cold_water_verifications_sum

        # Получение количества и суммы выполненных поверок для ГВС.
        hot_water_verifications_sum = int(services.filter(
            service_name__company_service='Поверка счетчиков воды',
            hot_water__gt=0
        ).aggregate(Sum('hot_water'))['hot_water__sum'] or 0)

        context['hot_water_verifications_sum'] = hot_water_verifications_sum

        # Получение общего количества и суммы выполненных поверок для ХВС + ГВС.
        context['sum_verifications_water'] = cold_water_verifications_sum + hot_water_verifications_sum

        # Получение количества выполненных замен для ХВС.
        cold_water_replacements_sum = int(services.filter(
            service_name__company_service='Замена счетчиков воды',
            cold_water__gt=0
        ).aggregate(Sum('cold_water'))['cold_water__sum'] or 0)

        context['cold_water_replacements_sum'] = cold_water_replacements_sum

        # Получение количества выполненных замен для ГВС.
        hot_water_replacements_sum = int(services.filter(
            service_name__company_service='Замена счетчиков воды',
            hot_water__gt=0
        ).aggregate(Sum('hot_water'))['hot_water__sum'] or 0)

        context['hot_water_replacements_sum'] = hot_water_replacements_sum

        # Получение количества и суммы выполненных замен для ХВС + ГВС.
        context['sum_replacements_water'] = cold_water_replacements_sum + hot_water_replacements_sum


        # Получение количества и суммы выполненных ввода в экспуатацию для ХВС.
        cold_water_commissioning_sum = int(services.filter(
            service_name__company_service='Ввод в эксплуатацию',
            cold_water__gt=0
        ).aggregate(Sum('cold_water'))['cold_water__sum'] or 0)

        context['cold_water_commissioning_sum'] = cold_water_commissioning_sum

        # Получение количества и суммы выполненных ввода в экспуатацию для ГВС.
        hot_water_commissioning_sum = int(services.filter(
            service_name__company_service='Ввод в эксплуатацию',
            hot_water__gt=0
        ).aggregate(Sum('hot_water'))['hot_water__sum'] or 0)

        context['hot_water_commissioning_sum'] = hot_water_commissioning_sum

        # Получение общего количества и суммы выполненных ввода в экспуатацию для ХВС + ГВС.
        context['sum_commissioning_water'] = cold_water_commissioning_sum + hot_water_commissioning_sum


        # Получение количества и суммы выполненных опломбировок для ХВС.
        cold_water_sealing_sum = int(services.filter(
            service_name__company_service='Опломбировка',
            cold_water__gt=0
        ).aggregate(Sum('cold_water'))['cold_water__sum'] or 0)

        context['cold_water_sealing_sum'] = cold_water_sealing_sum

        # Получение количества и суммы выполненных опломбировок для ГВС.
        hot_water_sealing_sum = int(services.filter(
            service_name__company_service='Опломбировка',
            hot_water__gt=0
        ).aggregate(Sum('hot_water'))['hot_water__sum'] or 0)

        context['hot_water_sealing_sum'] = hot_water_sealing_sum

        # Получение общего количества и суммы выполненных опломбировок для ХВС + ГВС.
        context['sum_sealing_water'] = cold_water_sealing_sum + hot_water_sealing_sum


        # Получение количества и суммы выполненных снятия контрольных показаний для ХВС.
        cold_water_taking_control_readings_sum = int(services.filter(
            service_name__company_service='Снятие контрольных показания',
            cold_water__gt=0
        ).aggregate(Sum('cold_water'))['cold_water__sum'] or 0)

        context['cold_water_taking_control_readings_sum'] = cold_water_taking_control_readings_sum

        # Получение количества и суммы выполненных снятия контрольных показаний для ГВС.
        hot_water_taking_control_readings_sum = int(services.filter(
            service_name__company_service='Снятие контрольных показания',
            hot_water__gt=0
        ).aggregate(Sum('hot_water'))['hot_water__sum'] or 0)

        context['hot_water_taking_control_readings_sum'] = hot_water_taking_control_readings_sum

        # Получение общего количества и суммы выполненных снятия контрольных показаний для ХВС + ГВС.
        context['sum_taking_control_readings_water'] = cold_water_taking_control_readings_sum + hot_water_taking_control_readings_sum


        # Получение количества и суммы выполненных услуг "Остальное" для ХВС.
        cold_water_other_services_sum = int(services.filter(
            ~Q(service_name__company_service__in=['Снятие контрольных показаний', 'Поверка счетчиков воды',
                                                  'Замена счетчиков воды', 'Ввод в эксплуатацию', 'Опломбировка']),
            cold_water__gt=0
        ).aggregate(Sum('cold_water'))['cold_water__sum'] or 0)

        context['cold_water_other_services_sum'] = cold_water_other_services_sum

        # Получение количества и суммы выполненных услуг "Остальное" для ГВС.
        hot_water_other_services_sum = int(services.filter(
            ~Q(service_name__company_service__in=['Снятие контрольных показаний', 'Поверка счетчиков воды',
                                                  'Замена счетчиков воды', 'Ввод в эксплуатацию', 'Опломбировка']),
            hot_water__gt=0
        ).aggregate(Sum('hot_water'))['hot_water__sum'] or 0)

        context['hot_water_other_services_sum'] = hot_water_other_services_sum

        # Получение общего количества и суммы выполненных услуг "Остальное" для ХВС + ГВС.
        context['sum_other_services_water'] = cold_water_other_services_sum + hot_water_other_services_sum


        # Получение общей суммы, начисленной за все услуги, предоставленные мастером
        total_service_amount = services.aggregate(
            total_amount=Sum('price')
        )['total_amount'] or Decimal('0.00')

        # Получение общей оплаты мастеру за все услуги
        total_payment_to_master = services.aggregate(
            total_payment=Sum('payment_master')
        )['total_payment'] or Decimal('0.00')

        # Теперь можно добавить эти значения в контекст
        context['total_service_amount'] = total_service_amount
        context['total_payment_to_master'] = total_payment_to_master


        # Группировка заявок отдельно по каждой дате исполнения и подсчет количества заявок на каждую дату.
        # Используйте уже отфильтрованный QuerySet filtered_orders для этого запроса.
        date_wise_orders = filtered_orders.values('execution_date').annotate(
            total_orders=Count('id')
        ).order_by('execution_date')

        # Добавление информации о заявках по датам в контекст для шаблона.
        context['date_wise_orders'] = date_wise_orders

        # Группировка заявок "Замена счетчиков воды" по дням и подсчет общего числа ХВС + ГВС
        replacements_by_day = filtered_orders.filter(
            master=user,
            service__service_name__company_service='Замена счетчиков воды'
        ).annotate(
            date=F('execution_date')
        ).values('date').annotate(
            total_cold_water=Sum(Case(
                When(Q(service__cold_water__gt=0), then='service__cold_water'),
                default=Value(0),
                output_field=models.IntegerField()
            )),
            total_hot_water=Sum(Case(
                When(Q(service__hot_water__gt=0), then='service__hot_water'),
                default=Value(0),
                output_field=models.IntegerField()
            ))
        ).annotate(
            total_replacements=F('total_cold_water') + F('total_hot_water')
        ).order_by('date')

        context['replacements_by_day'] = replacements_by_day

        # Группировка заявок "Поверка счетчиков воды" по дням и подсчет общего числа ХВС + ГВС
        verifications_by_day = filtered_orders.filter(
            master=user,
            service__service_name__company_service='Поверка счетчиков воды'
        ).annotate(
            date=F('execution_date')
        ).values('date').annotate(
            total_cold_water=Sum(Case(
                When(Q(service__cold_water__gt=0), then='service__cold_water'),
                default=Value(0),
                output_field=models.IntegerField()
            )),
            total_hot_water=Sum(Case(
                When(Q(service__hot_water__gt=0), then='service__hot_water'),
                default=Value(0),
                output_field=models.IntegerField()
            ))
        ).annotate(
            total_verifications=F('total_cold_water') + F('total_hot_water')
        ).order_by('date')

        context['verifications_by_day'] = verifications_by_day

        # Группировка заявок "Ввода в экспуатацию" по дням и подсчет общего числа ХВС + ГВС
        commissioning_by_day = filtered_orders.filter(
            master=user,
            service__service_name__company_service='Ввод в эксплуатацию'
        ).annotate(
            date=F('execution_date')
        ).values('date').annotate(
            total_cold_water=Sum(Case(
                When(Q(service__cold_water__gt=0), then='service__cold_water'),
                default=Value(0),
                output_field=models.IntegerField()
            )),
            total_hot_water=Sum(Case(
                When(Q(service__hot_water__gt=0), then='service__hot_water'),
                default=Value(0),
                output_field=models.IntegerField()
            ))
        ).annotate(
            total_commissioning=F('total_cold_water') + F('total_hot_water')
        ).order_by('date')

        context['commissioning_by_day'] = commissioning_by_day

        # Группировка заявок "Опломбировки" по дням и подсчет общего числа ХВС + ГВС
        sealing_by_day = filtered_orders.filter(
            master=user,
            service__service_name__company_service='Опломбировка'
        ).annotate(
            date=F('execution_date')
        ).values('date').annotate(
            total_cold_water=Sum(Case(
                When(Q(service__cold_water__gt=0), then='service__cold_water'),
                default=Value(0),
                output_field=models.IntegerField()
            )),
            total_hot_water=Sum(Case(
                When(Q(service__hot_water__gt=0), then='service__hot_water'),
                default=Value(0),
                output_field=models.IntegerField()
            ))
        ).annotate(
            total_sealing=F('total_cold_water') + F('total_hot_water')
        ).order_by('date')

        context['sealing_by_day'] = sealing_by_day


        # Группировка заявок "Снятия контрольных показаний" по дням и подсчет общего числа ХВС + ГВС
        taking_control_readings_by_day = filtered_orders.filter(
            master=user,
            service__service_name__company_service='Снятие контрольных показания'
        ).annotate(
            date=F('execution_date')
        ).values('date').annotate(
            total_cold_water=Sum(Case(
                When(Q(service__cold_water__gt=0), then='service__cold_water'),
                default=Value(0),
                output_field=models.IntegerField()
            )),
            total_hot_water=Sum(Case(
                When(Q(service__hot_water__gt=0), then='service__hot_water'),
                default=Value(0),
                output_field=models.IntegerField()
            ))
        ).annotate(
            total_taking_control_readings=F('total_cold_water') + F('total_hot_water')
        ).order_by('date')

        context['taking_control_readings_by_day'] = taking_control_readings_by_day

        # Группировка заявок "Остальное" по дням и подсчет общего числа ХВС + ГВС
        other_services_by_day = filtered_orders.filter(
            master=user
        ).exclude(
            service__service_name__company_service__in=['Снятие контрольных показаний', 'Поверка счетчиков воды',
                                       'Замена счетчиков воды', 'Ввод в эксплуатацию', 'Опломбировка']
        ).annotate(
            date=F('execution_date')
        ).values('date').annotate(
            total_cold_water=Sum(Case(
                When(Q(service__cold_water__gt=0), then='service__cold_water'),
                default=Value(0),
                output_field=models.IntegerField()
            )),
            total_hot_water=Sum(Case(
                When(Q(service__hot_water__gt=0), then='service__hot_water'),
                default=Value(0),
                output_field=models.IntegerField()
            ))
        ).annotate(
            total_other_services=F('total_cold_water') + F('total_hot_water')
        ).order_by('date')

        context['other_services_by_day'] = other_services_by_day

        # Сумма с заявки и оплата мастеру за день
        orders_summary_by_day = filtered_orders.filter(
            master=user
        ).annotate(
            date=F('execution_date')
        ).values(
            'date'
        ).annotate(
            daily_sum=Sum('service__price'),
            daily_payment_master=Sum('service__payment_master')
        ).order_by('date')

        context['filter_form'] = form

        # Создаем словарь по умолчанию для замен и поверок по датам
        replacements_dict = {item['date']: item['total_replacements'] for item in replacements_by_day}
        verifications_dict = {item['date']: item['total_verifications'] for item in verifications_by_day}
        commissioning_dict = {item['date']: item['total_commissioning'] for item in commissioning_by_day}
        sealing_dict = {item['date']: item['total_sealing'] for item in sealing_by_day}
        taking_control_readings_dict = {item['date']: item['total_taking_control_readings'] for item in taking_control_readings_by_day}
        other_services_dict = {item['date']: item['total_other_services'] for item in other_services_by_day}
        daily_sum_dict = {item['date']: item['daily_sum'] for item in orders_summary_by_day}
        daily_payment_master_dict = {item['date']: item['daily_payment_master'] for item in orders_summary_by_day}

        # Создаем комбинированный список для данных по датам
        combined_data_by_date = []
        for order_date in date_wise_orders:
            date = order_date['execution_date']
            total_orders = order_date['total_orders']
            total_replacements = replacements_dict.get(date, 0)
            total_verifications = verifications_dict.get(date, 0)
            total_commissioning = commissioning_dict.get(date, 0)
            total_sealing = sealing_dict.get(date, 0)
            total_taking_control_readings = taking_control_readings_dict.get(date, 0)
            total_other_services = other_services_dict.get(date, 0)
            daily_sum = daily_sum_dict.get(date, 0)  # Новая общая сумма за день
            daily_payment_master = daily_payment_master_dict.get(date, 0)  # Новая общая сумма оплаты мастеру за день

            # Создаем словарь с данными для каждой записи
            combined_data_by_date.append({
                'date': date,
                'total_orders': total_orders,
                'total_verifications': total_verifications,
                'total_replacements': total_replacements,
                'total_commissioning': total_commissioning,
                'total_sealing': total_sealing,
                'total_taking_control_readings': total_taking_control_readings,
                'total_other_services': total_other_services,
                'daily_sum': daily_sum,
                'daily_payment_master': daily_payment_master,
            })

        # Сортируем combined_data_by_date по ключу 'date' в порядке убывания
        sorted_combined_data = sorted(combined_data_by_date, key=lambda x: x['date'], reverse=True)

        # Пагинация для combined_data_by_date
        paginator = Paginator(sorted_combined_data, 20)
        page = self.request.GET.get('page')
        page_obj = paginator.get_page(page)

        # Добавляем комбинированный список в контекст
        context['combined_data_by_date'] = page_obj

        return context

