from django import forms
from django.contrib import admin, messages
from django.utils.html import format_html

from .models import (
    STATUS_EM_ABERTO,
    TRANSICOES,
    Acompanhamento,
    Favorito,
    PedidoAdocao,
    StatusPedido,
    TransicaoInvalida,
)

# Classes de cor do Bootstrap 5, que é a versão usada pelo Jazzmin.
CORES_STATUS = {
    StatusPedido.PENDENTE: "text-bg-warning",
    StatusPedido.EM_ANALISE: "text-bg-info",
    StatusPedido.APROVADO: "text-bg-success",
    StatusPedido.RECUSADO: "text-bg-danger",
    StatusPedido.CONCLUIDO: "text-bg-secondary",
}


class PedidoAdocaoForm(forms.ModelForm):
    """Submete o admin às mesmas transições de status que o painel da ONG usa.

    Sem isto o admin gravava o status direto, e concluir um pedido por aqui deixava o
    animal como disponível.
    """

    class Meta:
        model = PedidoAdocao
        fields = "__all__"

    def clean_status(self):
        novo = self.cleaned_data["status"]
        # Em _clean_fields a instância ainda tem o status que está no banco, que é
        # justamente o ponto de partida da transição.
        if not self.instance.pk or novo == self.instance.status:
            return novo
        if novo not in TRANSICOES[self.instance.status]:
            atual = self.instance.get_status_display().lower()
            destino = dict(StatusPedido.choices)[novo].lower()
            raise forms.ValidationError(
                f"Um pedido {atual} não pode passar para {destino}."
            )
        return novo


class SituacaoPedidoFilter(admin.SimpleListFilter):
    """Agrupa os cinco status em duas situações, para achar rápido o que falta resolver."""

    title = "situação"
    parameter_name = "situacao"

    def lookups(self, request, model_admin):
        return [("aberto", "Em aberto"), ("encerrado", "Encerrado")]

    def queryset(self, request, queryset):
        if self.value() == "aberto":
            return queryset.filter(status__in=STATUS_EM_ABERTO)
        if self.value() == "encerrado":
            return queryset.exclude(status__in=STATUS_EM_ABERTO)
        return queryset


class AcompanhamentoInline(admin.StackedInline):
    model = Acompanhamento
    extra = 0
    fields = ["data", "relato", "foto"]


@admin.register(PedidoAdocao)
class PedidoAdocaoAdmin(admin.ModelAdmin):
    inlines = [AcompanhamentoInline]
    list_display = [
        "pet",
        "adotante",
        "ong",
        "status_colorido",
        "solicitado_em",
        "respondido_em",
    ]
    list_filter = [
        SituacaoPedidoFilter,
        "status",
        ("pet__ong", admin.RelatedOnlyFieldListFilter),
        "pet__especie",
        "solicitado_em",
        "respondido_em",
    ]
    list_select_related = ["pet__especie", "pet__ong", "adotante"]
    list_per_page = 20
    search_fields = [
        "pet__nome",
        "pet__ong__nome_fantasia",
        "adotante__username",
        "adotante__first_name",
        "adotante__last_name",
        "adotante__email",
    ]
    date_hierarchy = "solicitado_em"
    autocomplete_fields = ["pet", "adotante"]
    readonly_fields = ["solicitado_em", "respondido_em"]
    fieldsets = [
        ("Pedido", {"fields": ["pet", "adotante", "mensagem"]}),
        ("Análise da ONG", {"fields": ["status", "resposta_ong"]}),
        ("Registro", {"fields": ["solicitado_em", "respondido_em"]}),
    ]

    form = PedidoAdocaoForm

    def save_model(self, request, obj, form, change):
        """Troca o status pelo mudar_status, para o animal e os outros pedidos seguirem junto."""
        if not change or "status" not in form.changed_data:
            return super().save_model(request, obj, form, change)

        novo_status = obj.status
        # mudar_status valida a partir do status atual, então a instância volta ao
        # valor do banco antes da chamada.
        obj.status = form.initial["status"]
        try:
            obj.mudar_status(novo_status, resposta=obj.resposta_ong)
        except TransicaoInvalida as erro:
            messages.error(request, str(erro))

    def restrito_a_ong(self, request):
        # Superusuário e administrador veem tudo. A ONG vê só o que é dela.
        return request.user.eh_ong and not request.user.is_superuser

    def get_queryset(self, request):
        pedidos = super().get_queryset(request)
        if not self.restrito_a_ong(request):
            return pedidos
        # Sem este filtro, a ONG abria no admin os pedidos dos animais de outras ONGs.
        # Os filtros da lateral partem deste mesmo queryset, então também ficam restritos.
        ong = getattr(request.user, "ong", None)
        return pedidos.filter(pet__ong=ong) if ong else pedidos.none()

    def get_readonly_fields(self, request, obj=None):
        campos = super().get_readonly_fields(request, obj)
        if self.restrito_a_ong(request):
            # A ONG decide o status e responde, mas não troca o animal nem o adotante.
            return [*campos, "pet", "adotante", "mensagem"]
        return campos

    @admin.display(description="ONG", ordering="pet__ong__nome_fantasia")
    def ong(self, obj):
        return obj.pet.ong

    @admin.display(description="status", ordering="status")
    def status_colorido(self, obj):
        return format_html(
            '<span class="badge {}">{}</span>',
            CORES_STATUS[obj.status],
            obj.get_status_display(),
        )


@admin.register(Favorito)
class FavoritoAdmin(admin.ModelAdmin):
    list_display = ["pet", "usuario", "criado_em"]
    list_filter = ["pet__especie", ("pet__ong", admin.RelatedOnlyFieldListFilter), "criado_em"]
    list_select_related = ["pet__especie", "usuario"]
    search_fields = ["pet__nome", "usuario__username", "usuario__email"]
    date_hierarchy = "criado_em"
    autocomplete_fields = ["usuario", "pet"]


@admin.register(Acompanhamento)
class AcompanhamentoAdmin(admin.ModelAdmin):
    list_display = ["miniatura", "animal", "adotante", "data"]
    list_display_links = ["animal"]
    list_filter = ["data", "pedido__pet__especie"]
    list_select_related = ["pedido__pet", "pedido__adotante"]
    search_fields = ["relato", "pedido__pet__nome", "pedido__adotante__username"]
    date_hierarchy = "data"
    autocomplete_fields = ["pedido"]
    readonly_fields = ["miniatura"]
    fields = ["pedido", "data", "relato", "foto", "miniatura"]

    @admin.display(description="animal", ordering="pedido__pet__nome")
    def animal(self, obj):
        return obj.pedido.pet.nome

    @admin.display(description="adotante", ordering="pedido__adotante__username")
    def adotante(self, obj):
        return obj.pedido.adotante

    @admin.display(description="foto")
    def miniatura(self, obj):
        if not obj.foto:
            return "-"
        return format_html(
            '<img src="{}" alt="" style="height: 48px; width: 48px; object-fit: cover; border-radius: 4px;">',
            obj.foto.url,
        )
