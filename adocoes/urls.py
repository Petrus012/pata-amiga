from django.urls import path

from . import views

app_name = "adocoes"

urlpatterns = [
    # Adotante
    path("solicitar/<int:pk>/", views.SolicitarAdocaoView.as_view(), name="solicitar"),
    path("meus-pedidos/", views.MeusPedidosView.as_view(), name="meus_pedidos"),
    path("meus-pedidos/<int:pk>/cancelar/", views.CancelarPedidoView.as_view(), name="cancelar"),
    path(
        "meus-pedidos/<int:pk>/acompanhamento/",
        views.AcompanhamentoCreateView.as_view(),
        name="acompanhamento",
    ),
    path("favoritos/", views.MeusFavoritosView.as_view(), name="favoritos"),
    path("favoritos/<int:pk>/alternar/", views.FavoritarView.as_view(), name="alternar_favorito"),
    # ONG
    path("recebidos/", views.PedidosRecebidosView.as_view(), name="recebidos"),
    path("recebidos/<int:pk>/", views.ResponderPedidoView.as_view(), name="responder"),
]
