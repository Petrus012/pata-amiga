# Testes do comando fotos_demo e das fotos de demonstração versionadas.
import io
import shutil
import tempfile

from django.core.management import call_command
from django.test import TestCase, override_settings
from PIL import Image

from contas.models import Ong, Usuario

from .management.commands.fotos_demo import PASTA_FOTOS
from .models import Especie, Pet


class FotosDemoTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        responsavel = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.especies = {
            nome: Especie.objects.create(nome=nome)
            for nome in ["Cachorro", "Gato", "Coelho", "Calopsita"]
        }

    def setUp(self):
        self.pasta_media = tempfile.mkdtemp()
        configuracao = override_settings(MEDIA_ROOT=self.pasta_media)
        configuracao.enable()
        self.addCleanup(configuracao.disable)
        self.addCleanup(shutil.rmtree, self.pasta_media, ignore_errors=True)

    def criar_pet(self, nome, especie, **extras):
        return Pet.objects.create(
            nome=nome,
            especie=self.especies[especie],
            ong=self.ong,
            sexo=Pet.Sexo.MACHO,
            porte=Pet.Porte.MEDIO,
            idade_aproximada=3,
            descricao="Dócil.",
            **extras,
        )

    def rodar(self):
        saida = io.StringIO()
        call_command("fotos_demo", stdout=saida)
        return saida.getvalue()

    def test_animais_sem_foto_recebem_foto_da_propria_especie(self):
        pets = [self.criar_pet(f"Pet {e}", e) for e in ["Cachorro", "Gato", "Coelho"]]
        self.rodar()
        for pet in pets:
            with self.subTest(especie=pet.especie.nome):
                pet.refresh_from_db()
                self.assertTrue(pet.foto.name.startswith("pets/"))
                self.assertTrue(pet.foto.storage.exists(pet.foto.name))

    def test_foto_enviada_pela_ong_nao_e_trocada(self):
        pet = self.criar_pet("Rex", "Cachorro", foto="pets/foto-da-ong.jpg")
        self.rodar()
        pet.refresh_from_db()
        self.assertEqual(pet.foto.name, "pets/foto-da-ong.jpg")

    def test_especie_sem_foto_disponivel_fica_sem_foto_e_e_avisada(self):
        pet = self.criar_pet("Piu", "Calopsita")
        saida = self.rodar()
        pet.refresh_from_db()
        self.assertFalse(pet.foto)
        self.assertIn("1 ficaram sem", saida)

    def test_animais_da_mesma_especie_recebem_fotos_diferentes(self):
        gatos = [self.criar_pet(f"Gato {i}", "Gato") for i in range(3)]
        self.rodar()
        tamanhos = set()
        for gato in gatos:
            gato.refresh_from_db()
            tamanhos.add(gato.foto.size)
        self.assertEqual(len(tamanhos), 3)

    def test_rodar_de_novo_nao_altera_nada(self):
        pet = self.criar_pet("Rex", "Cachorro")
        self.rodar()
        pet.refresh_from_db()
        primeira = pet.foto.name
        saida = self.rodar()
        pet.refresh_from_db()
        self.assertEqual(pet.foto.name, primeira)
        self.assertIn("0 animais receberam", saida)


class ArquivosDasFotosTests(TestCase):
    def fotos(self):
        return sorted(PASTA_FOTOS.glob("*.jpg"))

    def test_ha_fotos_para_as_especies_da_fixture(self):
        prefixos = {foto.stem.rsplit("-", 1)[0] for foto in self.fotos()}
        self.assertTrue({"cachorro", "gato", "coelho"} <= prefixos)

    def test_toda_foto_tem_a_origem_registrada_nos_creditos(self):
        creditos = (PASTA_FOTOS / "CREDITOS.md").read_text(encoding="utf-8")
        for foto in self.fotos():
            with self.subTest(foto=foto.name):
                self.assertIn(f"`{foto.name}`", creditos)

    def test_fotos_na_proporcao_dos_cards(self):
        for foto in self.fotos():
            with self.subTest(foto=foto.name), Image.open(foto) as imagem:
                self.assertEqual(imagem.size, (800, 600))
