# Testes da página de detalhe do animal.
from datetime import date

from django.test import TestCase
from django.urls import reverse

from adocoes.models import Favorito, PedidoAdocao, StatusPedido
from contas.models import Ong, Usuario

from .models import Especie, Pet, Raca, Vacina


class DetalheTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.responsavel = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=cls.responsavel,
            nome_fantasia="Patas Livres",
            cidade="Lavras",
            descricao="Resgate de animais abandonados.",
            verificada=True,
        )
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)
        cls.rex = Pet.objects.create(
            nome="Rex",
            especie=cls.cachorro,
            raca=cls.poodle,
            ong=cls.ong,
            sexo=Pet.Sexo.MACHO,
            porte=Pet.Porte.MEDIO,
            idade_aproximada=0,
            castrado=True,
            descricao="Dócil e brincalhão.\nGosta de crianças.",
        )
        cls.ana = Usuario.objects.create_user("ana", password="senha")

    def setUp(self):
        self.client.force_login(self.ana)
        self.url = self.rex.get_absolute_url()

    def test_url_do_animal_e_a_rota_de_detalhe(self):
        self.assertEqual(self.url, reverse("pets:detalhe", args=[self.rex.pk]))

    def test_anonimo_vai_para_o_login(self):
        self.client.logout()
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, f"{reverse('login')}?next={self.url}")

    def test_animal_inexistente_da_404(self):
        resposta = self.client.get(reverse("pets:detalhe", args=[9999]))
        self.assertEqual(resposta.status_code, 404)

    def test_mostra_os_dados_do_animal_e_da_ong(self):
        resposta = self.client.get(self.url)
        self.assertTemplateUsed(resposta, "pets/detalhe.html")
        for trecho in [
            "Rex",
            "Poodle",
            "Macho",
            "Médio",
            "Filhote",
            "Gosta de crianças.",
            "Patas Livres",
            "Lavras",
            "Resgate de animais abandonados.",
            "Verificada",
        ]:
            with self.subTest(trecho=trecho):
                self.assertContains(resposta, trecho)

    def test_lista_as_vacinas(self):
        Vacina.objects.create(pet=self.rex, nome="V10", data_aplicacao=date(2026, 8, 15))
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "V10")
        self.assertContains(resposta, "15/08/2026")

    def test_sem_vacinas_avisa(self):
        self.assertContains(self.client.get(self.url), "Nenhuma vacina registrada")

    def test_consultas_nao_crescem_com_as_vacinas(self):
        for indice in range(5):
            Vacina.objects.create(
                pet=self.rex, nome=f"Vacina {indice}", data_aplicacao=date(2026, 8, 15)
            )
        # Sessão, usuário, o animal com as relações, as vacinas, o favorito e o pedido.
        with self.assertNumQueries(6):
            self.client.get(self.url)

    def test_adotante_ve_o_botao_de_adocao_e_de_favorito(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, reverse("adocoes:solicitar", args=[self.rex.pk]))
        self.assertContains(resposta, "Favoritar")

    def test_favorito_muda_o_rotulo_do_botao(self):
        Favorito.objects.create(usuario=self.ana, pet=self.rex)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Remover dos favoritos")
        self.assertNotContains(resposta, "> Favoritar")

    def test_pedido_em_aberto_troca_o_botao_por_aviso(self):
        PedidoAdocao.objects.create(
            pet=self.rex, adotante=self.ana, mensagem="Quero.", status=StatusPedido.EM_ANALISE
        )
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Você já tem um pedido para Rex")
        self.assertContains(resposta, "em análise")
        self.assertNotContains(resposta, reverse("adocoes:solicitar", args=[self.rex.pk]))

    def test_pedido_recusado_nao_impede_novo_pedido(self):
        PedidoAdocao.objects.create(
            pet=self.rex, adotante=self.ana, mensagem="Quero.", status=StatusPedido.RECUSADO
        )
        resposta = self.client.get(self.url)
        self.assertContains(resposta, reverse("adocoes:solicitar", args=[self.rex.pk]))

    def test_animal_adotado_nao_oferece_adocao(self):
        Pet.objects.filter(pk=self.rex.pk).update(status=Pet.Status.ADOTADO)
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "já foi adotado")
        self.assertNotContains(resposta, reverse("adocoes:solicitar", args=[self.rex.pk]))

    def test_ong_ve_a_pagina_sem_botoes_de_adocao(self):
        self.client.force_login(self.responsavel)
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertNotContains(resposta, reverse("adocoes:solicitar", args=[self.rex.pk]))
        self.assertNotContains(resposta, "Favoritar")

    def test_card_do_catalogo_leva_ao_detalhe(self):
        resposta = self.client.get(reverse("pets:catalogo"))
        self.assertContains(resposta, f'href="{self.url}"')
