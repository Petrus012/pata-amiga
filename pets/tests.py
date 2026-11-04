import io
import tempfile

from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.core.exceptions import ValidationError
from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from PIL import Image

from contas.models import Ong

from .models import Especie, Pet, Raca, Vacina


class PetCleanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.gato = Especie.objects.create(nome="Gato")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)

    def test_recusa_raca_de_outra_especie(self):
        pet = Pet(nome="Mimi", especie=self.gato, raca=self.poodle)
        with self.assertRaisesMessage(ValidationError, "não pertence à espécie"):
            pet.clean()

    def test_aceita_raca_da_mesma_especie(self):
        Pet(nome="Rex", especie=self.cachorro, raca=self.poodle).clean()

    def test_aceita_animal_sem_raca(self):
        Pet(nome="Tom", especie=self.gato).clean()


class RacaTests(TestCase):
    def test_nome_repetido_so_e_barrado_na_mesma_especie(self):
        cachorro = Especie.objects.create(nome="Cachorro")
        gato = Especie.objects.create(nome="Gato")
        Raca.objects.create(nome="SRD", especie=cachorro)
        Raca.objects.create(nome="SRD", especie=gato)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Raca.objects.create(nome="SRD", especie=cachorro)


class FixtureEspeciesRacasTests(TestCase):
    fixtures = ["especies_racas"]

    def test_toda_especie_tem_racas_e_opcao_srd(self):
        self.assertEqual(Especie.objects.count(), 3)
        for especie in Especie.objects.all():
            with self.subTest(especie=especie.nome):
                self.assertTrue(especie.racas.filter(nome="SRD").exists())

    def test_acentos_foram_preservados(self):
        self.assertTrue(Raca.objects.filter(nome="Pastor Alemão").exists())


class FaixaEtariaTests(TestCase):
    def test_limites_de_cada_faixa(self):
        casos = {
            0: "Filhote",
            1: "Jovem",
            2: "Jovem",
            3: "Adulto",
            7: "Adulto",
            8: "Idoso",
        }
        for idade, esperado in casos.items():
            with self.subTest(idade=idade):
                self.assertEqual(Pet(idade_aproximada=idade).faixa_etaria, esperado)


class AdminBaseTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.admin_user = Usuario.objects.create_superuser("admin", "a@a.com", "senha")
        responsavel = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.gato = Especie.objects.create(nome="Gato")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)
        cls.siames = Raca.objects.create(nome="Siamês", especie=cls.gato)

    def setUp(self):
        self.client.force_login(self.admin_user)

    def criar_pet(self, nome, idade=3, especie=None, raca=None, **extras):
        return Pet.objects.create(
            nome=nome,
            especie=especie or self.cachorro,
            raca=raca,
            ong=self.ong,
            sexo=Pet.Sexo.MACHO,
            porte=Pet.Porte.MEDIO,
            idade_aproximada=idade,
            descricao="Dócil.",
            **extras,
        )


