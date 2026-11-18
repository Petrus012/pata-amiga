# Testes das telas do adotante e da ONG. Os de modelos e admin ficam no tests.py.
import io
import tempfile
from unittest import mock

from django.core.files.uploadedfile import SimpleUploadedFile
from django.db import IntegrityError
from django.test import override_settings
from django.urls import reverse
from PIL import Image

from contas.models import Ong, Perfil, Usuario
from pets.models import Pet

from .forms import PedidoAdocaoForm
from .models import Acompanhamento, Favorito, PedidoAdocao, StatusPedido
from .tests import AdocoesTestCase


class FluxoTestCase(AdocoesTestCase):
    @classmethod
    def setUpTestData(cls):
        super().setUpTestData()
        cls.usuario_ong = cls.ong.responsavel
        outro_responsavel = Usuario.objects.create_user(
            "ong2", password="senha", tipo=Usuario.Tipo.ONG
        )
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

    def entrar(self, usuario):
        self.client.force_login(usuario)

    def mensagens(self, resposta):
        return [str(m) for m in resposta.context["messages"]]


class AcessoPorPerfilTests(FluxoTestCase):
    def test_cada_area_exige_o_perfil_certo(self):
        pedido = self.criar_pedido()
        areas_do_adotante = [
            reverse("adocoes:solicitar", args=[self.rex.pk]),
            reverse("adocoes:meus_pedidos"),
            reverse("adocoes:favoritos"),
            reverse("adocoes:acompanhamento", args=[pedido.pk]),
        ]
        areas_da_ong = [
            reverse("adocoes:recebidos"),
            reverse("adocoes:responder", args=[pedido.pk]),
        ]
        casos = [
            (None, areas_do_adotante + areas_da_ong, 302),
            (self.usuario_ong, areas_do_adotante, 403),
            (self.ana, areas_da_ong, 403),
        ]
        for usuario, urls, esperado in casos:
            for url in urls:
                with self.subTest(usuario=usuario and usuario.username, url=url):
                    self.client.logout()
                    if usuario:
                        self.entrar(usuario)
                    self.assertEqual(self.client.get(url).status_code, esperado)

    def test_anonimo_volta_para_a_tela_pedida_depois_do_login(self):
        url = reverse("adocoes:meus_pedidos")
        resposta = self.client.get(url)
        self.assertRedirects(resposta, f"{reverse('login')}?next={url}")

    def test_pagina_403_explica_o_motivo(self):
        self.entrar(self.usuario_ong)
        resposta = self.client.get(reverse("adocoes:meus_pedidos"))
        self.assertContains(resposta, "não é para o seu perfil", status_code=403)

    def test_acoes_de_escrita_nao_aceitam_get(self):
        pedido = self.criar_pedido()
        self.entrar(self.ana)
        urls = [
            reverse("adocoes:cancelar", args=[pedido.pk]),
            reverse("adocoes:alternar_favorito", args=[self.rex.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 405)


class SolicitarAdocaoTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.ana)
        self.url = reverse("adocoes:solicitar", args=[self.rex.pk])

    def test_formulario_mostra_o_animal(self):
        resposta = self.client.get(self.url)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Solicitar adoção de Rex")

    def test_cria_pedido_pendente_do_proprio_usuario(self):
        resposta = self.client.post(
            self.url,
            {"mensagem": "Tenho quintal.", "adotante": self.bruno.pk, "status": "APROVADO"},
            follow=True,
        )
        self.assertRedirects(resposta, reverse("adocoes:meus_pedidos"))
        pedido = PedidoAdocao.objects.get()
        # Campos que não fazem parte do formulário não podem ser forjados pelo POST.
        self.assertEqual(pedido.adotante, self.ana)
        self.assertEqual(pedido.pet, self.rex)
        self.assertEqual(pedido.status, StatusPedido.PENDENTE)
        self.assertContains(resposta, "Pedido de adoção de Rex enviado")

    def test_mensagem_vazia_volta_com_erro(self):
        resposta = self.client.post(self.url, {"mensagem": "   "})
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Este campo é obrigatório")
        self.assertFalse(PedidoAdocao.objects.exists())

    def test_segundo_pedido_em_aberto_nao_e_criado(self):
        self.criar_pedido()
        resposta = self.client.post(self.url, {"mensagem": "De novo."}, follow=True)
        self.assertEqual(PedidoAdocao.objects.count(), 1)
        self.assertContains(resposta, "Você já tem um pedido em aberto para Rex")

    def test_abrir_o_formulario_com_pedido_em_aberto_redireciona(self):
        self.criar_pedido()
        resposta = self.client.get(self.url)
        self.assertRedirects(resposta, reverse("adocoes:meus_pedidos"))

    def test_pode_pedir_de_novo_depois_de_uma_recusa(self):
        self.criar_pedido(status=StatusPedido.RECUSADO)
        self.client.post(self.url, {"mensagem": "Posso tentar de novo?"})
        self.assertEqual(PedidoAdocao.objects.filter(status=StatusPedido.PENDENTE).count(), 1)

    def test_animal_adotado_nao_recebe_pedido(self):
        adotado = self.criar_pet("Bob", status=Pet.Status.ADOTADO)
        url = reverse("adocoes:solicitar", args=[adotado.pk])
        for resposta in [self.client.get(url), self.client.post(url, {"mensagem": "Quero."})]:
            self.assertRedirects(resposta, adotado.get_absolute_url())
        self.assertFalse(PedidoAdocao.objects.exists())

    def test_animal_inexistente_da_404_so_para_quem_tem_permissao(self):
        url = reverse("adocoes:solicitar", args=[9999])
        self.assertEqual(self.client.get(url).status_code, 404)
        self.client.logout()
        self.assertEqual(self.client.get(url).status_code, 302)

    def test_formulario_barra_pedido_duplicado_antes_do_banco(self):
        self.criar_pedido()
        form = PedidoAdocaoForm(
            {"mensagem": "De novo."}, pet=self.rex, adotante=self.ana
        )
        self.assertFalse(form.is_valid())
        self.assertIn("já tem um pedido em aberto", str(form.non_field_errors()))

    def test_envios_simultaneos_caem_na_restricao_do_banco(self):
        # Simula a corrida: a validação passou, mas o banco recusa o segundo registro.
        with mock.patch.object(PedidoAdocao, "save", side_effect=IntegrityError):
            resposta = self.client.post(self.url, {"mensagem": "Quero."}, follow=True)
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Você já tem um pedido em aberto")


class MeusPedidosTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.ana)
        self.url = reverse("adocoes:meus_pedidos")

    def test_lista_so_os_pedidos_do_proprio_usuario(self):
        self.criar_pedido(adotante=self.ana, pet=self.rex)
        self.criar_pedido(adotante=self.bruno, pet=self.luna)
        resposta = self.client.get(self.url)
        self.assertEqual([p.pet for p in resposta.context["pedidos"]], [self.rex])
        self.assertNotContains(resposta, "Luna")

    def test_mostra_resposta_da_ong_e_acompanhamentos(self):
        pedido = self.criar_pedido(status=StatusPedido.CONCLUIDO, resposta_ong="Parabéns!")
        Acompanhamento.objects.create(pedido=pedido, relato="Dorme no sofá.")
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Parabéns!")
        self.assertContains(resposta, "Dorme no sofá.")
        self.assertContains(resposta, reverse("adocoes:acompanhamento", args=[pedido.pk]))

    def test_lista_vazia_convida_a_conhecer_os_animais(self):
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "ainda não fez nenhum pedido")

    def test_botao_de_cancelar_so_para_pedido_pendente(self):
        pedido = self.criar_pedido(status=StatusPedido.EM_ANALISE)
        resposta = self.client.get(self.url)
        self.assertNotContains(resposta, reverse("adocoes:cancelar", args=[pedido.pk]))


class CancelarPedidoTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.ana)

    def cancelar(self, pedido):
        return self.client.post(reverse("adocoes:cancelar", args=[pedido.pk]), follow=True)

    def test_cancela_pedido_pendente(self):
        pedido = self.criar_pedido()
        resposta = self.cancelar(pedido)
        self.assertFalse(PedidoAdocao.objects.filter(pk=pedido.pk).exists())
        self.assertContains(resposta, "Pedido de adoção de Rex cancelado")

    def test_nao_cancela_pedido_ja_em_analise(self):
        pedido = self.criar_pedido(status=StatusPedido.EM_ANALISE)
        resposta = self.cancelar(pedido)
        self.assertTrue(PedidoAdocao.objects.filter(pk=pedido.pk).exists())
        self.assertContains(resposta, "Só é possível cancelar")

    def test_nao_cancela_pedido_de_outro_usuario(self):
        pedido = self.criar_pedido(adotante=self.bruno)
        resposta = self.client.post(reverse("adocoes:cancelar", args=[pedido.pk]))
        self.assertEqual(resposta.status_code, 404)
        self.assertTrue(PedidoAdocao.objects.filter(pk=pedido.pk).exists())

    def test_cancelar_libera_novo_pedido(self):
        pedido = self.criar_pedido()
        self.cancelar(pedido)
        self.criar_pedido()


class AcompanhamentoViewTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.ana)

    def url(self, pedido):
        return reverse("adocoes:acompanhamento", args=[pedido.pk])

    def dados(self, **extras):
        dados = {"data": "2026-11-10", "relato": "Já brinca com as crianças."}
        dados.update(extras)
        return dados

    def test_so_abre_para_adocao_concluida(self):
        for status in StatusPedido:
            with self.subTest(status=status):
                PedidoAdocao.objects.all().delete()
                pedido = self.criar_pedido(status=status)
                resposta = self.client.get(self.url(pedido))
                if status == StatusPedido.CONCLUIDO:
                    self.assertEqual(resposta.status_code, 200)
                else:
                    self.assertRedirects(resposta, reverse("adocoes:meus_pedidos"))

    def test_registra_o_relato(self):
        pedido = self.criar_pedido(status=StatusPedido.CONCLUIDO)
        resposta = self.client.post(self.url(pedido), self.dados(), follow=True)
        self.assertRedirects(resposta, reverse("adocoes:meus_pedidos"))
        self.assertEqual(pedido.acompanhamentos.get().relato, "Já brinca com as crianças.")

    def test_post_em_pedido_nao_concluido_nao_grava(self):
        pedido = self.criar_pedido(status=StatusPedido.APROVADO)
        self.client.post(self.url(pedido), self.dados())
        self.assertFalse(Acompanhamento.objects.exists())

    def test_relato_vazio_volta_com_erro(self):
        pedido = self.criar_pedido(status=StatusPedido.CONCLUIDO)
        resposta = self.client.post(self.url(pedido), self.dados(relato=""))
        self.assertEqual(resposta.status_code, 200)
        self.assertContains(resposta, "Este campo é obrigatório")

    def test_pedido_de_outro_usuario_da_404(self):
        pedido = self.criar_pedido(adotante=self.bruno, status=StatusPedido.CONCLUIDO)
        self.assertEqual(self.client.get(self.url(pedido)).status_code, 404)
        self.assertEqual(self.client.post(self.url(pedido), self.dados()).status_code, 404)

    def test_aceita_foto(self):
        pedido = self.criar_pedido(status=StatusPedido.CONCLUIDO)
        imagem = io.BytesIO()
        Image.new("RGB", (2, 2)).save(imagem, format="PNG")
        foto = SimpleUploadedFile("rex.png", imagem.getvalue(), "image/png")
        with tempfile.TemporaryDirectory() as pasta, override_settings(MEDIA_ROOT=pasta):
            self.client.post(self.url(pedido), self.dados(foto=foto))
            acompanhamento = pedido.acompanhamentos.get()
            self.assertTrue(acompanhamento.foto.name.endswith(".png"))
            # No Windows a pasta temporária só é apagada com o arquivo fechado.
            acompanhamento.foto.close()


class FavoritosTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.ana)

    def alternar(self, pet, **dados):
        return self.client.post(reverse("adocoes:alternar_favorito", args=[pet.pk]), dados)

    def test_favoritar_e_desfavoritar(self):
        self.alternar(self.rex)
        self.assertTrue(Favorito.objects.filter(usuario=self.ana, pet=self.rex).exists())
        self.alternar(self.rex)
        self.assertFalse(Favorito.objects.exists())

    def test_volta_para_a_pagina_de_origem(self):
        resposta = self.alternar(self.rex, next=reverse("adocoes:favoritos"))
        self.assertRedirects(resposta, reverse("adocoes:favoritos"))

    def test_ignora_destino_fora_do_site(self):
        for destino in ["https://exemplo.com/golpe", "//exemplo.com/golpe"]:
            with self.subTest(destino=destino):
                resposta = self.alternar(self.rex, next=destino)
                self.assertRedirects(resposta, self.rex.get_absolute_url())

    def test_animal_inexistente_da_404(self):
        resposta = self.client.post(reverse("adocoes:alternar_favorito", args=[9999]))
        self.assertEqual(resposta.status_code, 404)

    def test_lista_so_os_favoritos_do_proprio_usuario(self):
        Favorito.objects.create(usuario=self.ana, pet=self.rex)
        Favorito.objects.create(usuario=self.bruno, pet=self.luna)
        resposta = self.client.get(reverse("adocoes:favoritos"))
        self.assertEqual([f.pet for f in resposta.context["favoritos"]], [self.rex])
        self.assertContains(resposta, "Rex")
        self.assertNotContains(resposta, "Luna")

    def test_lista_vazia_convida_a_conhecer_os_animais(self):
        resposta = self.client.get(reverse("adocoes:favoritos"))
        self.assertContains(resposta, "ainda não favoritou")

    def test_cartao_do_favorito_leva_ao_detalhe(self):
        Favorito.objects.create(usuario=self.ana, pet=self.rex)
        resposta = self.client.get(reverse("adocoes:favoritos"))
        self.assertContains(resposta, f'href="{self.rex.get_absolute_url()}"')


class PedidosRecebidosTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.usuario_ong)
        self.url = reverse("adocoes:recebidos")
        self.meu = self.criar_pedido(adotante=self.ana, pet=self.rex)
        self.analise = self.criar_pedido(
            adotante=self.bruno, pet=self.rex, status=StatusPedido.EM_ANALISE
        )
        self.alheio = self.criar_pedido(adotante=self.ana, pet=self.luna)

    def test_lista_so_pedidos_dos_animais_da_propria_ong(self):
        resposta = self.client.get(self.url)
        self.assertEqual(set(resposta.context["pedidos"]), {self.meu, self.analise})
        self.assertNotContains(resposta, "Luna")

    def test_filtra_por_status(self):
        resposta = self.client.get(self.url, {"status": "EM_ANALISE"})
        self.assertEqual(list(resposta.context["pedidos"]), [self.analise])

    def test_status_invalido_e_ignorado(self):
        resposta = self.client.get(self.url, {"status": "QUALQUER"})
        self.assertEqual(len(resposta.context["pedidos"]), 2)

    def test_abas_contam_so_os_pedidos_da_ong(self):
        resposta = self.client.get(self.url)
        contagem = {valor: total for valor, _, total in resposta.context["filtros"]}
        self.assertEqual(contagem[""], 2)
        self.assertEqual(contagem["PENDENTE"], 1)
        self.assertEqual(contagem["EM_ANALISE"], 1)
        self.assertEqual(contagem["APROVADO"], 0)

    def test_paginacao_mantem_o_filtro_de_status(self):
        for indice in range(11):
            self.criar_pedido(adotante=Usuario.objects.create_user(f"u{indice}", password="x"))
        resposta = self.client.get(self.url, {"status": "PENDENTE"})
        self.assertContains(resposta, "status=PENDENTE&amp;page=2")


