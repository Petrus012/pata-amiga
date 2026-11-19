from django.contrib.auth.models import Group
from django.test import TestCase
from django.urls import reverse

from .models import Ong, Perfil, Usuario

DADOS_BASE = {
    "username": "maria.silva",
    "password1": "pataamiga2026",
    "password2": "pataamiga2026",
    "first_name": "Maria",
    "last_name": "Silva",
    "email": "maria@exemplo.com",
    "cidade": "Lavras",
    "telefone": "35999990000",
}


def dados_adotante(**extra):
    dados = DADOS_BASE | {"tipo": Usuario.Tipo.ADOTANTE, "tipo_moradia": "APARTAMENTO"}
    return dados | extra


def dados_ong(**extra):
    dados = DADOS_BASE | {
        "username": "abrigo.esperanca",
        "email": "contato@abrigo.org",
        "tipo": Usuario.Tipo.ONG,
        "nome_fantasia": "Abrigo Esperança",
    }
    return dados | extra


class CadastroTests(TestCase):
    def setUp(self):
        self.url = reverse("contas:cadastro")

    def test_pagina_abre_para_anonimo(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_adotante_entra_no_grupo_e_ganha_perfil(self):
        resposta = self.client.post(self.url, dados_adotante(), follow=True)

        usuario = Usuario.objects.get(username="maria.silva")
        self.assertEqual(usuario.tipo, Usuario.Tipo.ADOTANTE)
        self.assertTrue(usuario.groups.filter(name="Adotante").exists())
        self.assertEqual(usuario.perfil.tipo_moradia, "APARTAMENTO")
        self.assertFalse(Ong.objects.filter(responsavel=usuario).exists())
        self.assertRedirects(resposta, reverse("home"))

    def test_ong_entra_no_grupo_e_ganha_registro(self):
        self.client.post(self.url, dados_ong(cnpj="12.345.678/0001-90"))

        usuario = Usuario.objects.get(username="abrigo.esperanca")
        self.assertEqual(usuario.tipo, Usuario.Tipo.ONG)
        self.assertTrue(usuario.groups.filter(name="ONG").exists())
        self.assertEqual(usuario.ong.nome_fantasia, "Abrigo Esperança")
        self.assertEqual(usuario.ong.cidade, "Lavras")
        self.assertFalse(Perfil.objects.filter(usuario=usuario).exists())

    def test_ong_nasce_sem_acesso_ao_admin(self):
        self.client.post(self.url, dados_ong())
        self.assertFalse(Usuario.objects.get(username="abrigo.esperanca").is_staff)

    def test_cadastro_ja_entra_logado(self):
        self.client.post(self.url, dados_adotante())
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_ong_sem_nome_fantasia_e_recusada(self):
        resposta = self.client.post(self.url, dados_ong(nome_fantasia=""))

        self.assertEqual(resposta.status_code, 200)
        self.assertFormError(
            resposta.context["form"],
            "nome_fantasia",
            "Informe o nome da ONG ou do protetor responsável.",
        )
        self.assertFalse(Usuario.objects.filter(username="abrigo.esperanca").exists())

    def test_email_repetido_e_recusado(self):
        Usuario.objects.create_user("outro", email="maria@exemplo.com", password="x")

        resposta = self.client.post(self.url, dados_adotante())

        self.assertFormError(
            resposta.context["form"], "email", "Já existe uma conta com este e-mail."
        )

    def test_cnpj_repetido_e_recusado(self):
        self.client.post(self.url, dados_ong(cnpj="12.345.678/0001-90"))
        self.client.logout()

        resposta = self.client.post(
            self.url,
            dados_ong(username="outro.abrigo", email="b@b.com", cnpj="12.345.678/0001-90"),
        )

        self.assertFormError(
            resposta.context["form"], "cnpj", "Já existe uma ONG cadastrada com este CNPJ."
        )

    def test_duas_ongs_sem_cnpj_convivem(self):
        # O CNPJ é único no banco. Guardar string vazia faria a segunda ONG falhar.
        self.client.post(self.url, dados_ong())
        self.client.logout()
        self.client.post(self.url, dados_ong(username="outro.abrigo", email="b@b.com"))

        self.assertEqual(Ong.objects.filter(cnpj__isnull=True).count(), 2)

    def test_senha_fica_cifrada(self):
        self.client.post(self.url, dados_adotante())
        usuario = Usuario.objects.get(username="maria.silva")

        self.assertNotEqual(usuario.password, "pataamiga2026")
        self.assertTrue(usuario.check_password("pataamiga2026"))

    def test_cadastro_falho_nao_deixa_usuario_orfao(self):
        # O save é atômico: se a criação do registro de ONG falhar, o usuário não fica.
        self.client.post(self.url, dados_ong(nome_fantasia=""))
        self.assertEqual(Usuario.objects.count(), 0)

    def test_quem_ja_esta_logado_vai_para_a_home(self):
        Usuario.objects.create_user("ana", password="pataamiga2026")
        self.client.login(username="ana", password="pataamiga2026")

        self.assertRedirects(self.client.get(self.url), reverse("home"))


class LoginLogoutTests(TestCase):
    def setUp(self):
        self.usuario = Usuario.objects.create_user(
            "ana.souza", password="pataamiga2026", tipo=Usuario.Tipo.ADOTANTE
        )

    def test_login_com_dados_certos(self):
        resposta = self.client.post(
            reverse("login"),
            {"username": "ana.souza", "password": "pataamiga2026"},
            follow=True,
        )

        self.assertRedirects(resposta, reverse("home"))
        self.assertTrue(self.client.session.get("_auth_user_id"))

    def test_login_com_senha_errada_nao_conecta(self):
        resposta = self.client.post(
            reverse("login"), {"username": "ana.souza", "password": "errada"}
        )

        self.assertEqual(resposta.status_code, 200)
        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_logout_encerra_a_sessao(self):
        self.client.login(username="ana.souza", password="pataamiga2026")

        self.client.post(reverse("logout"))

        self.assertIsNone(self.client.session.get("_auth_user_id"))

    def test_login_leva_para_a_pagina_pedida_antes(self):
        destino = reverse("pets:catalogo")
        resposta = self.client.post(
            f"{reverse('login')}?next={destino}",
            {"username": "ana.souza", "password": "pataamiga2026"},
        )

        self.assertRedirects(resposta, destino)

    def test_anonimo_e_mandado_para_o_login(self):
        destino = reverse("pets:catalogo")
        self.assertRedirects(self.client.get(destino), f"{reverse('login')}?next={destino}")


class GruposTests(TestCase):
    def test_grupos_existem_vindos_da_migracao(self):
        self.assertEqual(Group.objects.filter(name__in=["ONG", "Adotante"]).count(), 2)


class SuperusuarioTests(TestCase):
    def test_superusuario_nasce_como_administrador(self):
        # Com o tipo padrão ele seria adotante e apareceria nas telas do adotante.
        admin = Usuario.objects.create_superuser("admin", "a@a.com", "pataamiga2026")

        self.assertEqual(admin.tipo, Usuario.Tipo.ADMIN)
        self.assertFalse(admin.eh_adotante)
        self.assertFalse(admin.eh_ong)

    def test_tipo_explicito_continua_valendo(self):
        admin = Usuario.objects.create_superuser(
            "outro", "b@b.com", "pataamiga2026", tipo=Usuario.Tipo.ADOTANTE
        )

        self.assertEqual(admin.tipo, Usuario.Tipo.ADOTANTE)

    def test_usuario_comum_continua_adotante_por_padrao(self):
        comum = Usuario.objects.create_user("comum", password="pataamiga2026")

        self.assertEqual(comum.tipo, Usuario.Tipo.ADOTANTE)
