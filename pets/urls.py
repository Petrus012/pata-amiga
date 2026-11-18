from django.urls import path

from . import views

app_name = "pets"

urlpatterns = [
    path("", views.CatalogoView.as_view(), name="catalogo"),
    path("<int:pk>/", views.DetalheView.as_view(), name="detalhe"),
]