class ResponderPedidoTests(FluxoTestCase):
    def setUp(self):
        self.entrar(self.usuario_ong)
        self.pedido = self.criar_pedido(adotante=self.ana, pet=self.rex)
        self.url = reverse("adocoes:responder", args=[self.pedido.pk])

    def responder(self, acao, resposta="", pedido=None):
        url = reverse("adocoes:responder", args=[(pedido or self.pedido).pk])
        return self.client.post(url, {"acao": acao, "resposta": resposta}, follow=True)

    def test_mostra_dados_e_perfil_do_adotante(self):
        Perfil.objects.create(
            usuario=self.ana,
            tipo_moradia=Perfil.Moradia.CASA,
            tem_outros_animais=True,
            bio="Amo animais.",
        )
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "Tenho quintal e tempo para passear.")
        self.assertContains(resposta, "Casa com quintal")
        self.assertContains(resposta, "Amo animais.")

    def test_funciona_para_adotante_sem_perfil(self):
        self.assertEqual(self.client.get(self.url).status_code, 200)

    def test_pedido_de_outra_ong_da_404(self):
        alheio = self.criar_pedido(adotante=self.bruno, pet=self.luna)
        url = reverse("adocoes:responder", args=[alheio.pk])
        self.assertEqual(self.client.get(url).status_code, 404)
        resposta = self.client.post(url, {"acao": "aprovar"})
        self.assertEqual(resposta.status_code, 404)
        alheio.refresh_from_db()
        self.assertEqual(alheio.status, StatusPedido.PENDENTE)

    def test_aprovar_atualiza_pedido_e_animal(self):
        resposta = self.responder("aprovar", "Venha conhecer o Rex.")
        self.pedido.refresh_from_db()
        self.rex.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusPedido.APROVADO)
        self.assertEqual(self.pedido.resposta_ong, "Venha conhecer o Rex.")
        self.assertEqual(self.rex.status, Pet.Status.EM_PROCESSO)
        self.assertContains(resposta, "atualizado para aprovado")

    def test_recusar_exige_motivo(self):
        resposta = self.responder("recusar", "  ")
        self.assertContains(resposta, "Explique ao adotante o motivo da recusa")
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusPedido.PENDENTE)

    def test_recusar_com_motivo(self):
        self.responder("recusar", "Perfil incompatível com o porte do animal.")
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusPedido.RECUSADO)

    def test_transicao_proibida_mostra_o_erro_sem_alterar_nada(self):
        resposta = self.responder("concluir")
        self.assertContains(resposta, "não pode ir para")
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusPedido.PENDENTE)

    def test_acao_desconhecida_e_recusada(self):
        resposta = self.responder("apagar")
        self.assertEqual(resposta.status_code, 200)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.status, StatusPedido.PENDENTE)

    def test_adocao_completa_recusa_os_concorrentes(self):
        concorrente = self.criar_pedido(adotante=self.bruno, pet=self.rex)
        self.responder("aprovar")
        resposta = self.responder("concluir", "Boa adoção!")
        self.rex.refresh_from_db()
        concorrente.refresh_from_db()
        self.assertEqual(self.rex.status, Pet.Status.ADOTADO)
        self.assertEqual(concorrente.status, StatusPedido.RECUSADO)
        self.assertContains(resposta, "atualizado para concluído")

    def test_nao_aprova_segundo_candidato_para_o_mesmo_animal(self):
        segundo = self.criar_pedido(adotante=self.bruno, pet=self.rex)
        self.responder("aprovar")
        resposta = self.responder("aprovar", pedido=segundo)
        self.assertContains(resposta, "já tem um pedido aprovado")
        segundo.refresh_from_db()
        self.assertEqual(segundo.status, StatusPedido.PENDENTE)

    def test_botoes_seguem_o_que_o_status_permite(self):
        resposta = self.client.get(self.url)
        for valor in ["analisar", "aprovar", "recusar"]:
            self.assertContains(resposta, f'value="{valor}"')
        self.assertNotContains(resposta, 'value="concluir"')

    def test_pedido_encerrado_nao_tem_botoes(self):
        self.responder("recusar", "Sem espaço.")
        resposta = self.client.get(self.url)
        self.assertContains(resposta, "está encerrado")
        self.assertNotContains(resposta, 'name="acao"')
