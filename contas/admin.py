from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Ong, Perfil, Usuario


class PerfilInline(admin.StackedInline):
    model = Perfil
    can_delete = False
    verbose_name_plural = "perfil"


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    inlines = [PerfilInline]
    list_display = ["username", "nome_completo", "tipo", "cidade", "is_active"]
    list_filter = ["tipo", "is_active", "is_staff", "date_joined"]
    search_fields = ["username", "first_name", "last_name", "email", "cidade"]
    fieldsets = UserAdmin.fieldsets + (
        ("Dados da plataforma", {"fields": ("tipo", "telefone", "cidade")}),
    )

    @admin.display(description="nome completo")
    def nome_completo(self, obj):
        return obj.get_full_name() or "-"


@admin.register(Ong)
class OngAdmin(admin.ModelAdmin):
    list_display = ["nome_fantasia", "cidade", "responsavel", "verificada", "criada_em"]
    list_filter = ["verificada", "cidade", "criada_em"]
    search_fields = ["nome_fantasia", "cnpj", "cidade"]
    list_editable = ["verificada"]
    autocomplete_fields = ["responsavel"]