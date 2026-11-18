# Testes do formulário de animal e do formset de vacinas usados na área da ONG.
import io

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from PIL import Image

from contas.models import Ong, Usuario

from .forms import TAMANHO_MAXIMO_FOTO_MB, PetForm, VacinaFormSet
from .models import IDADE_MAXIMA, Especie, Pet, Raca, Vacina


def imagem(formato="PNG", tamanho=(4, 4), nome="foto.png"):
    arquivo = io.BytesIO()
    Image.new("RGB", tamanho).save(arquivo, format=formato)
    return SimpleUploadedFile(nome, arquivo.getvalue(), content_type=f"image/{formato.lower()}")


class FormulariosTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        responsavel = Usuario.objects.create_user("ong1", password="senha", tipo=Usuario.Tipo.ONG)
        cls.ong = Ong.objects.create(
            responsavel=responsavel, nome_fantasia="Patas Livres", cidade="Lavras"
        )
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.gato = Especie.objects.create(nome="Gato")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)
        cls.beagle = Raca.objects.create(nome="Beagle", especie=cls.cachorro)
        cls.siames = Raca.objects.create(nome="Siamês", especie=cls.gato)

    def dados(self, **extras):
        dados = {
            "nome": "Luna",
            "especie": self.gato.pk,
            "raca": self.siames.pk,
            "sexo": Pet.Sexo.FEMEA,
            "porte": Pet.Porte.PEQUENO,
            "idade_aproximada": 2,
            "descricao": "Calma e carinhosa.",
        }
        dados.update(extras)
        return dados


class PetFormTests(FormulariosTestCase):
    def test_ong_e_status_ficam_fora_do_formulario(self):
        self.assertNotIn("ong", PetForm.base_fields)
        self.assertNotIn("status", PetForm.base_fields)

    def test_dados_validos_criam_animal_disponivel(self):
        form = PetForm(self.dados())
        self.assertTrue(form.is_valid(), form.errors)
        pet = form.save(commit=False)
        pet.ong = self.ong
        pet.save()
        self.assertEqual(pet.status, Pet.Status.DISPONIVEL)

    def test_status_enviado_a_forca_e_ignorado(self):
        form = PetForm(self.dados(status=Pet.Status.ADOTADO))
        self.assertTrue(form.is_valid(), form.errors)
        self.assertEqual(form.save(commit=False).status, Pet.Status.DISPONIVEL)

    def test_raca_de_outra_especie_e_recusada(self):
        form = PetForm(self.dados(raca=self.poodle.pk))
        self.assertFalse(form.is_valid())
        self.assertIn("não pertence à espécie", " ".join(form.non_field_errors()))

    def test_racas_aparecem_agrupadas_por_especie(self):
        escolhas = PetForm().fields["raca"].choices
        self.assertEqual(escolhas[0], ("", "Não informada"))
        grupos = dict(escolhas[1:])
        self.assertEqual(
            grupos,
            {
                "Cachorro": [(self.beagle.pk, "Beagle"), (self.poodle.pk, "Poodle")],
                "Gato": [(self.siames.pk, "Siamês")],
            },
        )

    def test_menus_tem_texto_inicial_em_portugues(self):
        html = str(PetForm())
        self.assertNotIn("Select an option", html)
        for texto in ["Escolha a espécie", "Escolha o sexo", "Escolha o porte", "Não informada"]:
            with self.subTest(texto=texto):
                self.assertIn(texto, html)

    def test_animal_sem_raca_e_aceito(self):
        self.assertTrue(PetForm(self.dados(raca="")).is_valid())

    def test_idade_acima_do_limite_e_recusada(self):
        form = PetForm(self.dados(idade_aproximada=IDADE_MAXIMA + 1))
        self.assertFalse(form.is_valid())
        self.assertIn("idade_aproximada", form.errors)

    def test_foto_pequena_e_aceita(self):
        form = PetForm(self.dados(), {"foto": imagem()})
        self.assertTrue(form.is_valid(), form.errors)

    def test_foto_acima_do_limite_e_recusada(self):
        # Um BMP de 1400x1400 é uma imagem válida com cerca de 5,9 MB.
        grande = imagem("BMP", (1400, 1400), "grande.bmp")
        self.assertGreater(grande.size, TAMANHO_MAXIMO_FOTO_MB * 1024 * 1024)
        form = PetForm(self.dados(), {"foto": grande})
        self.assertFalse(form.is_valid())
        self.assertIn(f"no máximo {TAMANHO_MAXIMO_FOTO_MB} MB", " ".join(form.errors["foto"]))

    def test_arquivo_que_nao_e_imagem_e_recusado(self):
        falso = SimpleUploadedFile("foto.png", b"isto nao e uma imagem", content_type="image/png")
        form = PetForm(self.dados(), {"foto": falso})
        self.assertFalse(form.is_valid())
        self.assertIn("foto", form.errors)


