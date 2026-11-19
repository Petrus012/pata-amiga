from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.base import Message
from django.contrib.staticfiles import finders
from django.template.loader import render_to_string
from django.test import TestCase
from django.urls import reverse


class BaseTemplateTests(TestCase):
    def test_pagina_inicial_herda_o_base(self):
        resposta = self.client.get(reverse("home"))
        self.assertEqual(resposta.status_code, 200)
        for template in [
            "base.html",
            "includes/navbar.html",
            "includes/mensagens.html",
            "includes/rodape.html",
        ]:
            with self.subTest(template=template):
                self.assertTemplateUsed(resposta, template)

    def test_bootstrap_e_tema_sao_carregados_no_head(self):
        conteudo = self.client.get(reverse("home")).content.decode()
        head = conteudo.split("</head>")[0]
        self.assertIn("bootstrap@5.3.8/dist/css/bootstrap.min.css", head)
        self.assertIn("bootstrap-icons", head)
        # O tema precisa ser aplicado antes de o corpo da página ser desenhado.
        self.assertIn("js/tema.js", head)
        self.assertIn('id="alternar-tema"', conteudo)

    def test_arquivos_proprios_estao_nos_estaticos(self):
        self.assertIsNotNone(finders.find("js/tema.js"))

    def test_link_da_administracao_so_aparece_para_a_equipe(self):
        Usuario = get_user_model()
        link_admin = f'href="{reverse("admin:index")}"'
        casos = [
            ("anônimo", None, False),
            ("adotante", Usuario.objects.create_user("ana", password="senha"), False),
            (
                "equipe",
                Usuario.objects.create_user("bia", password="senha", is_staff=True),
                True,
            ),
        ]
        for nome, usuario, deve_aparecer in casos:
            with self.subTest(usuario=nome):
                self.client.logout()
                if usuario:
                    self.client.force_login(usuario)
                conteudo = self.client.get(reverse("home")).content.decode()
                self.assertEqual(link_admin in conteudo, deve_aparecer)

    def test_mensagem_de_erro_usa_a_cor_de_perigo_do_bootstrap(self):
        html = render_to_string(
            "includes/mensagens.html",
            {
                "messages": [
                    Message(messages.ERROR, "Não foi possível salvar."),
                    Message(messages.SUCCESS, "Pedido enviado."),
                ]
            },
        )
        self.assertIn("alert-danger", html)
        self.assertIn("alert-success", html)
        self.assertNotIn("alert-error", html)


class NavbarPorPerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        Usuario = get_user_model()
        cls.adotante = Usuario.objects.create_user("ana", password="senha")
        cls.ong = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )

    def itens(self, usuario=None):
        self.client.logout()
        if usuario:
            self.client.force_login(usuario)
        conteudo = self.client.get(reverse("home")).content.decode()
        return {
            "entrar": reverse("login") in conteudo,
            "sair": reverse("logout") in conteudo,
            "pedidos": reverse("adocoes:meus_pedidos") in conteudo,
            "favoritos": reverse("adocoes:favoritos") in conteudo,
            "recebidos": reverse("adocoes:recebidos") in conteudo,
        }

    def test_anonimo_ve_entrar_e_nenhum_menu_de_perfil(self):
        self.assertEqual(
            self.itens(),
            {"entrar": True, "sair": False, "pedidos": False, "favoritos": False, "recebidos": False},
        )

    def test_adotante_ve_pedidos_e_favoritos(self):
        self.assertEqual(
            self.itens(self.adotante),
            {"entrar": False, "sair": True, "pedidos": True, "favoritos": True, "recebidos": False},
        )

    def test_ong_ve_pedidos_recebidos(self):
        self.assertEqual(
            self.itens(self.ong),
            {"entrar": False, "sair": True, "pedidos": False, "favoritos": False, "recebidos": True},
        )

    def test_logout_e_por_post_e_encerra_a_sessao(self):
        self.client.force_login(self.adotante)
        self.assertEqual(self.client.get(reverse("logout")).status_code, 405)
        resposta = self.client.post(reverse("logout"))
        self.assertRedirects(resposta, reverse("home"))
        self.assertNotIn("_auth_user_id", self.client.session)


class LoginTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.usuario = get_user_model().objects.create_user("ana", password="senha-forte-123")

    def test_login_com_senha_certa_volta_para_a_pagina_pedida(self):
        destino = reverse("pets:catalogo")
        resposta = self.client.post(
            f"{reverse('login')}?next={destino}",
            {"username": "ana", "password": "senha-forte-123", "next": destino},
        )
        self.assertRedirects(resposta, destino)

    def test_senha_errada_mostra_mensagem(self):
        resposta = self.client.post(reverse("login"), {"username": "ana", "password": "errada"})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Usuário ou senha incorretos")
