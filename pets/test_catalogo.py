# Testes do catálogo público. Os de modelos e admin do app ficam no tests.py.
from django.test import TestCase
from django.urls import reverse

from contas.models import Ong, Usuario

from .models import Especie, Pet, Raca


class CatalogoTests(TestCase):
    url = reverse("pets:catalogo")

    @classmethod
    def setUpTestData(cls):
        responsavel = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.gato = Especie.objects.create(nome="Gato")
        cls.siames = Raca.objects.create(nome="Siamês", especie=cls.gato)

    def criar_pet(self, nome, **extras):
        dados = {
            "especie": self.gato,
            "ong": self.ong,
            "sexo": Pet.Sexo.FEMEA,
            "porte": Pet.Porte.PEQUENO,
            "idade_aproximada": 2,
            "descricao": "Carinhosa.",
        }
        dados.update(extras)
        return Pet.objects.create(nome=nome, **dados)

    def nomes_listados(self, resposta):
        return [pet.nome for pet in resposta.context["pets"]]

    def test_usa_o_template_do_catalogo_com_o_base(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertTemplateUsed(resposta, "pets/catalogo.html")
        self.assertTemplateUsed(resposta, "base.html")

    def test_animal_adotado_sai_do_catalogo(self):
        self.criar_pet("Mimi")
        self.criar_pet("Nina", status=Pet.Status.EM_PROCESSO)
        self.criar_pet("Tom", status=Pet.Status.ADOTADO)
        resposta = self.client.get(self.url)
        self.assertEqual(set(self.nomes_listados(resposta)), {"Mimi", "Nina"})
        self.assertContains(resposta, "2 animais esperando")

    def test_card_mostra_os_dados_do_animal(self):
        self.criar_pet(
            "Mimi",
            raca=self.siames,
            castrado=True,
            vacinado=False,
            status=Pet.Status.EM_PROCESSO,
        )
        resposta = self.client.get(self.url)
        for trecho in [
            "Mimi",
            "Siamês",
            "Fêmea",
            "Porte pequeno",
            "Jovem",
            "Castrado",
            "Em processo de adoção",
            "Patas Livres",
            "Lavras",
        ]:
            with self.subTest(trecho=trecho):
                self.assertContains(resposta, trecho)
        self.assertNotContains(resposta, "Vacinado")

    def test_animal_sem_foto_mostra_espaco_reservado(self):
        self.criar_pet("Mimi")
        self.criar_pet("Nina", foto="pets/nina.jpg")
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "foto-pendente", count=1)
        self.assertContains(resposta, 'src="/media/pets/nina.jpg"', count=1)

    def test_catalogo_vazio_avisa_o_usuario(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Nenhum animal disponível no momento.")

    def test_mais_recentes_primeiro(self):
        for nome in ["Primeiro", "Segundo", "Terceiro"]:
            self.criar_pet(nome)
        resposta = self.client.get(self.url)
        self.assertEqual(self.nomes_listados(resposta), ["Terceiro", "Segundo", "Primeiro"])

    def test_consulta_nao_cresce_com_o_numero_de_animais(self):
        for indice in range(12):
            self.criar_pet(f"Pet {indice}", raca=self.siames)
        # Uma consulta para a contagem da paginação e outra para a listagem com
        # espécie, raça e ONG já carregadas. Sem select_related seriam dezenas.
        with self.assertNumQueries(2):
            self.client.get(self.url)

    def test_pagina_de_doze_em_doze(self):
        for indice in range(13):
            self.criar_pet(f"Pet {indice}")
        primeira = self.client.get(self.url)
        self.assertEqual(len(self.nomes_listados(primeira)), 12)
        self.assertContains(primeira, "1 de 2")
        self.assertContains(primeira, 'href="?page=2"')

        segunda = self.client.get(self.url, {"page": 2})
        self.assertEqual(self.nomes_listados(segunda), ["Pet 0"])
        self.assertContains(segunda, 'href="?page=1"')

    def test_paginacao_mantem_os_outros_parametros_da_url(self):
        for indice in range(13):
            self.criar_pet(f"Pet {indice}")
        resposta = self.client.get(self.url, {"q": "gato"})
        self.assertContains(resposta, 'href="?q=gato&amp;page=2"')

    def test_sem_paginacao_quando_cabe_em_uma_pagina(self):
        self.criar_pet("Mimi")
        self.assertNotContains(self.client.get(self.url), 'aria-label="Paginação"')

    def test_menu_destaca_animais_e_a_inicial_leva_ao_catalogo(self):
        catalogo = self.client.get(self.url).content.decode()
        self.assertRegex(catalogo, rf'nav-link active"\s+href="{self.url}"')
        inicial = self.client.get(reverse("home"))
        self.assertContains(inicial, f'href="{self.url}"', count=2)