class PetAdminListaTests(AdminBaseTestCase):
    def setUp(self):
        super().setUp()
        self.url = reverse("admin:pets_pet_changelist")

    def nomes_listados(self, resposta):
        return {pet.nome for pet in resposta.context["cl"].queryset}

    def test_exige_autenticacao(self):
        self.client.logout()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("admin:login"), resposta.url)

    def test_lista_abre_com_cada_filtro(self):
        self.criar_pet("Rex")
        inicio_de_hoje = timezone.localtime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        filtros = [
            {"status__exact": Pet.Status.DISPONIVEL},
            {"especie__id__exact": self.cachorro.pk},
            {"porte__exact": Pet.Porte.MEDIO},
            {"sexo__exact": Pet.Sexo.MACHO},
            {"faixa_etaria": "adulto"},
            {"castrado__exact": 0},
            {"vacinado__exact": 0},
            {"ong__id__exact": self.ong.pk},
            {"criado_em__gte": str(inicio_de_hoje)},
            {"q": "Rex"},
            {"q": "Patas Livres"},
        ]
        for filtro in filtros:
            with self.subTest(filtro=filtro):
                resposta = self.client.get(self.url, filtro)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(self.nomes_listados(resposta), {"Rex"})

    def test_filtro_exclui_quem_nao_combina(self):
        self.criar_pet("Rex", castrado=False)
        self.criar_pet("Bob", castrado=True)
        resposta = self.client.get(self.url, {"castrado__exact": 1})
        self.assertEqual(self.nomes_listados(resposta), {"Bob"})

    def test_filtro_de_faixa_etaria_respeita_os_limites(self):
        for nome, idade in [("A", 0), ("B", 1), ("C", 2), ("D", 3), ("E", 7), ("F", 8)]:
            self.criar_pet(nome, idade=idade)
        casos = {
            "filhote": {"A"},
            "jovem": {"B", "C"},
            "adulto": {"D", "E"},
            "idoso": {"F"},
        }
        for faixa, esperado in casos.items():
            with self.subTest(faixa=faixa):
                resposta = self.client.get(self.url, {"faixa_etaria": faixa})
                self.assertEqual(self.nomes_listados(resposta), esperado)

    def test_miniatura_aparece_so_com_foto(self):
        self.criar_pet("Com foto", foto="pets/teste.jpg")
        self.criar_pet("Sem foto")
        resposta = self.client.get(self.url)
        self.assertContains(resposta, 'src="/media/pets/teste.jpg"', count=1)

    def edicao_em_lista(self, pet, **campos):
        dados = {
            "form-TOTAL_FORMS": 1,
            "form-INITIAL_FORMS": 1,
            "form-MIN_NUM_FORMS": 0,
            "form-MAX_NUM_FORMS": 1000,
            "form-0-id": pet.pk,
            "form-0-status": pet.status,
            "_save": "Salvar",
        }
        dados.update({f"form-0-{campo}": valor for campo, valor in campos.items()})
        return self.client.post(self.url, dados)

    def test_edicao_direta_na_lista(self):
        pet = self.criar_pet("Rex")
        resposta = self.edicao_em_lista(pet, status=Pet.Status.ADOTADO, castrado="on")
        self.assertEqual(resposta.status_code, 302)
        pet.refresh_from_db()
        self.assertEqual(pet.status, Pet.Status.ADOTADO)
        self.assertTrue(pet.castrado)
        self.assertFalse(pet.vacinado)

    def test_edicao_na_lista_nao_quebra_com_raca_inconsistente(self):
        # Trocar a espécie de uma raça pelo admin deixa animais antigos inconsistentes.
        pet = self.criar_pet("Rex", raca=self.poodle)
        Raca.objects.filter(pk=self.poodle.pk).update(especie=self.gato)
        resposta = self.edicao_em_lista(pet, status=Pet.Status.ADOTADO)
        self.assertEqual(resposta.status_code, 200)
        # O Jazzmin não exibe erros gerais de linha, então a conferência é no formulário.
        erros = resposta.context["cl"].formset.forms[0].non_field_errors()
        self.assertIn("não pertence à espécie", str(erros))
        pet.refresh_from_db()
        self.assertEqual(pet.status, Pet.Status.DISPONIVEL)


