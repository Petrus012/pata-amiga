from django.test import TestCase
from django.urls import reverse

from contas.models import Ong, Usuario
from pets.models import Especie, Pet

from .models import PedidoAdocao, StatusPedido


class AdminMudancaDeStatusTests(TestCase):
    """O admin precisa aplicar as mesmas regras do painel da ONG.

    Antes disso o status era gravado direto: concluir um pedido por aqui deixava o
    animal disponível e os outros candidatos pendentes para sempre.
    """

    @classmethod
    def setUpTestData(cls):
        cls.admin = Usuario.objects.create_superuser("adm", "a@a.com", "pataamiga2026")
        dono = Usuario.objects.create_user(
            "abrigo", password="pataamiga2026", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=dono, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.especie = Especie.objects.create(nome="Cachorro")

    def setUp(self):
        self.client.force_login(self.admin)
        self.pet = Pet.objects.create(
            nome="Bidu",
            especie=self.especie,
            ong=self.ong,
            sexo="M",
            porte="M",
            idade_aproximada=2,
            descricao="Dócil.",
        )

    def novo_pedido(self, username, status=StatusPedido.PENDENTE):
        adotante = Usuario.objects.create_user(username, password="pataamiga2026")
        return PedidoAdocao.objects.create(
            pet=self.pet, adotante=adotante, mensagem="Tenho espaço.", status=status
        )

    def salvar(self, pedido, status, resposta=""):
        return self.client.post(
            reverse("admin:adocoes_pedidoadocao_change", args=[pedido.pk]),
            {
                "pet": self.pet.pk,
                "adotante": pedido.adotante.pk,
                "mensagem": pedido.mensagem,
                "status": status,
                "resposta_ong": resposta,
                "acompanhamentos-TOTAL_FORMS": "0",
                "acompanhamentos-INITIAL_FORMS": "0",
                "_save": "Salvar",
            },
            follow=True,
        )

    def test_aprovar_poe_o_animal_em_processo(self):
        pedido = self.novo_pedido("ana")

        self.salvar(pedido, StatusPedido.APROVADO)

        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.EM_PROCESSO)

    def test_concluir_marca_o_animal_como_adotado(self):
        pedido = self.novo_pedido("bruno", StatusPedido.APROVADO)

        self.salvar(pedido, StatusPedido.CONCLUIDO)

        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.ADOTADO)

    def test_concluir_recusa_os_outros_candidatos(self):
        escolhido = self.novo_pedido("carla", StatusPedido.APROVADO)
        outro = self.novo_pedido("diego")

        self.salvar(escolhido, StatusPedido.CONCLUIDO)

        outro.refresh_from_db()
        self.assertEqual(outro.status, StatusPedido.RECUSADO)
        self.assertTrue(outro.resposta_ong)

    def test_recusar_devolve_o_animal_ao_catalogo(self):
        pedido = self.novo_pedido("eva", StatusPedido.APROVADO)
        self.pet.status = Pet.Status.EM_PROCESSO
        self.pet.save()

        self.salvar(pedido, StatusPedido.RECUSADO)

        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.DISPONIVEL)

    def test_transicao_invalida_e_recusada_pelo_formulario(self):
        pedido = self.novo_pedido("felipe", StatusPedido.RECUSADO)

        resposta = self.salvar(pedido, StatusPedido.CONCLUIDO)

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.RECUSADO)
        self.assertContains(resposta, "não pode passar para")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.DISPONIVEL)

    def test_salvar_so_a_resposta_nao_mexe_no_animal(self):
        pedido = self.novo_pedido("gabi")

        self.salvar(pedido, StatusPedido.PENDENTE, resposta="Estamos analisando.")

        pedido.refresh_from_db()
        self.assertEqual(pedido.resposta_ong, "Estamos analisando.")
        self.pet.refresh_from_db()
        self.assertEqual(self.pet.status, Pet.Status.DISPONIVEL)

    def test_resposta_da_ong_e_gravada_junto_com_o_status(self):
        pedido = self.novo_pedido("hugo")

        self.salvar(pedido, StatusPedido.RECUSADO, resposta="Perfil não compatível.")

        pedido.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.RECUSADO)
        self.assertEqual(pedido.resposta_ong, "Perfil não compatível.")
