from django.conf.urls.static import static
from django.contrib import admin
from django.urls import path, include


from .settings import base
from django.views.static import serve as mediaserve


urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('metrouchet_crm.urls')),
    path("select2/", include("django_select2.urls")),
]

if base.DEBUG:
    urlpatterns += static(base.MEDIA_URL, document_root=base.MEDIA_ROOT)
# else:
#     urlpatterns += [
#         path(f'^{base.MEDIA_URL.lstrip("/")}(?P<path>.*)$',
#             mediaserve, {'document_root': base.MEDIA_ROOT}),
#         path(f'^{base.STATIC_URL.lstrip("/")}(?P<path>.*)$',
#             mediaserve, {'document_root': base.STATIC_ROOT}),
#     ]