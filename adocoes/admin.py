from django.contrib import admin

from .models import STATUS_EM_ABERTO, Acompanhamento, PedidoAdocao


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
    list_display = ["pet", "adotante", "ong", "status", "solicitado_em", "respondido_em"]
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
