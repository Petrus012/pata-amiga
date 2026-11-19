from pathlib import Path

from django.core.files import File
from django.core.management.base import BaseCommand
from django.utils.text import slugify

from pets.models import Pet

# Fotos CC0 versionadas no projeto, com a origem de cada uma em CREDITOS.md.
# O nome do arquivo começa pela espécie em minúsculas: cachorro-01.jpg, gato-03.jpg...
PASTA_FOTOS = Path(__file__).resolve().parents[2] / "fotos_demo"


class Command(BaseCommand):
    help = "Coloca fotos de demonstração nos animais que ainda não têm foto."

    def fotos_por_especie(self):
        fotos = {}
        for arquivo in sorted(PASTA_FOTOS.glob("*.jpg")):
            especie = arquivo.stem.rsplit("-", 1)[0]
            fotos.setdefault(especie, []).append(arquivo)
        return fotos

    def handle(self, *args, **options):
        fotos = self.fotos_por_especie()
        usadas = {}
        com_foto = sem_foto_disponivel = 0

        # Só animais sem foto: a foto que a ONG enviou nunca é trocada.
        for pet in Pet.objects.filter(foto="").select_related("especie").order_by("pk"):
            especie = slugify(pet.especie.nome)
            opcoes = fotos.get(especie)
            if not opcoes:
                sem_foto_disponivel += 1
                continue
            # Revezamento dentro da espécie, para animais vizinhos no catálogo não
            # aparecerem com a mesma foto.
            arquivo = opcoes[usadas.get(especie, 0) % len(opcoes)]
            usadas[especie] = usadas.get(especie, 0) + 1
            with arquivo.open("rb") as conteudo:
                pet.foto.save(f"{slugify(pet.nome) or 'animal'}.jpg", File(conteudo), save=False)
            pet.save(update_fields=["foto", "atualizado_em"])
            com_foto += 1

        mensagem = f"{com_foto} animais receberam foto de demonstração."
        if sem_foto_disponivel:
            mensagem += f" {sem_foto_disponivel} ficaram sem, por não haver foto da espécie."
        self.stdout.write(self.style.SUCCESS(mensagem))
