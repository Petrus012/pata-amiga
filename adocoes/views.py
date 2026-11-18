from django.contrib import messages
from django.db import IntegrityError, transaction
from django.db.models import Count
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse, reverse_lazy
from django.utils.functional import cached_property
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View
from django.views.generic import CreateView, FormView, ListView

from contas.mixins import AdotanteRequiredMixin, OngRequiredMixin
from pets.models import Pet

from .forms import (
    ACOES_DA_ONG,
    AcompanhamentoForm,
    PedidoAdocaoForm,
    ResponderPedidoForm,
)
from .models import (
    STATUS_EM_ABERTO,
    Favorito,
    PedidoAdocao,
    StatusPedido,
    TransicaoInvalida,
)


# Área do adotante

class SolicitarAdocaoView(AdotanteRequiredMixin, FormView):
    template_name = "adocoes/solicitar.html"
    form_class = PedidoAdocaoForm
    success_url = reverse_lazy("adocoes:meus_pedidos")

    # O animal é carregado sob demanda, e não no dispatch, para o teste de perfil do
    # mixin rodar antes. Assim um anônimo não descobre pelo 404 quais animais existem.
    @cached_property
    def pet(self):
        return get_object_or_404(Pet.objects.select_related("especie", "ong"), pk=self.kwargs["pk"])

    def bloqueio(self):
        if self.pet.status == Pet.Status.ADOTADO:
            messages.error(
                self.request, f"{self.pet.nome} já foi adotado e não recebe novos pedidos."
            )
            return redirect(self.pet)
        if PedidoAdocao.objects.filter(
            pet=self.pet, adotante=self.request.user, status__in=STATUS_EM_ABERTO
        ).exists():
            messages.info(
                self.request, f"Você já tem um pedido em aberto para {self.pet.nome}."
            )
            return redirect(self.success_url)
        return None

    def get(self, request, *args, **kwargs):
        return self.bloqueio() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.bloqueio() or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs.update(pet=self.pet, adotante=self.request.user)
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(pet=self.pet, **kwargs)

    def form_valid(self, form):
        pedido = form.save(commit=False)
        pedido.pet = self.pet
        pedido.adotante = self.request.user
        try:
            with transaction.atomic():
                pedido.save()
        except IntegrityError:
            # Dois envios simultâneos: o banco barrou o segundo.
            messages.info(
                self.request, f"Você já tem um pedido em aberto para {self.pet.nome}."
            )
            return redirect(self.success_url)
        messages.success(
            self.request,
            f"Pedido de adoção de {self.pet.nome} enviado. A ONG vai analisar e responder por aqui.",
        )
        return redirect(self.success_url)


class MeusPedidosView(AdotanteRequiredMixin, ListView):
    template_name = "adocoes/meus_pedidos.html"
    context_object_name = "pedidos"
    paginate_by = 10

    def get_queryset(self):
        return (
            PedidoAdocao.objects.filter(adotante=self.request.user)
            .select_related("pet__especie", "pet__ong")
            .prefetch_related("acompanhamentos")
        )


class CancelarPedidoView(AdotanteRequiredMixin, View):
    http_method_names = ["post"]

    def post(self, request, pk):
        pedido = get_object_or_404(PedidoAdocao, pk=pk, adotante=request.user)
        if pedido.status != StatusPedido.PENDENTE:
            messages.error(
                request, "Só é possível cancelar um pedido que a ONG ainda não começou a analisar."
            )
        else:
            nome = pedido.pet.nome
            pedido.delete()
            messages.success(request, f"Pedido de adoção de {nome} cancelado.")
        return redirect("adocoes:meus_pedidos")


class AcompanhamentoCreateView(AdotanteRequiredMixin, CreateView):
    form_class = AcompanhamentoForm
    template_name = "adocoes/acompanhamento_form.html"
    success_url = reverse_lazy("adocoes:meus_pedidos")

    @cached_property
    def pedido(self):
        return get_object_or_404(
            PedidoAdocao.objects.select_related("pet"),
            pk=self.kwargs["pk"],
            adotante=self.request.user,
        )

    def bloqueio(self):
        if self.pedido.status != StatusPedido.CONCLUIDO:
            messages.error(
                self.request, "Você só pode registrar acompanhamento depois da adoção concluída."
            )
            return redirect(self.success_url)
        return None

    def get(self, request, *args, **kwargs):
        return self.bloqueio() or super().get(request, *args, **kwargs)

    def post(self, request, *args, **kwargs):
        return self.bloqueio() or super().post(request, *args, **kwargs)

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["pedido"] = self.pedido
        return kwargs

    def get_context_data(self, **kwargs):
        return super().get_context_data(pedido=self.pedido, **kwargs)

    def form_valid(self, form):
        messages.success(self.request, "Acompanhamento registrado. Obrigado por compartilhar!")
        return super().form_valid(form)


