import random

from django.contrib.auth.models import Group
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction

from adocoes.models import Favorito, PedidoAdocao
from contas.models import Ong, Perfil, Usuario
from pets.models import Especie, Pet, Raca, Vacina

SENHA_PADRAO = "pataamiga123"

ONGS = [
    ("Patas Unidas", "Lavras", "Resgate e reabilitação de animais abandonados."),
    ("Lar dos Focinhos", "Formiga", "Lar temporário para cães e gatos em recuperação."),
    ("Amigo Fiel", "Varginha", "Protetores independentes atuando em rede."),
]

ADOTANTES = [
    ("ana.souza", "Ana", "Souza", "Lavras"),
    ("bruno.lima", "Bruno", "Lima", "Formiga"),
    ("carla.dias", "Carla", "Dias", "Lavras"),
    ("diego.rocha", "Diego", "Rocha", "Varginha"),
]

NOMES_PETS = [
    "Bidu", "Mel", "Thor", "Nina", "Pingo", "Luna",
    "Bento", "Amora", "Simba", "Cacau", "Zeus", "Pérola",
]

DESCRICOES = [
    "Dócil com crianças e acostumado a conviver com outros animais.",
    "Resgatado das ruas, já recuperado e pronto para uma nova família.",
    "Brincalhão, precisa de espaço para gastar energia todos os dias.",
    "Tranquilo e companheiro, prefere ambientes silenciosos.",
    "Muito apegado a pessoas, não gosta de ficar sozinho por muito tempo.",
]

VACINAS = ["V8", "V10", "Antirrábica", "Giárdia"]


class Command(BaseCommand):
    help = "Popula o banco com dados de demonstração."

    def add_arguments(self, parser):
        parser.add_argument(
            "--limpar",
            action="store_true",
            help="Remove os dados de demonstração antes de recriar.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        random.seed(116)

        if options["limpar"]:
            PedidoAdocao.objects.all().delete()
            Favorito.objects.all().delete()
            Vacina.objects.all().delete()
            Pet.objects.all().delete()
            Ong.objects.all().delete()
            Usuario.objects.filter(is_superuser=False).delete()
            self.stdout.write("Dados anteriores removidos.")

        if not Especie.objects.exists():
            call_command("loaddata", "especies_racas", verbosity=0)
            self.stdout.write("Fixture de espécies e raças carregada.")

        grupo_ong = Group.objects.get(name="ONG")
        grupo_adotante = Group.objects.get(name="Adotante")

        ongs = []
        for nome_fantasia, cidade, descricao in ONGS:
            username = nome_fantasia.lower().replace(" ", ".")
            usuario, criado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nome_fantasia,
                    "email": f"{username}@exemplo.org",
                    "tipo": Usuario.Tipo.ONG,
                    "cidade": cidade,
                    "is_staff": True,
                },
            )
            if criado:
                usuario.set_password(SENHA_PADRAO)
                usuario.save()
            usuario.groups.add(grupo_ong)

            ong, _ = Ong.objects.get_or_create(
                responsavel=usuario,
                defaults={
                    "nome_fantasia": nome_fantasia,
                    "cidade": cidade,
                    "descricao": descricao,
                    "verificada": True,
                },
            )
            ongs.append(ong)

        adotantes = []
        for username, nome, sobrenome, cidade in ADOTANTES:
            usuario, criado = Usuario.objects.get_or_create(
                username=username,
                defaults={
                    "first_name": nome,
                    "last_name": sobrenome,
                    "email": f"{username}@exemplo.com",
                    "tipo": Usuario.Tipo.ADOTANTE,
                    "cidade": cidade,
                },
            )
            if criado:
                usuario.set_password(SENHA_PADRAO)
                usuario.save()
            usuario.groups.add(grupo_adotante)

            Perfil.objects.get_or_create(
                usuario=usuario,
                defaults={
                    "tipo_moradia": random.choice(Perfil.Moradia.values),
                    "tem_outros_animais": random.choice([True, False]),
                    "bio": "Procuro um companheiro para a família.",
                },
            )
            adotantes.append(usuario)

        racas = list(Raca.objects.select_related("especie"))
        pets = []
        for indice, nome in enumerate(NOMES_PETS):
            raca = random.choice(racas)
            pet, _ = Pet.objects.get_or_create(
                nome=nome,
                ong=ongs[indice % len(ongs)],
                defaults={
                    "especie": raca.especie,
                    "raca": raca,
                    "sexo": random.choice(Pet.Sexo.values),
                    "porte": random.choice(Pet.Porte.values),
                    "idade_aproximada": random.randint(0, 11),
                    "castrado": random.choice([True, False]),
                    "vacinado": random.choice([True, False]),
                    "descricao": random.choice(DESCRICOES),
                },
            )
            pets.append(pet)

            if pet.vacinado and not pet.vacinas.exists():
                for nome_vacina in random.sample(VACINAS, 2):
                    Vacina.objects.create(
                        pet=pet,
                        nome=nome_vacina,
                        data_aplicacao="2026-08-15",
                    )

        combinacoes = [(pet, adotante) for pet in pets[:6] for adotante in adotantes]
        for pet, adotante in random.sample(combinacoes, 8):
            PedidoAdocao.objects.get_or_create(
                pet=pet,
                adotante=adotante,
                defaults={
                    "mensagem": "Tenho espaço, tempo e experiência para cuidar bem.",
                    "status": random.choice(
                        [
                            PedidoAdocao.Status.PENDENTE,
                            PedidoAdocao.Status.EM_ANALISE,
                            PedidoAdocao.Status.RECUSADO,
                        ]
                    ),
                },
            )

        for adotante in adotantes:
            for pet in random.sample(pets, 3):
                Favorito.objects.get_or_create(usuario=adotante, pet=pet)

        self.stdout.write(
            self.style.SUCCESS(
                f"Pronto: {Ong.objects.count()} ONGs, {Pet.objects.count()} animais, "
                f"{PedidoAdocao.objects.count()} pedidos, "
                f"{Favorito.objects.count()} favoritos. "
                f"Senha de todos os usuários de demonstração: {SENHA_PADRAO}"
            )
        )