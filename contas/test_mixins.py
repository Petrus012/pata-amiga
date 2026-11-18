from django.contrib.auth.models import AnonymousUser
from django.core.exceptions import PermissionDenied
from django.http import HttpResponse
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.views import View

from .mixins import AdotanteRequiredMixin, OngRequiredMixin
from .models import Ong, Usuario


class ViewDeAdotante(AdotanteRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


class ViewDeOng(OngRequiredMixin, View):
    def get(self, request):
        return HttpResponse("ok")


class MixinsDePerfilTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.adotante = Usuario.objects.create_user("ana", password="senha")
        cls.responsavel = Usuario.objects.create_user(
            "ong1", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.ong = Ong.objects.create(
            responsavel=cls.responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.ong_sem_cadastro = Usuario.objects.create_user(
            "ong2", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.admin = Usuario.objects.create_superuser(
            "admin", "a@a.com", "senha", tipo=Usuario.Tipo.ADMIN
        )

    def chamar(self, view, usuario=None):
        requisicao = RequestFactory().get("/qualquer/")
        requisicao.user = usuario or AnonymousUser()
        return view.as_view()(requisicao)

    def test_perfil_certo_passa(self):
        self.assertEqual(self.chamar(ViewDeAdotante, self.adotante).status_code, 200)
        self.assertEqual(self.chamar(ViewDeOng, self.responsavel).status_code, 200)

    def test_anonimo_vai_para_o_login(self):
        for view in [ViewDeAdotante, ViewDeOng]:
            with self.subTest(view=view.__name__):
                resposta = self.chamar(view)
                self.assertEqual(resposta.status_code, 302)
                self.assertTrue(resposta.url.startswith(reverse("login")))

    def test_perfil_errado_recebe_403_e_nao_redirecionamento(self):
        casos = [
            (ViewDeAdotante, self.responsavel),
            (ViewDeAdotante, self.admin),
            (ViewDeOng, self.adotante),
            (ViewDeOng, self.admin),
        ]
        for view, usuario in casos:
            with self.subTest(view=view.__name__, usuario=usuario.username):
                with self.assertRaises(PermissionDenied):
                    self.chamar(view, usuario)

    def test_ong_sem_registro_de_ong_nao_passa(self):
        with self.assertRaises(PermissionDenied):
            self.chamar(ViewDeOng, self.ong_sem_cadastro)