class PetAdminFormularioTests(AdminBaseTestCase):
    def dados_validos(self, **extras):
        dados = {
            "nome": "Luna",
            "especie": self.cachorro.pk,
            "raca": self.poodle.pk,
            "ong": self.ong.pk,
            "sexo": Pet.Sexo.FEMEA,
            "porte": Pet.Porte.PEQUENO,
            "idade_aproximada": 2,
            "descricao": "Brincalhona.",
            "status": Pet.Status.DISPONIVEL,
            "vacinas-TOTAL_FORMS": 1,
            "vacinas-INITIAL_FORMS": 0,
            "vacinas-MIN_NUM_FORMS": 0,
            "vacinas-MAX_NUM_FORMS": 1000,
            "vacinas-0-nome": "V10",
            "vacinas-0-data_aplicacao": "01/10/2026",
        }
        dados.update(extras)
        return dados

    def test_formularios_abrem_com_inline_de_vacinas(self):
        pet = self.criar_pet("Rex")
        Vacina.objects.create(pet=pet, nome="V8", data_aplicacao=timezone.localdate())
        urls = [
            reverse("admin:pets_pet_add"),
            reverse("admin:pets_pet_change", args=[pet.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, "vacinas-TOTAL_FORMS")

    def test_nao_oferece_ver_no_site_enquanto_a_rota_nao_existe(self):
        pet = self.criar_pet("Rex")
        resposta = self.client.get(reverse("admin:pets_pet_change", args=[pet.pk]))
        self.assertNotContains(resposta, "/admin/r/")

    def test_cadastro_com_foto_e_vacina(self):
        imagem = io.BytesIO()
        Image.new("RGB", (2, 2)).save(imagem, format="PNG")
        foto = SimpleUploadedFile("luna.png", imagem.getvalue(), "image/png")
        with tempfile.TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta):
            resposta = self.client.post(
                reverse("admin:pets_pet_add"), self.dados_validos(foto=foto)
            )
            self.assertEqual(resposta.status_code, 302)
            pet = Pet.objects.get(nome="Luna")
            self.assertTrue(pet.foto.name.endswith(".png"))
            self.assertEqual(pet.vacinas.get().nome, "V10")
            # Fecha o arquivo antes de a pasta temporária ser apagada no Windows.
            pet.foto.close()

    def test_cadastro_recusa_raca_de_outra_especie(self):
        resposta = self.client.post(
            reverse("admin:pets_pet_add"),
            self.dados_validos(especie=self.gato.pk, raca=self.poodle.pk),
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não pertence à espécie")
        self.assertFalse(Pet.objects.filter(nome="Luna").exists())

    def test_autocomplete_de_raca_e_ong(self):
        casos = [("raca", "Poodle", "Poodle"), ("ong", "Patas", "Patas Livres")]
        for campo, termo, esperado in casos:
            with self.subTest(campo=campo):
                resposta = self.client.get(
                    reverse("admin:autocomplete"),
                    {
                        "app_label": "pets",
                        "model_name": "pet",
                        "field_name": campo,
                        "term": termo,
                    },
                )
                self.assertEqual(resposta.status_code, 200)
                self.assertContains(resposta, esperado)


class TemaJazzminTests(AdminBaseTestCase):
    def test_login_usa_a_marca_do_projeto(self):
        self.client.logout()
        resposta = self.client.get(reverse("admin:login"))
        self.assertContains(resposta, "Painel administrativo da Pata Amiga")
        self.assertContains(resposta, "img/logo.png")
        self.assertNotContains(resposta, "AdminLTELogo")

    def test_painel_usa_tema_menu_e_seletor_de_modo(self):
        resposta = self.client.get(reverse("admin:index"))
        self.assertContains(resposta, "bootswatch/flatly/bootstrap.min.css")
        self.assertContains(resposta, "jazzmin-mode-select")
        self.assertContains(resposta, "fas fa-dog")
        self.assertContains(resposta, "fas fa-hand-holding-heart")
        self.assertContains(resposta, reverse("admin:pets_pet_changelist"))
        self.assertContains(resposta, reverse("admin:contas_ong_changelist"))

    def test_arquivos_proprios_estao_nos_estaticos(self):
        for caminho in ["img/logo.png", "css/admin.css"]:
            with self.subTest(caminho=caminho):
                self.assertIsNotNone(finders.find(caminho))

    def test_rotulo_de_especie_tem_acento_no_formulario(self):
        resposta = self.client.get(reverse("admin:pets_pet_add"))
        self.assertContains(resposta, "css/admin.css")
        self.assertContains(resposta, "Espécie")


class EspecieRacaAdminTests(AdminBaseTestCase):
    def test_totais_nao_se_multiplicam_entre_as_relacoes(self):
        Raca.objects.create(nome="Beagle", especie=self.cachorro)
        Raca.objects.create(nome="Labrador", especie=self.cachorro)
        self.criar_pet("Rex")
        self.criar_pet("Bob")
        resposta = self.client.get(reverse("admin:pets_especie_changelist"))
        self.assertEqual(resposta.status_code, 200)
        especie = resposta.context["cl"].queryset.get(pk=self.cachorro.pk)
        self.assertEqual(especie.num_racas, 3)
        self.assertEqual(especie.num_animais, 2)

    def test_lista_de_racas_filtra_por_especie(self):
        resposta = self.client.get(
            reverse("admin:pets_raca_changelist"),
            {"especie__id__exact": self.gato.pk},
        )
        self.assertEqual(resposta.status_code, 200)
        nomes = {raca.nome for raca in resposta.context["cl"].queryset}
        self.assertEqual(nomes, {"Siamês"})
