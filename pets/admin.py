from django.contrib import admin
from django.db.models import Count
from django.utils.html import format_html

from .models import FAIXAS_ETARIAS, Especie, Pet, Raca, Vacina, filtro_faixa_etaria


class FaixaEtariaFilter(admin.SimpleListFilter):
    """Pet.faixa_etaria é uma propriedade, então o filtro usa os limites como consulta."""

    title = "faixa etária"
    parameter_name = "faixa_etaria"

    def lookups(self, request, model_admin):
        return [(chave, rotulo) for chave, rotulo, _, _ in FAIXAS_ETARIAS]

    def queryset(self, request, queryset):
        filtro = filtro_faixa_etaria(self.value())
        if filtro is not None:
            return queryset.filter(filtro)
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

    # Restrição da ONG: mesma regra do PedidoAdocaoAdmin. O superusuário vê tudo, e a
    # ONG vê e cadastra só os próprios animais, sem nem ver o campo ONG responsável.

    def restrito_a_ong(self, request):
        return request.user.eh_ong and not request.user.is_superuser

    def get_queryset(self, request):
        animais = super().get_queryset(request)
        if not self.restrito_a_ong(request):
            return animais
        # Os filtros da lateral e a busca partem deste queryset, então também ficam
        # restritos. Animal de outra ONG não aparece nem abre pelo endereço direto.
        ong = getattr(request.user, "ong", None)
        return animais.filter(ong=ong) if ong else animais.none()

    def has_add_permission(self, request):
        # Usuário do tipo ONG sem registro de Ong não teria a quem atribuir o animal.
        if self.restrito_a_ong(request) and not hasattr(request.user, "ong"):
            return False
        return super().has_add_permission(request)

    def sem_campo_ong(self, request, campos):
        if not self.restrito_a_ong(request):
            return campos

        # Um item pode ser o nome do campo ou uma tupla (campo, filtro), como no filtro
        # de ONG, ou ainda uma classe de filtro, como FaixaEtariaFilter.
        def e_ong(item):
            return item == "ong" or (isinstance(item, tuple) and item[0] == "ong")

        return [item for item in campos if not e_ong(item)]

    def get_fieldsets(self, request, obj=None):
        fieldsets = super().get_fieldsets(request, obj)
        if not self.restrito_a_ong(request):
            return fieldsets
        return [
            (nome, {**opcoes, "fields": [c for c in opcoes["fields"] if c != "ong"]})
            for nome, opcoes in fieldsets
        ]

    def get_list_display(self, request):
        return self.sem_campo_ong(request, super().get_list_display(request))

    def get_list_filter(self, request):
        return self.sem_campo_ong(request, super().get_list_filter(request))

    def get_autocomplete_fields(self, request):
        # Sem isto, o campo ONG virava uma busca que o grupo ONG não tem permissão de
        # consultar, e o cadastro mostrava "Os resultados não puderam ser carregados".
        return self.sem_campo_ong(request, super().get_autocomplete_fields(request))

    def save_model(self, request, obj, form, change):
        if self.restrito_a_ong(request) and not change:
            obj.ong = request.user.ong
        super().save_model(request, obj, form, change)


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
