from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import DetailView, ListView

from adocoes.models import STATUS_EM_ABERTO, Favorito, PedidoAdocao

from .models import Pet


class CatalogoView(LoginRequiredMixin, ListView):
    template_name = "pets/catalogo.html"
    context_object_name = "pets"
    paginate_by = 12

    def get_queryset(self):
        # Animais em processo de adoção continuam visíveis, porque o pedido ainda pode
        # não dar certo. Só os já adotados saem do catálogo.
        return Pet.objects.exclude(status=Pet.Status.ADOTADO).select_related(
            "especie", "raca", "ong"
        )


class DetalheView(LoginRequiredMixin, DetailView):
    template_name = "pets/detalhe.html"
    context_object_name = "pet"
    queryset = Pet.objects.select_related("especie", "raca", "ong").prefetch_related("vacinas")

    def get_context_data(self, **kwargs):
        contexto = super().get_context_data(**kwargs)
        usuario = self.request.user
        # Favorito e pedido só fazem sentido para o adotante. ONG e administrador
        # veem a página sem os botões de ação.
        if usuario.eh_adotante:
            contexto["favoritado"] = Favorito.objects.filter(
                usuario=usuario, pet=self.object
            ).exists()
            contexto["pedido_aberto"] = PedidoAdocao.objects.filter(
                adotante=usuario, pet=self.object, status__in=STATUS_EM_ABERTO
            ).first()
        return contexto
