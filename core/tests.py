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
