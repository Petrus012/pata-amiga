# Testes da área "Meus animais": a ONG cadastra, edita e remove só os próprios animais.
import shutil
import tempfile

from django.test import TestCase, override_settings
from django.urls import reverse

from adocoes.models import PedidoAdocao
from contas.models import Ong, Usuario

from .models import Especie, Pet, Raca, Vacina
from .test_formularios import imagem

PASTA_MEDIA = tempfile.mkdtemp()


@override_settings(MEDIA_ROOT=PASTA_MEDIA)
class AreaOngTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.addClassCleanup(shutil.rmtree, PASTA_MEDIA, ignore_errors=True)

    @classmethod
    def setUpTestData(cls):
        cls.usuario_ong = Usuario.objects.create_user("ong1", password="senha", tipo=Usuario.Tipo.ONG)
        cls.ong = Ong.objects.create(
            responsavel=cls.usuario_ong, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        outro = Usuario.objects.create_user("ong2", password="senha", tipo=Usuario.Tipo.ONG)
        cls.outra_ong = Ong.objects.create(
            responsavel=outro, nome_fantasia="Lar dos Focinhos", cidade="Formiga"
        )
        cls.ong_sem_cadastro = Usuario.objects.create_user(
            "ong3", password="senha", tipo=Usuario.Tipo.ONG
        )
        cls.adotante = Usuario.objects.create_user("ana", password="senha")
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.gato = Especie.objects.create(nome="Gato")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)
        cls.siames = Raca.objects.create(nome="Siamês", especie=cls.gato)

    def setUp(self):
        self.client.force_login(self.usuario_ong)
        self.rex = self.criar_pet("Rex", self.ong)
        self.bob = self.criar_pet("Bob", self.outra_ong)

    def criar_pet(self, nome, ong, **extras):
        dados = {
            "especie": self.cachorro,
            "sexo": Pet.Sexo.MACHO,
            "porte": Pet.Porte.MEDIO,
            "idade_aproximada": 3,
            "descricao": "Dócil.",
        }
        dados.update(extras)
        return Pet.objects.create(nome=nome, ong=ong, **dados)

    def dados(self, total_vacinas=1, iniciais=0, **extras):
        dados = {
            "nome": "Luna",
            "especie": self.gato.pk,
            "raca": self.siames.pk,
            "sexo": Pet.Sexo.FEMEA,
            "porte": Pet.Porte.PEQUENO,
            "idade_aproximada": 2,
            "descricao": "Calma.",
            "vacinas-TOTAL_FORMS": total_vacinas,
            "vacinas-INITIAL_FORMS": iniciais,
            "vacinas-MIN_NUM_FORMS": 0,
            "vacinas-MAX_NUM_FORMS": 1000,
        }
        dados.update(extras)
        return dados

    def mensagens(self, resposta):
        return [str(m) for m in resposta.context["messages"]]


class AcessoTests(AreaOngTestCase):
    def urls(self):
        return [
            reverse("pets:meus_animais"),
            reverse("pets:cadastrar"),
            reverse("pets:editar", args=[self.rex.pk]),
            reverse("pets:remover", args=[self.rex.pk]),
        ]

    def test_anonimo_vai_para_o_login(self):
        self.client.logout()
        for url in self.urls():
            with self.subTest(url=url):
                resposta = self.client.get(url)
                self.assertRedirects(resposta, f"{reverse('login')}?next={url}")

    def test_adotante_e_ong_sem_cadastro_recebem_403(self):
        for usuario in [self.adotante, self.ong_sem_cadastro]:
            self.client.force_login(usuario)
            for url in self.urls():
                with self.subTest(usuario=usuario.username, url=url):
                    self.assertEqual(self.client.get(url).status_code, 403)

    def test_animal_de_outra_ong_da_404(self):
        for nome in ["pets:editar", "pets:remover"]:
            url = reverse(nome, args=[self.bob.pk])
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 404)
                self.assertEqual(self.client.post(url, self.dados(nome="Invadido")).status_code, 404)
        self.bob.refresh_from_db()
        self.assertEqual(self.bob.nome, "Bob")
        self.assertTrue(Pet.objects.filter(pk=self.bob.pk).exists())

    def test_menu_mostra_meus_animais_so_para_a_ong(self):
        link = f'href="{reverse("pets:meus_animais")}"'
        self.assertContains(self.client.get(reverse("home")), link)
        self.client.force_login(self.adotante)
        self.assertNotContains(self.client.get(reverse("home")), link)


class ListaTests(AreaOngTestCase):
    def test_lista_so_os_animais_da_propria_ong(self):
        resposta = self.client.get(reverse("pets:meus_animais"))
        self.assertEqual([p.nome for p in resposta.context["pets"]], ["Rex"])
        self.assertNotContains(resposta, "Bob")

    def test_mostra_pedidos_em_aberto_vacinas_e_resumo(self):
        PedidoAdocao.objects.create(pet=self.rex, adotante=self.adotante, mensagem="Quero.")
        Vacina.objects.create(pet=self.rex, nome="V8", data_aplicacao="2026-08-01")
        Vacina.objects.create(pet=self.rex, nome="V10", data_aplicacao="2026-09-01")
        self.criar_pet("Tom", self.ong, status=Pet.Status.ADOTADO)
        resposta = self.client.get(reverse("pets:meus_animais"))
        rex = next(p for p in resposta.context["pets"] if p.nome == "Rex")
        self.assertEqual((rex.pedidos_abertos, rex.total_vacinas), (1, 2))
        self.assertEqual(
            resposta.context["resumo"],
            {"total": 2, "disponiveis": 1, "em_processo": 0, "adotados": 1},
        )

    def test_consultas_nao_crescem_com_o_numero_de_animais(self):
        url = reverse("pets:meus_animais")
        with self.assertNumQueries(6) as primeira:
            self.client.get(url)
        for indice in range(5):
            self.criar_pet(f"Pet {indice}", self.ong)
        with self.assertNumQueries(len(primeira.captured_queries)):
            self.client.get(url)

    def test_lista_vazia_convida_a_cadastrar(self):
        self.rex.delete()
        resposta = self.client.get(reverse("pets:meus_animais"))
        self.assertContains(resposta, "Nenhum animal cadastrado ainda.")