class FavoritarView(AdotanteRequiredMixin, View):
    """Adiciona o animal aos favoritos, ou remove se já estiver lá."""

    http_method_names = ["post"]

    def post(self, request, pk):
        pet = get_object_or_404(Pet, pk=pk)
        favorito, criado = Favorito.objects.get_or_create(usuario=request.user, pet=pet)
        if criado:
            messages.success(request, f"{pet.nome} foi para os seus favoritos.")
        else:
            favorito.delete()
            messages.info(request, f"{pet.nome} saiu dos seus favoritos.")

        # O formulário informa de onde veio, mas só aceitamos endereços do próprio site.
        destino = request.POST.get("next", "")
        if not url_has_allowed_host_and_scheme(
            destino, allowed_hosts={request.get_host()}, require_https=request.is_secure()
        ):
            destino = pet.get_absolute_url()
        return redirect(destino)


class MeusFavoritosView(AdotanteRequiredMixin, ListView):
    template_name = "adocoes/favoritos.html"
    context_object_name = "favoritos"
    paginate_by = 12

    def get_queryset(self):
        return Favorito.objects.filter(usuario=self.request.user).select_related(
            "pet__especie", "pet__raca", "pet__ong"
        )


# Área da ONG

class PedidosRecebidosView(OngRequiredMixin, ListView):
    template_name = "adocoes/recebidos.html"
    context_object_name = "pedidos"
    paginate_by = 10

    def pedidos_da_ong(self):
        return PedidoAdocao.objects.filter(pet__ong=self.request.user.ong)

    @property
    def status_escolhido(self):
        status = self.request.GET.get("status", "")
        return status if status in StatusPedido.values else ""

    def get_queryset(self):
        pedidos = self.pedidos_da_ong().select_related("pet__especie", "adotante")
        if self.status_escolhido:
            pedidos = pedidos.filter(status=self.status_escolhido)
        return pedidos

    def get_context_data(self, **kwargs):
        contagem = dict(
            self.pedidos_da_ong().values_list("status").annotate(total=Count("id"))
        )
        filtros = [("", "Todos", sum(contagem.values()))]
        filtros += [
            (valor, rotulo, contagem.get(valor, 0)) for valor, rotulo in StatusPedido.choices
        ]
        return super().get_context_data(
            filtros=filtros, status_escolhido=self.status_escolhido, **kwargs
        )


class ResponderPedidoView(OngRequiredMixin, FormView):
    template_name = "adocoes/responder.html"
    form_class = ResponderPedidoForm

    # Filtrar pelo animal da ONG logada é o que impede uma ONG de abrir o pedido de outra:
    # com o endereço de outro pedido, o resultado é 404, como se ele não existisse.
    @cached_property
    def pedido(self):
        return get_object_or_404(
            PedidoAdocao.objects.select_related("pet__especie", "pet__ong", "adotante"),
            pk=self.kwargs["pk"],
            pet__ong=self.request.user.ong,
        )

    def get_initial(self):
        return {"resposta": self.pedido.resposta_ong}

    def get_context_data(self, **kwargs):
        return super().get_context_data(pedido=self.pedido, **kwargs)

    def get_success_url(self):
        return reverse("adocoes:responder", kwargs={"pk": self.pedido.pk})

    def form_valid(self, form):
        acao = form.cleaned_data["acao"]
        try:
            self.pedido.mudar_status(ACOES_DA_ONG[acao], form.cleaned_data["resposta"].strip())
        except TransicaoInvalida as erro:
            form.add_error(None, str(erro))
            return self.form_invalid(form)
        messages.success(
            self.request,
            f"Pedido de {self.pedido.adotante} atualizado para "
            f"{self.pedido.get_status_display().lower()}.",
        )
        return super().form_valid(form)
