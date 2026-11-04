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


def aplicar(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for nome_grupo, blocos in PERMISSOES.items():
        grupo, _ = Group.objects.get_or_create(name=nome_grupo)
        for app_label, codenames in blocos:
            perms = Permission.objects.filter(
                content_type__app_label=app_label,
                codename__in=codenames,
            )
            grupo.permissions.add(*perms)


def reverter(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Group.objects.filter(name__in=PERMISSOES).update()
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