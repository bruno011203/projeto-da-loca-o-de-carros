from django.contrib import admin
from django.urls import include, path

admin.site.site_header = "Locadora — Administração"
admin.site.site_title = "Locadora"
admin.site.index_title = "Cadastros"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("contas/", include("django.contrib.auth.urls")),
    path("", include("locacao.urls")),
]
