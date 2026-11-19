# Testes da busca e dos filtros do catálogo. Os testes gerais do catálogo ficam em test_catalogo.py.
from django.test import TestCase
from django.urls import reverse

from contas.models import Ong, Usuario

from .models import Especie, Pet, Raca


class BuscaTestCase(TestCase):
    url = reverse("pets:catalogo")

    @classmethod
    def setUpTestData(cls):
        responsavel = Usuario.objects.create_user("ong1", password="senha", tipo=Usuario.Tipo.ONG)
        cls.patas = Ong.objects.create(
            responsavel=responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        outro = Usuario.objects.create_user("ong2", password="senha", tipo=Usuario.Tipo.ONG)
        cls.focinhos = Ong.objects.create(
            responsavel=outro, nome_fantasia="Lar dos Focinhos", cidade="Formiga"
        )
        cls.adotante = Usuario.objects.create_user("ana", password="senha")
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.gato = Especie.objects.create(nome="Gato")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)
        cls.siames = Raca.objects.create(nome="Siamês", especie=cls.gato)

        def pet(nome, especie, ong, **extras):
            dados = {
                "sexo": Pet.Sexo.MACHO,
                "porte": Pet.Porte.MEDIO,
                "idade_aproximada": 3,
                "descricao": "Dócil.",
            }
            dados.update(extras)
            return Pet.objects.create(nome=nome, especie=especie, ong=ong, **dados)

        pet("Rex", cls.cachorro, cls.patas, raca=cls.poodle, porte=Pet.Porte.PEQUENO)
        pet("Thor", cls.cachorro, cls.focinhos, porte=Pet.Porte.GRANDE, idade_aproximada=9)
        pet("Mimi", cls.gato, cls.patas, raca=cls.siames, sexo=Pet.Sexo.FEMEA, idade_aproximada=0)
        pet("Nina", cls.gato, cls.focinhos, sexo=Pet.Sexo.FEMEA, idade_aproximada=1)
        pet("Tom", cls.gato, cls.patas, status=Pet.Status.ADOTADO)

    def setUp(self):
        self.client.force_login(self.adotante)

    def nomes(self, **filtros):
        resposta = self.client.get(self.url, filtros)
        self.assertEqual(resposta.status_code, 200)
        return {pet.nome for pet in resposta.context["pets"]}


class BuscaPorTextoTests(BuscaTestCase):
    def test_busca_em_nome_raca_especie_ong_e_cidade(self):
        casos = {
            "rex": {"Rex"},
            "siam": {"Mimi"},
            "GATO": {"Mimi", "Nina"},
            "focinhos": {"Thor", "Nina"},
            "lavras": {"Rex", "Mimi"},
        }
        for termo, esperado in casos.items():
            with self.subTest(termo=termo):
                self.assertEqual(self.nomes(q=termo), esperado)

    def test_cada_palavra_precisa_aparecer(self):
        self.assertEqual(self.nomes(q="gato lavras"), {"Mimi"})
        self.assertEqual(self.nomes(q="  gato   formiga "), {"Nina"})

    def test_animal_adotado_continua_fora_mesmo_na_busca(self):
        self.assertNotIn("Tom", self.nomes(q="tom"))


class FiltrosTests(BuscaTestCase):
    def test_cada_filtro_sozinho(self):
        casos = [
            ({"especie": self.cachorro.pk}, {"Rex", "Thor"}),
            ({"porte": Pet.Porte.PEQUENO}, {"Rex"}),
            ({"sexo": Pet.Sexo.FEMEA}, {"Mimi", "Nina"}),
            ({"faixa": "filhote"}, {"Mimi"}),
            ({"faixa": "jovem"}, {"Nina"}),
            ({"faixa": "idoso"}, {"Thor"}),
        ]
        for filtros, esperado in casos:
            with self.subTest(filtros=filtros):
                self.assertEqual(self.nomes(**filtros), esperado)

    def test_filtros_combinados_com_busca(self):
        self.assertEqual(self.nomes(especie=self.gato.pk, sexo=Pet.Sexo.FEMEA, q="lavras"), {"Mimi"})
        self.assertEqual(self.nomes(especie=self.cachorro.pk, faixa="filhote"), set())

    def test_valor_invalido_e_ignorado_sem_derrubar_os_outros(self):
        todos = {"Rex", "Thor", "Mimi", "Nina"}
        for filtros in [{"especie": 999}, {"especie": "abc"}, {"porte": "X"}, {"faixa": "bebe"}]:
            with self.subTest(filtros=filtros):
                self.assertEqual(self.nomes(**filtros), todos)
        self.assertEqual(self.nomes(especie=999, sexo=Pet.Sexo.FEMEA), {"Mimi", "Nina"})


class TelaDeBuscaTests(BuscaTestCase):
    def test_formulario_mantem_os_valores_escolhidos(self):
        resposta = self.client.get(self.url, {"q": "rex", "porte": Pet.Porte.PEQUENO})
        self.assertContains(resposta, 'value="rex"')
        self.assertContains(resposta, f'<option value="{Pet.Porte.PEQUENO}" selected>')

    def test_contagem_e_limpar_aparecem_so_com_filtro(self):
        sem_filtro = self.client.get(self.url)
        self.assertContains(sem_filtro, "4 animais esperando")
        self.assertNotContains(sem_filtro, ">Limpar<")

        com_filtro = self.client.get(self.url, {"q": "rex"})
        self.assertContains(com_filtro, "1 animal encontrado")
        self.assertContains(com_filtro, ">Limpar<")

    def test_busca_sem_resultado_tem_mensagem_propria(self):
        resposta = self.client.get(self.url, {"q": "dinossauro"})
        self.assertContains(resposta, "Nenhum animal encontrado com esses filtros.")
        self.assertNotContains(resposta, "Nenhum animal disponível no momento.")

    def test_menus_sem_texto_em_ingles(self):
        self.assertNotContains(self.client.get(self.url), "Select an option")

    def test_paginacao_mantem_os_filtros(self):
        for indice in range(13):
            Pet.objects.create(
                nome=f"Gato {indice}",
                especie=self.gato,
                ong=self.patas,
                sexo=Pet.Sexo.MACHO,
                porte=Pet.Porte.MEDIO,
                idade_aproximada=3,
                descricao="Dócil.",
            )
        resposta = self.client.get(self.url, {"especie": self.gato.pk, "sexo": Pet.Sexo.MACHO})
        self.assertContains(resposta, "13 animais encontrados")
        self.assertContains(
            resposta, f'href="?especie={self.gato.pk}&amp;sexo={Pet.Sexo.MACHO}&amp;page=2"'
        )
        segunda = self.client.get(
            self.url, {"especie": self.gato.pk, "sexo": Pet.Sexo.MACHO, "page": 2}
        )
        self.assertEqual(len(segunda.context["pets"]), 1)
