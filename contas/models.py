from django.contrib.auth.models import AbstractUser
from django.db import models


class Usuario(AbstractUser):
    class Tipo(models.TextChoices):
        ADMIN = "ADMIN", "Administrador"
        ONG = "ONG", "ONG ou protetor"
        ADOTANTE = "ADOTANTE", "Adotante"

    tipo = models.CharField(
        "tipo de conta",
        max_length=10,
        choices=Tipo.choices,
        default=Tipo.ADOTANTE,
    )
    telefone = models.CharField(max_length=20, blank=True)
    cidade = models.CharField(max_length=80, blank=True)

    class Meta:
        verbose_name = "usuário"
        verbose_name_plural = "usuários"
        ordering = ["username"]

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def eh_ong(self):
        return self.tipo == self.Tipo.ONG

    @property
    def eh_adotante(self):
        return self.tipo == self.Tipo.ADOTANTE