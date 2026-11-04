from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

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

class Perfil(models.Model):
    """Dados complementares do adotante, usados na análise do pedido pela ONG."""

    class Moradia(models.TextChoices):
        CASA = "CASA", "Casa com quintal"
        CASA_SEM_QUINTAL = "CASA_SEM_QUINTAL", "Casa sem quintal"
        APARTAMENTO = "APARTAMENTO", "Apartamento"
        SITIO = "SITIO", "Sítio ou chácara"

    usuario = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="perfil",
    )
    data_nascimento = models.DateField(null=True, blank=True)
    tipo_moradia = models.CharField(
        max_length=20,
        choices=Moradia.choices,
        blank=True,
    )
    tem_outros_animais = models.BooleanField("já tem outros animais", default=False)
    bio = models.TextField("apresentação", blank=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "perfil"
        verbose_name_plural = "perfis"

    def __str__(self):
        return f"Perfil de {self.usuario}"


class Ong(models.Model):
    """ONG ou protetor independente responsável por cadastrar animais."""

    responsavel = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="ong",
        limit_choices_to={"tipo": Usuario.Tipo.ONG},
    )
    nome_fantasia = models.CharField(max_length=120)
    cnpj = models.CharField(max_length=18, blank=True, null=True, unique=True)
    endereco = models.CharField(max_length=160, blank=True)
    cidade = models.CharField(max_length=80)
    telefone = models.CharField(max_length=20, blank=True)
    descricao = models.TextField(blank=True)
    verificada = models.BooleanField(
        default=False,
        help_text="Marcada pelo administrador após conferir os dados da instituição.",
    )
    criada_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "ONG"
        verbose_name_plural = "ONGs"
        ordering = ["nome_fantasia"]

    def __str__(self):
        return self.nome_fantasia

    @property
    def total_disponiveis(self):
        return self.pets.filter(status="DISPONIVEL").count()