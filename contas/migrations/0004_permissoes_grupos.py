from django.apps import apps as registro_global
from django.contrib.auth.management import create_permissions
from django.db import migrations

PERMISSOES = {
    "ONG": [
        ("pets", ["add_pet", "change_pet", "delete_pet", "view_pet"]),
        ("pets", ["add_vacina", "change_vacina", "delete_vacina", "view_vacina"]),
        ("pets", ["view_especie", "view_raca"]),
        ("adocoes", ["view_pedidoadocao", "change_pedidoadocao"]),
    ],
    "Adotante": [
        ("pets", ["view_pet", "view_especie", "view_raca"]),
        ("adocoes", ["add_pedidoadocao", "view_pedidoadocao"]),
        ("adocoes", ["add_favorito", "delete_favorito", "view_favorito"]),
        ("adocoes", ["add_acompanhamento", "view_acompanhamento"]),
    ],
}


def garantir_permissoes():
    """As permissoes nascem no post_migrate, que roda depois desta migracao.

    Sem forcar a criacao aqui, o filtro abaixo nao encontraria nada e os
    grupos ficariam vazios.
    """
    for app_label in ("pets", "adocoes"):
        create_permissions(registro_global.get_app_config(app_label), verbosity=0)


def aplicar(apps, schema_editor):
    garantir_permissoes()

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")

    for nome_grupo, blocos in PERMISSOES.items():
        grupo, _ = Group.objects.get_or_create(name=nome_grupo)
        for app_label, codenames in blocos:
            permissoes = Permission.objects.filter(
                content_type__app_label=app_label,
                codename__in=codenames,
            )
            grupo.permissions.add(*permissoes)


def reverter(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for grupo in Group.objects.filter(name__in=PERMISSOES):
        grupo.permissions.clear()


class Migration(migrations.Migration):

    dependencies = [
        ("contas", "0003_grupos_padrao"),
        ("pets", "0002_rotulo_especie"),
        ("adocoes", "0004_acompanhamento_so_de_pedido_concluido"),
    ]

    operations = [
        migrations.RunPython(aplicar, reverter),
    ]