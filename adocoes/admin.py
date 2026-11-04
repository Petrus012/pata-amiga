from django.contrib import admin
from django.utils.html import format_html

from .models import STATUS_EM_ABERTO, Acompanhamento, Favorito, PedidoAdocao, StatusPedido

# Classes de cor do Bootstrap 5, que é a versão usada pelo Jazzmin.
CORES_STATUS = {
    StatusPedido.PENDENTE: "text-bg-warning",
    StatusPedido.EM_ANALISE: "text-bg-info",
    StatusPedido.APROVADO: "text-bg-success",
    StatusPedido.RECUSADO: "text-bg-danger",
    StatusPedido.CONCLUIDO: "text-bg-secondary",
}


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
