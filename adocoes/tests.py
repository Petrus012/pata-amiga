from django.contrib.auth.models import Group
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from contas.models import Ong, Usuario
from pets.models import Especie, Pet

from .models import (
    STATUS_EM_ABERTO,
    Acompanhamento,
    Favorito,
    PedidoAdocao,
    StatusPedido,
    TransicaoInvalida,
)


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


class MudarStatusTests(AdocoesTestCase):
    def test_aprovar_poe_o_animal_em_processo_e_registra_a_resposta(self):
        pedido = self.criar_pedido()
        pedido.mudar_status(StatusPedido.APROVADO, "Pode vir conhecer o Rex.")
        pedido.refresh_from_db()
        self.rex.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.APROVADO)
        self.assertEqual(pedido.resposta_ong, "Pode vir conhecer o Rex.")
        self.assertIsNotNone(pedido.respondido_em)
        self.assertEqual(self.rex.status, Pet.Status.EM_PROCESSO)

    def test_analisar_nao_mexe_no_animal(self):
        pedido = self.criar_pedido()
        pedido.mudar_status(StatusPedido.EM_ANALISE)
        self.rex.refresh_from_db()
        self.assertEqual(self.rex.status, Pet.Status.DISPONIVEL)
        self.assertIsNone(pedido.respondido_em)

    def test_concluir_marca_adotado_e_recusa_os_outros_pedidos_em_aberto(self):
        escolhido = self.criar_pedido(adotante=self.ana)
        concorrente = self.criar_pedido(adotante=self.bruno)
        escolhido.mudar_status(StatusPedido.APROVADO)
        escolhido.mudar_status(StatusPedido.CONCLUIDO)

        concorrente.refresh_from_db()
        self.rex.refresh_from_db()
        self.assertEqual(self.rex.status, Pet.Status.ADOTADO)
        self.assertEqual(concorrente.status, StatusPedido.RECUSADO)
        self.assertIn("adotado por outro", concorrente.resposta_ong)
        self.assertIsNotNone(concorrente.respondido_em)

    def test_concluir_nao_mexe_em_pedidos_de_outros_animais(self):
        luna = self.criar_pet("Luna")
        outro_animal = self.criar_pedido(adotante=self.bruno, pet=luna)
        escolhido = self.criar_pedido(adotante=self.ana)
        escolhido.mudar_status(StatusPedido.APROVADO)
        escolhido.mudar_status(StatusPedido.CONCLUIDO)
        outro_animal.refresh_from_db()
        self.assertEqual(outro_animal.status, StatusPedido.PENDENTE)

    def test_recusar_o_aprovado_devolve_o_animal_ao_catalogo(self):
        pedido = self.criar_pedido()
        pedido.mudar_status(StatusPedido.APROVADO)
        pedido.mudar_status(StatusPedido.RECUSADO, "A família desistiu.")
        self.rex.refresh_from_db()
        self.assertEqual(self.rex.status, Pet.Status.DISPONIVEL)

    def test_recusar_pedido_pendente_nao_altera_animal_em_processo_de_outro(self):
        aprovado = self.criar_pedido(adotante=self.ana)
        pendente = self.criar_pedido(adotante=self.bruno)
        aprovado.mudar_status(StatusPedido.APROVADO)
        pendente.mudar_status(StatusPedido.RECUSADO, "Outro candidato foi aprovado.")
        self.rex.refresh_from_db()
        self.assertEqual(self.rex.status, Pet.Status.EM_PROCESSO)

    def test_nao_aprova_dois_candidatos_para_o_mesmo_animal(self):
        primeiro = self.criar_pedido(adotante=self.ana)
        segundo = self.criar_pedido(adotante=self.bruno)
        primeiro.mudar_status(StatusPedido.APROVADO)
        with self.assertRaisesMessage(TransicaoInvalida, "já tem um pedido aprovado"):
            segundo.mudar_status(StatusPedido.APROVADO)
        segundo.refresh_from_db()
        self.assertEqual(segundo.status, StatusPedido.PENDENTE)

    def test_transicoes_proibidas(self):
        proibidas = [
            (StatusPedido.PENDENTE, StatusPedido.CONCLUIDO),
            (StatusPedido.EM_ANALISE, StatusPedido.CONCLUIDO),
            (StatusPedido.APROVADO, StatusPedido.EM_ANALISE),
            (StatusPedido.RECUSADO, StatusPedido.APROVADO),
            (StatusPedido.CONCLUIDO, StatusPedido.RECUSADO),
        ]
        for origem, destino in proibidas:
            with self.subTest(origem=origem, destino=destino):
                pedido = PedidoAdocao(
                    pet=self.rex, adotante=self.ana, mensagem="x", status=origem
                )
                with self.assertRaises(TransicaoInvalida):
                    pedido.mudar_status(destino)

    def test_transicao_invalida_nao_deixa_rastro_no_banco(self):
        pedido = self.criar_pedido()
        with self.assertRaises(TransicaoInvalida):
            pedido.mudar_status(StatusPedido.CONCLUIDO)
        pedido.refresh_from_db()
        self.rex.refresh_from_db()
        self.assertEqual(pedido.status, StatusPedido.PENDENTE)
        self.assertEqual(self.rex.status, Pet.Status.DISPONIVEL)