class CadastroTests(AreaOngTestCase):
    url = reverse("pets:cadastrar")

    def test_formulario_abre_com_vacinas_e_sem_campo_ong(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "vacinas-TOTAL_FORMS")
        self.assertNotContains(resposta, 'name="ong"')
        self.assertNotContains(resposta, 'name="status"')

    def test_cadastro_com_foto_e_vacina(self):
        dados = self.dados(
            foto=imagem(),
            **{"vacinas-0-nome": "V4", "vacinas-0-data_aplicacao": "2026-10-01"},
        )
        resposta = self.client.post(self.url, dados, follow=True)
        self.assertRedirects(resposta, reverse("pets:meus_animais"))
        luna = Pet.objects.get(nome="Luna")
        self.assertEqual((luna.ong, luna.status), (self.ong, Pet.Status.DISPONIVEL))
        self.assertTrue(luna.foto.name.startswith("pets/"))
        self.assertEqual([v.nome for v in luna.vacinas.all()], ["V4"])
        self.assertIn("Luna foi cadastrado e já aparece no catálogo.", self.mensagens(resposta))

    def test_ong_e_status_enviados_a_forca_sao_ignorados(self):
        self.client.post(
            self.url, self.dados(ong=self.outra_ong.pk, status=Pet.Status.ADOTADO)
        )
        luna = Pet.objects.get(nome="Luna")
        self.assertEqual((luna.ong, luna.status), (self.ong, Pet.Status.DISPONIVEL))

    def test_erro_no_animal_nao_salva_nada_e_mantem_as_vacinas_digitadas(self):
        dados = self.dados(
            raca=self.poodle.pk,
            **{"vacinas-0-nome": "V4", "vacinas-0-data_aplicacao": "2026-10-01"},
        )
        resposta = self.client.post(self.url, dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "não pertence à espécie")
        self.assertContains(resposta, 'value="V4"')
        self.assertFalse(Pet.objects.filter(nome="Luna").exists())

    def test_erro_na_vacina_nao_salva_o_animal(self):
        dados = self.dados(**{"vacinas-0-nome": "V4"})
        resposta = self.client.post(self.url, dados)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Este campo é obrigatório.")
        self.assertFalse(Pet.objects.filter(nome="Luna").exists())


class EdicaoTests(AreaOngTestCase):
    def test_edita_dados_e_vacinas_sem_mudar_o_status(self):
        Pet.objects.filter(pk=self.rex.pk).update(status=Pet.Status.EM_PROCESSO)
        v8 = Vacina.objects.create(pet=self.rex, nome="V8", data_aplicacao="2026-08-01")
        url = reverse("pets:editar", args=[self.rex.pk])
        self.assertContains(self.client.get(url), 'value="Rex"')
        dados = self.dados(
            total_vacinas=2,
            iniciais=1,
            nome="Rex Junior",
            especie=self.cachorro.pk,
            raca=self.poodle.pk,
            status=Pet.Status.DISPONIVEL,
            **{
                "vacinas-0-id": v8.pk,
                "vacinas-0-nome": "V8",
                "vacinas-0-data_aplicacao": "2026-08-01",
                "vacinas-0-DELETE": "on",
                "vacinas-1-nome": "Antirrábica",
                "vacinas-1-data_aplicacao": "2026-10-10",
            },
        )
        resposta = self.client.post(url, dados, follow=True)
        self.assertRedirects(resposta, reverse("pets:meus_animais"))
        self.rex.refresh_from_db()
        self.assertEqual(self.rex.nome, "Rex Junior")
        self.assertEqual(self.rex.status, Pet.Status.EM_PROCESSO)
        self.assertEqual([v.nome for v in self.rex.vacinas.all()], ["Antirrábica"])
        self.assertIn("Dados de Rex Junior atualizados.", self.mensagens(resposta))


class RemocaoTests(AreaOngTestCase):
    def test_remove_animal_sem_pedidos(self):
        url = reverse("pets:remover", args=[self.rex.pk])
        self.assertContains(self.client.get(url), "Remover Rex?")
        resposta = self.client.post(url, follow=True)
        self.assertRedirects(resposta, reverse("pets:meus_animais"))
        self.assertFalse(Pet.objects.filter(pk=self.rex.pk).exists())
        self.assertIn("Rex foi removido.", self.mensagens(resposta))

    def test_animal_com_pedido_nao_e_removido(self):
        pedido = PedidoAdocao.objects.create(pet=self.rex, adotante=self.adotante, mensagem="Quero.")
        url = reverse("pets:remover", args=[self.rex.pk])
        pagina = self.client.get(url)
        self.assertContains(pagina, "tem pedidos de adoção e não pode ser removido")
        self.assertNotContains(pagina, 'class="btn btn-danger">Remover')

        resposta = self.client.post(url, follow=True)
        self.assertRedirects(resposta, reverse("pets:meus_animais"))
        self.assertTrue(Pet.objects.filter(pk=self.rex.pk).exists())
        self.assertTrue(PedidoAdocao.objects.filter(pk=pedido.pk).exists())
        self.assertTrue(any("não pode ser removido" in m for m in self.mensagens(resposta)))
