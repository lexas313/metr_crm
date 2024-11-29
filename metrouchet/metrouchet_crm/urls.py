"""
URL configuration for metrouchet project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""

from django.urls import path
from . import views

urlpatterns = [
    path('', views.TodayOrdersListView.as_view(), name='today_orders'),
    path('tomorrow/', views.TomorrowOrdersListView.as_view(), name='tomorrow_orders'),
    path('all/', views.AllOrdersListView.as_view(), name='all_orders'),
    path('all-orders', views.OrderEditView.as_view(), name='all-orders'),
    path('details/<int:pk>', views.DetailsListView.as_view(), name='details'),
    path('create', views.OrderCreateView.as_view(), name='create'),
    path('update/<int:pk>', views.OrdersUpdateView.as_view(), name='update'),
    path('delete/<int:pk>', views.OrderDeleteView.as_view(), name='delete'),
    path('login', views.LoginUserView.as_view(), name='login'),
    path('register', views.RegisterUserView.as_view(), name='register_page'),
    path('logout', views.LogoutUserView.as_view(), name='logout_page'),
    path('get_water_price/', views.get_water_price, name='get_water_price'),
    path('get_service_price/', views.get_service_price, name='get_service_price'),
    path('all-orders/update_status/<int:order_id>/', views.update_status, name='order_update_status'),
    path('all-orders/update_master/<int:order_id>/', views.update_master, name='order_update_master'),
    path('company-service-price', views.CreateCompanyServiceView.as_view(), name='company_service_price'),
    path('company-service-price/<int:pk>', views.UpdateCompanyServiceView.as_view(), name='company_service_price'),
    path('company-service-price/delete/<int:pk>', views.DeleteCompanyServiceView.as_view(), name='company_service_price_delete'),
    path('water-name', views.CreateWaterNameView.as_view(), name='water_name'),
    path('water-name/<int:pk>', views.UpdateWaterNameView.as_view(), name='water_name'),
    path('water-name/delete/<int:pk>', views.DeleteWaterNameView.as_view(), name='water_name_delete'),
    path('status-name', views.CreateStatusView.as_view(), name='status_name'),
    path('status-name/<int:pk>', views.UpdateStatusView.as_view(), name='status_name'),
    path('status-name/delete/<int:pk>', views.DeleteStatusView.as_view(), name='status_name_delete'),

    path('districts', views.CreateDistrictView.as_view(), name='districts_name'),
    path('districts/<int:pk>', views.UpdateDistrictView.as_view(), name='districts_name'),
    path('districts/delete/<int:pk>', views.DeleteDistrictView.as_view(), name='districts_name_delete'),

    path('users', views.CreateUserView.as_view(), name='users_name'),
    path('users/<int:pk>', views.UpdateUserView.as_view(), name='users_name'),
    path('users/delete/<int:pk>', views.DeleteUserView.as_view(), name='users_name_delete'),

    path('import-excel', views.import_excel, name='import_excel'),
    path('profile', views.ProfileView.as_view(), name='user_profile'),
    # path('get-orders-ajax/', views.get_orders_ajax, name='get_orders_ajax'),
    path('get-client-name/', views.get_client_name, name='get-client-name'),
]

