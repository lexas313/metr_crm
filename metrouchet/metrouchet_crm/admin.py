from django.contrib import admin
from .models import Order, Client, Address, CompanyService, Service, WaterName, Status, WaterPhoto
from simple_history.admin import SimpleHistoryAdmin
# Register your models here.


class OrderAdmin(SimpleHistoryAdmin, admin.ModelAdmin):
    filter_horizontal = ('client', 'service', 'water_photo', 'document_photo')


admin.site.register(Order, OrderAdmin)
admin.site.register(Client)
admin.site.register(Address)
admin.site.register(CompanyService)
admin.site.register(Service)
admin.site.register(WaterName)
admin.site.register(Status)
admin.site.register(WaterPhoto)



