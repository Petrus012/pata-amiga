from django.core.exceptions import ValidationError
from django.db import models
from django.urls import reverse


class Especie(models.Model):
    nome = models.CharField(max_length=40, unique=True)

    class Meta:
        verbose_name = "espécie"
        verbose_name_plural = "espécies"
        ordering = ["nome"]

    def __str__(self):
        return self.nome


class Raca(models.Model):
    nome = models.CharField(max_length=60)
    especie = models.ForeignKey(
        Especie,
        on_delete=models.CASCADE,
        related_name="racas",
        verbose_name="espécie",
    )

    class Meta:
        verbose_name = "raça"
        verbose_name_plural = "raças"
        ordering = ["especie__nome", "nome"]
        constraints = [
            models.UniqueConstraint(
                fields=["especie", "nome"],
                name="raca_unica_por_especie",
            )
        ]

    def __str__(self):
        return f"{self.nome} ({self.especie})"


class Pet(models.Model):
    class Sexo(models.TextChoices):
        MACHO = "M", "Macho"
        FEMEA = "F", "Fêmea"

    class Porte(models.TextChoices):
        PEQUENO = "P", "Pequeno"
        MEDIO = "M", "Médio"
        GRANDE = "G", "Grande"

    class Status(models.TextChoices):
        DISPONIVEL = "DISPONIVEL", "Disponível"
        EM_PROCESSO = "EM_PROCESSO", "Em processo de adoção"
        ADOTADO = "ADOTADO", "Adotado"

    nome = models.CharField(max_length=60)
    especie = models.ForeignKey(
        Especie,
        on_delete=models.PROTECT,
        related_name="pets",
        verbose_name="espécie",
    )
    raca = models.ForeignKey(
        Raca,
        on_delete=models.SET_NULL,
        related_name="pets",
        null=True,
        blank=True,
        verbose_name="raça",
    )
    ong = models.ForeignKey(
        "contas.Ong",
        on_delete=models.CASCADE,
        related_name="pets",
        verbose_name="ONG responsável",
    )
    sexo = models.CharField(max_length=1, choices=Sexo.choices)
    porte = models.CharField(max_length=1, choices=Porte.choices)
    idade_aproximada = models.PositiveSmallIntegerField(
        help_text="Idade aproximada em anos. Use 0 para filhotes com menos de um ano.",
    )
    castrado = models.BooleanField(default=False)
    vacinado = models.BooleanField(default=False)
    descricao = models.TextField(
        "descrição",
        help_text="Temperamento, histórico e cuidados especiais.",
    )
    foto = models.ImageField(upload_to="pets/%Y/%m/", blank=True)
    status = models.CharField(
        max_length=12,
        choices=Status.choices,
        default=Status.DISPONIVEL,
    )
    criado_em = models.DateTimeField(auto_now_add=True)
    atualizado_em = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "animal"
        verbose_name_plural = "animais"
        ordering = ["-criado_em"]
        indexes = [models.Index(fields=["status", "especie"])]

    def __str__(self):
        return f"{self.nome} ({self.especie})"

    def clean(self):
        # A raça é opcional, mas quando informada precisa ser da espécie do animal.
        # O erro não é ligado ao campo raca porque nem todo formulário tem esse campo,
        # como a edição em lista do admin, e o Django lançaria ValueError nesses casos.
        if self.raca_id and self.especie_id and self.raca.especie_id != self.especie_id:
            raise ValidationError("Esta raça não pertence à espécie selecionada.")

    def get_absolute_url(self):
        return reverse("pets:detalhe", kwargs={"pk": self.pk})

    @property
    def disponivel(self):
        return self.status == self.Status.DISPONIVEL

    @property
    def faixa_etaria(self):
        if self.idade_aproximada == 0:
            return "Filhote"
        if self.idade_aproximada <= 2:
            return "Jovem"
        if self.idade_aproximada <= 7:
            return "Adulto"
        return "Idoso"


class Vacina(models.Model):
    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name="vacinas",
        verbose_name="animal",
    )
    nome = models.CharField(max_length=80)
    data_aplicacao = models.DateField("data de aplicação")
    observacao = models.CharField("observação", max_length=160, blank=True)

    class Meta:
        verbose_name = "vacina"
        verbose_name_plural = "vacinas"
        ordering = ["-data_aplicacao"]

    def __str__(self):
        return f"{self.nome} em {self.data_aplicacao:%d/%m/%Y}"