class AdminDaOngTests(AdocoesTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.ong.responsavel.is_staff = True
        cls.ong.responsavel.save()
        cls.grupo = Group.objects.get(name="ONG")
        cls.ong.responsavel.groups.add(cls.grupo)

        outro_responsavel = Usuario.objects.create_user(
            "ong2", password="senha", tipo=Usuario.Tipo.ONG, is_staff=True
        )
        outro_responsavel.groups.add(cls.grupo)
        cls.outra_ong = Ong.objects.create(
            responsavel=outro_responsavel, nome_fantasia="Lar dos Focinhos", cidade="Formiga"
        )
        cls.luna = Pet.objects.create(
            nome="Luna",
            especie=cls.cachorro,
            ong=cls.outra_ong,
            sexo=Pet.Sexo.FEMEA,
            porte=Pet.Porte.PEQUENO,
            idade_aproximada=2,
            descricao="Brincalhona.",
        )

    def setUp(self):
        self.client.force_login(self.ong.responsavel)
        self.meu = self.criar_pedido(adotante=self.ana, pet=self.rex)
        self.alheio = self.criar_pedido(adotante=self.bruno, pet=self.luna)

    def test_lista_mostra_so_os_pedidos_da_propria_ong(self):
        resposta = self.client.get(reverse("admin:adocoes_pedidoadocao_changelist"))
        self.assertEqual(set(resposta.context["cl"].queryset), {self.meu})

    def test_filtro_de_ong_nao_oferece_outras_ongs(self):
        resposta = self.client.get(reverse("admin:adocoes_pedidoadocao_changelist"))
        self.assertContains(resposta, "Patas Livres")
        self.assertNotContains(resposta, "Lar dos Focinhos")

    def test_nao_abre_pedido_de_outra_ong(self):
        url = reverse("admin:adocoes_pedidoadocao_change", args=[self.alheio.pk])
        resposta = self.client.get(url)
        self.assertRedirects(resposta, reverse("admin:index"))

    def test_nao_altera_pedido_de_outra_ong_por_post(self):
        url = reverse("admin:adocoes_pedidoadocao_change", args=[self.alheio.pk])
        self.client.post(url, {"status": StatusPedido.APROVADO, "resposta_ong": "x"})
        self.alheio.refresh_from_db()
        self.assertEqual(self.alheio.status, StatusPedido.PENDENTE)

    def test_ong_nao_troca_animal_nem_adotante_do_proprio_pedido(self):
        url = reverse("admin:adocoes_pedidoadocao_change", args=[self.meu.pk])
        dados = {
            "pet": self.luna.pk,
            "adotante": self.bruno.pk,
            "mensagem": "Adulterada.",
            "status": StatusPedido.EM_ANALISE,
            "resposta_ong": "Em análise.",
        }
        resposta = self.client.post(url, dados)
        self.assertEqual(resposta.status_code, 302)
        self.meu.refresh_from_db()
        self.assertEqual(self.meu.status, StatusPedido.EM_ANALISE)
        self.assertEqual(self.meu.pet, self.rex)
        self.assertEqual(self.meu.adotante, self.ana)
        self.assertNotEqual(self.meu.mensagem, "Adulterada.")

    def test_superusuario_continua_vendo_tudo(self):
        admin = Usuario.objects.create_superuser(
            "admin", "a@a.com", "senha", tipo=Usuario.Tipo.ADMIN
        )
        self.client.force_login(admin)
        resposta = self.client.get(reverse("admin:adocoes_pedidoadocao_changelist"))
        self.assertEqual(set(resposta.context["cl"].queryset), {self.meu, self.alheio})
