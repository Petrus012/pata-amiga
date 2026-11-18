from django.urls import path

from . import views

app_name = "pets"

urlpatterns = [
    path("", views.CatalogoView.as_view(), name="catalogo"),
    path("<int:pk>/", views.DetalheView.as_view(), name="detalhe"),
    # Área da ONG
    path("meus/", views.MeusAnimaisView.as_view(), name="meus_animais"),
    path("meus/novo/", views.CadastrarAnimalView.as_view(), name="cadastrar"),
    path("meus/<int:pk>/editar/", views.EditarAnimalView.as_view(), name="editar"),
    path("meus/<int:pk>/remover/", views.RemoverAnimalView.as_view(), name="remover"),
]
