from django import forms
from .models import Order, Client, Address, Service, CompanyService, WaterName, WaterPhoto, DocumentPhoto, Status, District
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.models import User
from django.forms import modelformset_factory
from django_select2.forms import ModelSelect2Widget


class UserFullnameChoiceField(forms.ModelChoiceField):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.queryset = User.objects.filter(groups__name__icontains='Мастер')

    def label_from_instance(self, obj):
        return obj.get_full_name()


class OrderForm(forms.ModelForm):
    master = UserFullnameChoiceField(queryset=User.objects.all(), label='Мастер', required=False)
    execution_date = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), label='Дата исполнения', required=False)
    start_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Время от', required=False)
    end_time = forms.TimeField(widget=forms.TimeInput(attrs={'type': 'time'}), label='Время до', required=False)
    comments = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)
    comments_masters = forms.CharField(widget=forms.Textarea(attrs={'rows': 2}), required=False)

    class Meta:
        model = Order
        fields = ('status', 'execution_date', 'start_time', 'end_time', 'master', 'comments', 'comments_masters')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['master'].empty_label = '-Выберите мастера-'
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


# Форма для клиентов
class ClientForm(forms.ModelForm):
    phone = forms.CharField(max_length=20, label='Телефон', required=False)
    client_name = forms.CharField(max_length=100, label='ФИО клиента', required=False)
    delete = forms.BooleanField(required=False, widget=forms.HiddenInput())


    class Meta:
        model = Client
        fields = ['phone', 'client_name']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


# Формсет для создания клиентов
ClientFormSet = modelformset_factory(Client, form=ClientForm, extra=1, can_delete=True)

# Формсет для редактирования клиентов
ClientFormSetUpdate = modelformset_factory(Client, form=ClientForm, extra=0, can_delete=True)


class AddressForm(forms.ModelForm):
    district = forms.ModelChoiceField(queryset=District.objects.all(), label='Район', required=False)
    street_house = forms.CharField(max_length=255, label='Улица', required=False)
    apartment = forms.IntegerField(label="Квартира", required=False)
    entrance = forms.IntegerField(label="Подъезд", required=False)
    floor = forms.IntegerField(label="Этаж", required=False)
    intercom = forms.CharField(max_length=24, label='Домофон', required=False)

    class Meta:
        model = Address
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class ServiceForm(forms.ModelForm):
    service_name = forms.ModelChoiceField(queryset=CompanyService.objects.all(), label='Услуга', required=False)
    water_name = forms.ModelChoiceField(queryset=WaterName.objects.all(), label='Модель счетчиков', required=False)
    cold_water = forms.IntegerField(label='Холодных счетчиков', required=False)
    hot_water = forms.IntegerField(label='Горячих счетчиков', required=False)
    price = forms.DecimalField(label='Сумма', required=False, max_digits=10, decimal_places=2)
    payment_master = forms.DecimalField(label='Оплата мастера', required=False, max_digits=10, decimal_places=2)
    delete = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = Service
        fields = ['service_name', 'water_name', 'cold_water', 'hot_water', 'price', 'payment_master']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

        self.fields['cold_water'].initial = 0
        self.fields['hot_water'].initial = 0
        self.fields['price'].initial = 0.0
        self.fields['payment_master'].initial = 0.0

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('cold_water'):
            cleaned_data['cold_water'] = 0
        if not cleaned_data.get('hot_water'):
            cleaned_data['hot_water'] = 0
        if not cleaned_data.get('price'):
            cleaned_data['price'] = 0
        if not cleaned_data.get('payment_master'):
            cleaned_data['payment_master'] = 0
        return cleaned_data


# Формсет для создания услуг
ServiceFormSet = modelformset_factory(Service, form=ServiceForm, extra=1, can_delete=True)


class WaterNameForm(forms.ModelForm):
    water_name = forms.CharField(label='Модель счетчика', max_length=64, required=False)
    water_price = forms.DecimalField(label='Цена с заменой', max_digits=10, decimal_places=2, required=False)

    class Meta:
        model = WaterName
        fields = ['water_name', 'water_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class WaterPhotoForm(forms.ModelForm):
    CHOICES = [
        ('', '---------'),  # Добавьте пустой выбор в начало списка
        ('ХВ', '🔵ХВС'),
        ('ГВ', '🔴ГВС')
    ]
    cold_or_hot = forms.ChoiceField(label='Хвс или гвс', required=False, choices=CHOICES, initial='')
    water_photo = forms.ImageField(label='Фото счетчика', required=False)
    delete = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = WaterPhoto
        fields = ['cold_or_hot', 'water_photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


# Формсет для фото счетчиков
WaterPhotoFormSet = modelformset_factory(WaterPhoto, form=WaterPhotoForm, extra=1, can_delete=True)


class DocumentPhotoForm(forms.ModelForm):
    document_photo = forms.ImageField(label='Фото документов', required=False)
    delete = forms.BooleanField(required=False, widget=forms.HiddenInput())

    class Meta:
        model = DocumentPhoto
        fields = ['document_photo']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


# Формсет для фото документов
DocumentPhotoFormSet = modelformset_factory(DocumentPhoto, form=DocumentPhotoForm, extra=1, can_delete=True)


class OrderFilterForm(forms.Form):
    start_date = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), label='Начальная дата', required=False)
    end_date = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), label='Конечная дата', required=False)
    master = UserFullnameChoiceField(queryset=User.objects.all(), label='Мастер', required=False)
    search = forms.CharField(label='Поиск', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class OrderCountFilterForm(forms.Form):
    user = UserFullnameChoiceField(queryset=User.objects.all(), label='Мастер', required=False)
    start_date = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), label='Начальная дата', required=False)
    end_date = forms.DateField(widget=forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}), label='Конечная дата', required=False)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class CompanyServiceForm(forms.ModelForm):
    company_service = forms.CharField(label='Услуга', max_length=64)
    service_price = forms.DecimalField(label='Цена', required=False, max_digits=10, decimal_places=2)

    class Meta:
        model = CompanyService
        fields = ['company_service', 'service_price']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class StatusForm(forms.ModelForm):
    status = forms.CharField(label='Статус', max_length=15)

    class Meta:
        model = Status
        fields = ['status']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class DistrictForm(forms.ModelForm):
    district = forms.CharField(label='Район', max_length=64)

    class Meta:
        model = District
        fields = ['district']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class DistrictListForm(forms.Form):
    district_list = forms.CharField(
        widget=forms.Textarea(attrs={'placeholder': 'Введите название районов, каждый с новой строки'}),
        label='Список районов'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class AuthUserForm(AuthenticationForm, forms.ModelForm):
    class Meta:
        model = User
        fields = ('username', 'password')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'


class RegisterUserForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'username', 'groups')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'

    # def save(self, commit=True):
    #     user = super().save(commit=False)
    #     user.set_password(self.cleaned_data["password"])
    #     if commit:
    #         user.save()
    #         if hasattr(self, "save_m2m"):
    #             self.save_m2m()
    #     return user


class ExcelImportForm(forms.Form):
    excel_file = forms.FileField(label='Выберите файл Excel')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields:
            self.fields[field].widget.attrs['class'] = 'form-control'