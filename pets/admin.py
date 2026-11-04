from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import Especie, Pet, Raca, Vacina


class FaixaEtariaFilter(admin.SimpleListFilter):
    """Pet.faixa_etaria é uma propriedade, então o filtro repete os limites como consulta."""

    title = "faixa etária"
    parameter_name = "faixa_etaria"

    FAIXAS = {
        "filhote": ("Filhote", {"idade_aproximada": 0}),
        "jovem": ("Jovem", {"idade_aproximada__range": (1, 2)}),
        "adulto": ("Adulto", {"idade_aproximada__range": (3, 7)}),
        "idoso": ("Idoso", {"idade_aproximada__gte": 8}),
    }

    def lookups(self, request, model_admin):
        return [(chave, rotulo) for chave, (rotulo, _) in self.FAIXAS.items()]

    def queryset(self, request, queryset):
        faixa = self.FAIXAS.get(self.value())
        if faixa:
            return queryset.filter(**faixa[1])
        return queryset


class VacinaInline(admin.TabularInline):
    model = Vacina
    extra = 1
    fields = ["nome", "data_aplicacao", "observacao"]


@admin.register(Pet)
class PetAdmin(admin.ModelAdmin):
    inlines = [VacinaInline]
    list_display = [
        "miniatura",
        "nome",
        "especie",
        "raca",
        "ong",
        "porte",
        "faixa",
        "status",
        "castrado",
        "vacinado",
        "criado_em",
    ]
    list_display_links = ["nome"]
    list_editable = ["status", "castrado", "vacinado"]
    list_filter = [
        "status",
        "especie",
        "porte",
        "sexo",
        FaixaEtariaFilter,
        "castrado",
        "vacinado",
        ("ong", admin.RelatedOnlyFieldListFilter),
        "criado_em",
    ]
    list_select_related = ["especie", "raca", "ong"]
    list_per_page = 20
    search_fields = ["nome", "raca__nome", "especie__nome", "ong__nome_fantasia"]
    date_hierarchy = "criado_em"
    autocomplete_fields = ["raca", "ong"]
    readonly_fields = ["miniatura", "criado_em", "atualizado_em"]
    # A rota pets:detalhe ainda não existe. Remover quando a página de detalhe entrar.
    view_on_site = False
    fieldsets = [
        ("Identificação", {"fields": ["nome", "especie", "raca", "ong"]}),
        ("Foto", {"fields": ["foto", "miniatura"]}),
        (
            "Características",
            {"fields": ["sexo", "porte", "idade_aproximada", "descricao"]},
        ),
        ("Saúde", {"fields": ["castrado", "vacinado"]}),
        ("Adoção", {"fields": ["status"]}),
        ("Registro", {"fields": ["criado_em", "atualizado_em"]}),
    ]

    @admin.display(description="foto")
    def miniatura(self, obj):
        if not obj.foto:
            return "-"
        return format_html(
            '<img src="{}" alt="" style="height: 48px; width: 48px; object-fit: cover; border-radius: 4px;">',
            obj.foto.url,
        )

    @admin.display(description="faixa etária", ordering="idade_aproximada")
    def faixa(self, obj):
        return obj.faixa_etaria


@admin.register(Especie)
class EspecieAdmin(admin.ModelAdmin):
    list_display = ["nome", "num_racas", "num_animais"]
    search_fields = ["nome"]

    def get_queryset(self, request):
        # distinct evita multiplicar as contagens ao juntar duas relações na mesma consulta.
        return (
            super()
            .get_queryset(request)
            .annotate(
                num_racas=Count("racas", distinct=True),
                num_animais=Count("pets", distinct=True),
            )
        )

    @admin.display(description="raças", ordering="num_racas")
    def num_racas(self, obj):
        return obj.num_racas

    @admin.display(description="animais", ordering="num_animais")
    def num_animais(self, obj):
        return obj.num_animais


@admin.register(Raca)
class RacaAdmin(admin.ModelAdmin):
    list_display = ["nome", "especie"]
    list_filter = ["especie"]
    list_select_related = ["especie"]
    search_fields = ["nome", "especie__nome"]
