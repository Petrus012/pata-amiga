from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path
from django.views.generic import TemplateView

from contas import views as contas_views

urlpatterns = [
    path("", TemplateView.as_view(template_name="home.html"), name="home"),
    # Os nomes login e logout ficam sem namespace porque a navbar, os mixins e o
    # LOGIN_URL do settings referenciam as rotas por esses nomes.
    path("entrar/", contas_views.EntrarView.as_view(), name="login"),
    path("sair/", contas_views.SairView.as_view(), name="logout"),
    path("contas/", include("contas.urls")),
    path("animais/", include("pets.urls")),
    path("adocoes/", include("adocoes.urls")),
    path("admin/", admin.site.urls),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)