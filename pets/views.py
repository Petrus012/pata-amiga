from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView

from adocoes.models import STATUS_EM_ABERTO, Favorito, PedidoAdocao
from contas.mixins import OngRequiredMixin

from .forms import CatalogoFiltroForm, PetForm, VacinaFormSet
from .models import Pet


class CatalogoView(LoginRequiredMixin, ListView):
    template_name = "pets/catalogo.html"
    context_object_name = "pets"
    paginate_by = 12

    def get_queryset(self):
        # Animais em processo de adoção continuam visíveis, porque o pedido ainda pode
        # não dar certo. Só os já adotados saem do catálogo.
        animais = Pet.objects.exclude(status=Pet.Status.ADOTADO).select_related(
            "especie", "raca", "ong"
        )
        self.filtros = CatalogoFiltroForm(self.request.GET)
        return self.filtros.filtrar(animais)

    def get_context_data(self, **kwargs):
        return super().get_context_data(filtros=self.filtros, **kwargs)


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


# Área da ONG: os animais da própria ONG

class AnimaisDaOngMixin(OngRequiredMixin):
    """Toda tela da área da ONG trabalha só com os animais da ONG logada.

    Com o endereço de um animal de outra ONG, editar e remover dão 404, como se o
    animal não existisse. É o mesmo comportamento das telas de pedidos recebidos.
    """

    def get_queryset(self):
        return Pet.objects.filter(ong=self.request.user.ong)


class MeusAnimaisView(AnimaisDaOngMixin, ListView):
    template_name = "pets/meus_animais.html"
    context_object_name = "pets"
    paginate_by = 20

    def get_queryset(self):
        return (
            super()
            .get_queryset()
            .select_related("especie", "raca")
            # distinct nas duas contagens: juntar pedidos e vacinas na mesma consulta
            # multiplica as linhas, e sem ele 1 pedido com 2 vacinas contaria 2 pedidos.
            .annotate(
                pedidos_abertos=Count(
                    "pedidos", filter=Q(pedidos__status__in=STATUS_EM_ABERTO), distinct=True
                ),
                total_vacinas=Count("vacinas", distinct=True),
            )
            # O annotate desfaz a ordenação padrão do modelo, e a paginação sem ordem
            # pode repetir ou pular animais entre as páginas.
            .order_by("-criado_em")
        )

    def get_context_data(self, **kwargs):
        resumo = AnimaisDaOngMixin.get_queryset(self).aggregate(
            total=Count("pk"),
            disponiveis=Count("pk", filter=Q(status=Pet.Status.DISPONIVEL)),
            em_processo=Count("pk", filter=Q(status=Pet.Status.EM_PROCESSO)),
            adotados=Count("pk", filter=Q(status=Pet.Status.ADOTADO)),
        )
        return super().get_context_data(resumo=resumo, **kwargs)


class FormularioAnimalMixin:
    """Salva o animal e as vacinas juntos: ou os dois entram no banco, ou nenhum."""

    form_class = PetForm
    template_name = "pets/animal_form.html"
    success_url = reverse_lazy("pets:meus_animais")
    mensagem_sucesso = ""

    def get_context_data(self, **kwargs):
        kwargs.setdefault("vacinas", VacinaFormSet(instance=self.object))
        return super().get_context_data(**kwargs)

    def form_valid(self, form):
        vacinas = VacinaFormSet(self.request.POST, instance=form.instance)
        if not vacinas.is_valid():
            return self.form_invalid(form, vacinas)
        with transaction.atomic():
            self.preparar(form.instance)
            self.object = form.save()
            vacinas.instance = self.object
            vacinas.save()
        messages.success(self.request, self.mensagem_sucesso.format(nome=self.object.nome))
        return redirect(self.get_success_url())

    def form_invalid(self, form, vacinas=None):
        if vacinas is None:
            # O animal tem erro, mas as vacinas digitadas voltam para a tela com seus
            # próprios erros, em vez de sumirem.
            vacinas = VacinaFormSet(self.request.POST, instance=form.instance)
            vacinas.is_valid()
        return self.render_to_response(self.get_context_data(form=form, vacinas=vacinas))

    def preparar(self, pet):
        """Ajusta o animal antes de salvar. O cadastro usa para definir a ONG."""


class CadastrarAnimalView(AnimaisDaOngMixin, FormularioAnimalMixin, CreateView):
    mensagem_sucesso = "{nome} foi cadastrado e já aparece no catálogo."

    def preparar(self, pet):
        # A ONG não é campo do formulário: vem sempre do usuário logado.
        pet.ong = self.request.user.ong


class EditarAnimalView(AnimaisDaOngMixin, FormularioAnimalMixin, UpdateView):
    mensagem_sucesso = "Dados de {nome} atualizados."


class RemoverAnimalView(AnimaisDaOngMixin, DeleteView):
    template_name = "pets/animal_remover.html"
    context_object_name = "pet"
    success_url = reverse_lazy("pets:meus_animais")

    def get_context_data(self, **kwargs):
        return super().get_context_data(tem_pedidos=self.object.pedidos.exists(), **kwargs)

    def form_valid(self, form):
        # Remover o animal apagaria em cascata os pedidos e os acompanhamentos, e o
        # adotante perderia o histórico. Animal com qualquer pedido não é removido.
        if self.object.pedidos.exists():
            messages.error(
                self.request,
                f"{self.object.nome} tem pedidos de adoção e não pode ser removido, "
                "para não apagar o histórico dos adotantes.",
            )
            return redirect(self.success_url)
        nome = self.object.nome
        resposta = super().form_valid(form)
        messages.success(self.request, f"{nome} foi removido.")
        return resposta
