from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from contas.models import Ong, Usuario
from pets.models import Especie, Pet

from .models import STATUS_EM_ABERTO, Acompanhamento, Favorito, PedidoAdocao, StatusPedido


class AdocoesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        responsavel = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.ana = Usuario.objects.create_user("ana", password="senha")
        cls.bruno = Usuario.objects.create_user("bruno", password="senha")
        cls.rex = cls.criar_pet("Rex")

    @classmethod
    def criar_pet(cls, nome, **extras):
        return Pet.objects.create(
            nome=nome,
            especie=cls.cachorro,
            ong=cls.ong,
            sexo=Pet.Sexo.MACHO,
            porte=Pet.Porte.MEDIO,
            idade_aproximada=3,
            descricao="Dócil.",
            **extras,
        )

    def criar_pedido(self, adotante=None, pet=None, **extras):
        return PedidoAdocao.objects.create(
            pet=pet or self.rex,
            adotante=adotante or self.ana,
            mensagem="Tenho quintal e tempo para passear.",
            **extras,
        )


class PedidoAbertoUnicoTests(AdocoesTestCase):
    def test_banco_recusa_segundo_pedido_enquanto_o_primeiro_esta_aberto(self):
        for status in STATUS_EM_ABERTO:
            with self.subTest(status=status):
                primeiro = self.criar_pedido(status=status)
                with self.assertRaises(IntegrityError), transaction.atomic():
                    self.criar_pedido()
                primeiro.delete()

    def test_pedido_encerrado_libera_um_novo_pedido(self):
        for status in [StatusPedido.RECUSADO, StatusPedido.CONCLUIDO]:
            with self.subTest(status=status):
                self.criar_pedido(status=status)
                self.criar_pedido().delete()

    def test_outro_adotante_pode_pedir_o_mesmo_animal(self):
        self.criar_pedido(adotante=self.ana)
        self.criar_pedido(adotante=self.bruno)
        self.assertEqual(self.rex.pedidos.count(), 2)

    def test_validacao_avisa_antes_de_chegar_no_banco(self):
        self.criar_pedido()
        repetido = PedidoAdocao(pet=self.rex, adotante=self.ana, mensagem="De novo.")
        with self.assertRaisesMessage(ValidationError, "já tem um pedido em aberto"):
            repetido.full_clean()


class PedidoAdocaoTests(AdocoesTestCase):
    def test_animal_adotado_nao_recebe_novos_pedidos(self):
        adotado = self.criar_pet("Bob", status=Pet.Status.ADOTADO)
        pedido = PedidoAdocao(pet=adotado, adotante=self.ana, mensagem="Quero adotar.")
        with self.assertRaisesMessage(ValidationError, "já foi adotado"):
            pedido.full_clean()

    def test_pedido_antigo_continua_valido_depois_da_adocao(self):
        pedido = self.criar_pedido(status=StatusPedido.CONCLUIDO)
        Pet.objects.filter(pk=self.rex.pk).update(status=Pet.Status.ADOTADO)
        pedido.refresh_from_db()
        pedido.full_clean()

    def test_data_da_resposta_e_registrada_quando_a_ong_decide(self):
        pedido = self.criar_pedido()
        self.assertIsNone(pedido.respondido_em)

        pedido.status = StatusPedido.EM_ANALISE
        pedido.save()
        self.assertIsNone(pedido.respondido_em)

        pedido.status = StatusPedido.APROVADO
        pedido.save()
        respondido_em = pedido.respondido_em
        self.assertIsNotNone(respondido_em)

        pedido.status = StatusPedido.CONCLUIDO
        pedido.save()
        self.assertEqual(pedido.respondido_em, respondido_em)

    def test_em_aberto(self):
        for status in StatusPedido:
            with self.subTest(status=status):
                pedido = PedidoAdocao(status=status)
                self.assertEqual(pedido.em_aberto, status in STATUS_EM_ABERTO)

    def test_status_acessivel_pelo_modelo(self):
        self.assertIs(PedidoAdocao.Status, StatusPedido)


class FavoritoTests(AdocoesTestCase):
    def test_mesmo_animal_nao_e_favoritado_duas_vezes(self):
        Favorito.objects.create(usuario=self.ana, pet=self.rex)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Favorito.objects.create(usuario=self.ana, pet=self.rex)

    def test_validacao_avisa_favorito_repetido(self):
        Favorito.objects.create(usuario=self.ana, pet=self.rex)
        with self.assertRaisesMessage(ValidationError, "já está nos favoritos"):
            Favorito(usuario=self.ana, pet=self.rex).full_clean()

    def test_relacao_muitos_para_muitos_pelos_dois_lados(self):
        luna = self.criar_pet("Luna")
        Favorito.objects.create(usuario=self.ana, pet=self.rex)
        Favorito.objects.create(usuario=self.ana, pet=luna)
        Favorito.objects.create(usuario=self.bruno, pet=self.rex)
        self.assertEqual(self.ana.favoritos.count(), 2)
        self.assertEqual(self.rex.favoritos.count(), 2)


class AcompanhamentoTests(AdocoesTestCase):
    def test_so_aceita_adocao_concluida(self):
        for status in StatusPedido:
            with self.subTest(status=status):
                pedido = PedidoAdocao(pet=self.rex, adotante=self.ana, status=status)
                acompanhamento = Acompanhamento(pedido=pedido, relato="Está ótimo.")
                if status == StatusPedido.CONCLUIDO:
                    acompanhamento.clean()
                else:
                    with self.assertRaisesMessage(ValidationError, "adoções concluídas"):
                        acompanhamento.clean()

    def test_sem_pedido_o_erro_fica_so_no_campo_obrigatorio(self):
        with self.assertRaises(ValidationError) as contexto:
            Acompanhamento(relato="Está ótimo.").full_clean()
        self.assertEqual(list(contexto.exception.message_dict), ["pedido"])