class VacinaFormSetTests(FormulariosTestCase):
    def setUp(self):
        self.pet = Pet.objects.create(
            ong=self.ong,
            nome="Rex",
            especie=self.cachorro,
            sexo=Pet.Sexo.MACHO,
            porte=Pet.Porte.MEDIO,
            idade_aproximada=3,
            descricao="Dócil.",
        )

    def gerenciamento(self, total, iniciais):
        return {
            "vacinas-TOTAL_FORMS": total,
            "vacinas-INITIAL_FORMS": iniciais,
            "vacinas-MIN_NUM_FORMS": 0,
            "vacinas-MAX_NUM_FORMS": 1000,
        }

    def test_cria_vacina_e_ignora_linha_em_branco(self):
        dados = {
            **self.gerenciamento(2, 0),
            "vacinas-0-nome": "V10",
            "vacinas-0-data_aplicacao": "2026-10-01",
            "vacinas-1-nome": "",
            "vacinas-1-data_aplicacao": "",
        }
        formset = VacinaFormSet(dados, instance=self.pet)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertEqual([v.nome for v in self.pet.vacinas.all()], ["V10"])

    def test_remove_vacina_marcada(self):
        vacina = Vacina.objects.create(pet=self.pet, nome="V8", data_aplicacao="2026-08-01")
        dados = {
            **self.gerenciamento(1, 1),
            "vacinas-0-id": vacina.pk,
            "vacinas-0-nome": "V8",
            "vacinas-0-data_aplicacao": "2026-08-01",
            "vacinas-0-DELETE": "on",
        }
        formset = VacinaFormSet(dados, instance=self.pet)
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        self.assertFalse(self.pet.vacinas.exists())

    def test_vacina_sem_data_e_recusada(self):
        dados = {**self.gerenciamento(1, 0), "vacinas-0-nome": "V10"}
        formset = VacinaFormSet(dados, instance=self.pet)
        self.assertFalse(formset.is_valid())
        self.assertIn("data_aplicacao", formset.errors[0])

    def test_formset_nao_altera_vacina_de_outro_animal(self):
        outro = Pet.objects.create(
            ong=self.ong,
            nome="Bob",
            especie=self.cachorro,
            sexo=Pet.Sexo.MACHO,
            porte=Pet.Porte.MEDIO,
            idade_aproximada=3,
            descricao="Dócil.",
        )
        alheia = Vacina.objects.create(pet=outro, nome="V8", data_aplicacao="2026-08-01")
        dados = {
            **self.gerenciamento(1, 1),
            "vacinas-0-id": alheia.pk,
            "vacinas-0-nome": "Trocada",
            "vacinas-0-data_aplicacao": "2026-08-01",
        }
        formset = VacinaFormSet(dados, instance=self.pet)
        # O formset só procura vacinas entre as do próprio animal. Um id de outro animal
        # não é encontrado, e a linha é descartada ao salvar, sem erro e sem efeito.
        self.assertTrue(formset.is_valid(), formset.errors)
        formset.save()
        alheia.refresh_from_db()
        self.assertEqual((alheia.nome, alheia.pet), ("V8", outro))
        self.assertFalse(self.pet.vacinas.exists())
