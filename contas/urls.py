from django.urls import path

from . import views

app_name = "contas"

urlpatterns = [
    path("cadastro/", views.CadastroView.as_view(), name="cadastro"),
]
