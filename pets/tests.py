from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import TestCase

from .models import Especie, Pet, Raca


class PetCleanTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.cachorro = Especie.objects.create(nome="Cachorro")
        cls.gato = Especie.objects.create(nome="Gato")
        cls.poodle = Raca.objects.create(nome="Poodle", especie=cls.cachorro)

    def test_recusa_raca_de_outra_especie(self):
        pet = Pet(nome="Mimi", especie=self.gato, raca=self.poodle)
        with self.assertRaises(ValidationError) as erro:
            pet.clean()
        self.assertIn("raca", erro.exception.message_dict)

    def test_aceita_raca_da_mesma_especie(self):
        Pet(nome="Rex", especie=self.cachorro, raca=self.poodle).clean()

    def test_aceita_animal_sem_raca(self):
        Pet(nome="Tom", especie=self.gato).clean()


class RacaTests(TestCase):
    def test_nome_repetido_so_e_barrado_na_mesma_especie(self):
        cachorro = Especie.objects.create(nome="Cachorro")
        gato = Especie.objects.create(nome="Gato")
        Raca.objects.create(nome="SRD", especie=cachorro)
        Raca.objects.create(nome="SRD", especie=gato)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Raca.objects.create(nome="SRD", especie=cachorro)


class FixtureEspeciesRacasTests(TestCase):
    fixtures = ["especies_racas"]

    def test_toda_especie_tem_racas_e_opcao_srd(self):
        self.assertEqual(Especie.objects.count(), 3)
        for especie in Especie.objects.all():
            with self.subTest(especie=especie.nome):
                self.assertTrue(especie.racas.filter(nome="SRD").exists())

    def test_acentos_foram_preservados(self):
        self.assertTrue(Raca.objects.filter(nome="Pastor Alemão").exists())


class FaixaEtariaTests(TestCase):
    def test_limites_de_cada_faixa(self):
        casos = {
            0: "Filhote",
            1: "Jovem",
            2: "Jovem",
            3: "Adulto",
            7: "Adulto",
            8: "Idoso",
        }
        for idade, esperado in casos.items():
            with self.subTest(idade=idade):
                self.assertEqual(Pet(idade_aproximada=idade).faixa_etaria, esperado)
