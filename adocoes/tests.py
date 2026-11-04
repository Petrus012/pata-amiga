from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

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


class AdminAdocoesTestCase(AdocoesTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.admin_user = Usuario.objects.create_superuser("admin", "a@a.com", "senha")

    def setUp(self):
        self.client.force_login(self.admin_user)

    def listados(self, resposta):
        return set(resposta.context["cl"].queryset)


class PedidoAdocaoAdminListaTests(AdminAdocoesTestCase):
    url = reverse("admin:adocoes_pedidoadocao_changelist")

    def test_exige_autenticacao(self):
        self.client.logout()
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 302)
        self.assertIn(reverse("admin:login"), resposta.url)

    def test_lista_abre_com_cada_filtro(self):
        pedido = self.criar_pedido()
        inicio_de_hoje = timezone.localtime().replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        filtros = [
            {"situacao": "aberto"},
            {"status__exact": StatusPedido.PENDENTE},
            {"pet__ong__id__exact": self.ong.pk},
            {"pet__especie__id__exact": self.cachorro.pk},
            {"solicitado_em__gte": str(inicio_de_hoje)},
            {"respondido_em__isnull": "True"},
            {"q": "Rex"},
            {"q": "ana"},
            {"q": "Patas Livres"},
        ]
        for filtro in filtros:
            with self.subTest(filtro=filtro):
                resposta = self.client.get(self.url, filtro)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(self.listados(resposta), {pedido})

    def test_filtro_de_situacao_separa_abertos_de_encerrados(self):
        pedidos = {
            status: self.criar_pedido(pet=self.criar_pet(f"Pet {status}"), status=status)
            for status in StatusPedido
        }
        abertos = {pedidos[status] for status in STATUS_EM_ABERTO}
        encerrados = set(pedidos.values()) - abertos

        resposta = self.client.get(self.url, {"situacao": "aberto"})
        self.assertEqual(self.listados(resposta), abertos)
        resposta = self.client.get(self.url, {"situacao": "encerrado"})
        self.assertEqual(self.listados(resposta), encerrados)

    def test_status_aparece_com_cor(self):
        self.criar_pedido()
        resposta = self.client.get(self.url)
        self.assertContains(resposta, '<span class="badge text-bg-warning">Pendente</span>')

    def test_menu_usa_os_icones_de_adocoes(self):
        resposta = self.client.get(reverse("admin:index"))
        for icone in ["fas fa-file-signature", "fas fa-star", "fas fa-camera"]:
            with self.subTest(icone=icone):
                self.assertContains(resposta, icone)


class PedidoAdocaoAdminFormularioTests(AdminAdocoesTestCase):
    def dados(self, pedido=None, **extras):
        dados = {
            "pet": self.rex.pk,
            "adotante": self.ana.pk,
            "mensagem": "Tenho quintal.",
            "status": StatusPedido.PENDENTE,
            "resposta_ong": "",
            "acompanhamentos-TOTAL_FORMS": 0,
            "acompanhamentos-INITIAL_FORMS": 0,
            "acompanhamentos-MIN_NUM_FORMS": 0,
            "acompanhamentos-MAX_NUM_FORMS": 1000,
        }
        dados.update(extras)
        return dados

    def test_recusa_pedido_duplicado_com_mensagem_clara(self):
        self.criar_pedido()
        resposta = self.client.post(reverse("admin:adocoes_pedidoadocao_add"), self.dados())
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "já tem um pedido em aberto")
        self.assertEqual(PedidoAdocao.objects.count(), 1)

    def test_acompanhamento_no_inline_so_com_adocao_concluida(self):
        pedido = self.criar_pedido(status=StatusPedido.APROVADO)
        url = reverse("admin:adocoes_pedidoadocao_change", args=[pedido.pk])
        acompanhamento = {
            "acompanhamentos-TOTAL_FORMS": 1,
            "acompanhamentos-0-data": "04/11/2026",
            "acompanhamentos-0-relato": "Adaptou bem.",
        }
        resposta = self.client.post(
            url, self.dados(status=StatusPedido.APROVADO, **acompanhamento)
        )
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "adoções concluídas")
        self.assertFalse(Acompanhamento.objects.exists())

        resposta = self.client.post(
            url, self.dados(status=StatusPedido.CONCLUIDO, **acompanhamento)
        )
        self.assertEqual(resposta.status_code, 302)
        self.assertEqual(pedido.acompanhamentos.get().relato, "Adaptou bem.")


class AutocompleteAdminTests(AdminAdocoesTestCase):
    def buscar(self, model_name, field_name, termo=""):
        resposta = self.client.get(
            reverse("admin:autocomplete"),
            {
                "app_label": "adocoes",
                "model_name": model_name,
                "field_name": field_name,
                "term": termo,
            },
        )
        self.assertEqual(resposta.status_code, 200)
        return {int(item["id"]) for item in resposta.json()["results"]}

    def test_pedido_oferece_so_adotantes(self):
        encontrados = self.buscar("pedidoadocao", "adotante")
        self.assertTrue({self.ana.pk, self.bruno.pk} <= encontrados)
        self.assertNotIn(self.ong.responsavel_id, encontrados)

    def test_pedido_busca_animal_pelo_nome(self):
        self.criar_pet("Luna")
        self.assertEqual(self.buscar("pedidoadocao", "pet", "Rex"), {self.rex.pk})

    def test_acompanhamento_oferece_so_pedidos_concluidos(self):
        concluido = self.criar_pedido(adotante=self.ana, status=StatusPedido.CONCLUIDO)
        self.criar_pedido(adotante=self.bruno, status=StatusPedido.APROVADO)
        self.assertEqual(self.buscar("acompanhamento", "pedido"), {concluido.pk})


class FavoritoAcompanhamentoAdminTests(AdminAdocoesTestCase):
    def test_listas_abrem_com_filtros(self):
        favorito = Favorito.objects.create(usuario=self.ana, pet=self.rex)
        pedido = self.criar_pedido(status=StatusPedido.CONCLUIDO)
        acompanhamento = Acompanhamento.objects.create(pedido=pedido, relato="Feliz.")
        casos = [
            ("admin:adocoes_favorito_changelist", {"pet__especie__id__exact": self.cachorro.pk}, favorito),
            ("admin:adocoes_favorito_changelist", {"q": "ana"}, favorito),
            ("admin:adocoes_acompanhamento_changelist", {"pedido__pet__especie__id__exact": self.cachorro.pk}, acompanhamento),
            ("admin:adocoes_acompanhamento_changelist", {"q": "Rex"}, acompanhamento),
        ]
        for nome_url, filtro, esperado in casos:
            with self.subTest(url=nome_url, filtro=filtro):
                resposta = self.client.get(reverse(nome_url), filtro)
                self.assertEqual(resposta.status_code, 200)
                self.assertEqual(self.listados(resposta), {esperado})
