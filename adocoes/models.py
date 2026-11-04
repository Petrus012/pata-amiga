from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone

from contas.models import Usuario
from pets.models import Pet


# O status fica fora do modelo porque a Meta da restrição de pedido aberto precisa dele,
# e a Meta não enxerga atributos declarados dentro da classe do modelo.
class StatusPedido(models.TextChoices):
    PENDENTE = "PENDENTE", "Pendente"
    EM_ANALISE = "EM_ANALISE", "Em análise"
    APROVADO = "APROVADO", "Aprovado"
    RECUSADO = "RECUSADO", "Recusado"
    CONCLUIDO = "CONCLUIDO", "Concluído"


# Recusado e concluído encerram o pedido. Nos demais ele ainda está em andamento.
STATUS_EM_ABERTO = [StatusPedido.PENDENTE, StatusPedido.EM_ANALISE, StatusPedido.APROVADO]

# Enquanto o pedido está nestes status, a ONG ainda não deu uma resposta final.
STATUS_AGUARDANDO_RESPOSTA = [StatusPedido.PENDENTE, StatusPedido.EM_ANALISE]


class PedidoAdocao(models.Model):
    Status = StatusPedido

    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name="pedidos",
        verbose_name="animal",
    )
    adotante = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pedidos_adocao",
        limit_choices_to={"tipo": Usuario.Tipo.ADOTANTE},
    )
    status = models.CharField(
        max_length=10,
        choices=StatusPedido.choices,
        default=StatusPedido.PENDENTE,
    )
    mensagem = models.TextField(
        help_text="Por que quer adotar este animal e como é a rotina da casa.",
    )
    resposta_ong = models.TextField("resposta da ONG", blank=True)
    solicitado_em = models.DateTimeField(auto_now_add=True)
    respondido_em = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "pedido de adoção"
        verbose_name_plural = "pedidos de adoção"
        ordering = ["-solicitado_em"]
        constraints = [
            # Restrição parcial: só vale para pedidos em aberto. Depois de uma recusa,
            # o mesmo adotante pode tentar de novo pelo mesmo animal.
            models.UniqueConstraint(
                fields=["pet", "adotante"],
                condition=Q(status__in=STATUS_EM_ABERTO),
                name="pedido_aberto_unico_por_adotante",
                violation_error_message="Este adotante já tem um pedido em aberto para este animal.",
            )
        ]

    def __str__(self):
        return f"Pedido de {self.adotante} por {self.pet.nome}"

    def clean(self):
        # Só vale na criação: um pedido antigo continua válido depois que o animal é adotado.
        # O erro não é ligado ao campo pet porque o formulário do adotante não terá esse
        # campo (o animal vem da página), e o Django lançaria ValueError nesse caso.
        if self._state.adding and self.pet_id and self.pet.status == Pet.Status.ADOTADO:
            raise ValidationError("Este animal já foi adotado e não recebe novos pedidos.")

    def save(self, *args, **kwargs):
        if self.status not in STATUS_AGUARDANDO_RESPOSTA and self.respondido_em is None:
            self.respondido_em = timezone.now()
        super().save(*args, **kwargs)

    @property
    def em_aberto(self):
        return self.status in STATUS_EM_ABERTO


class Favorito(models.Model):
    """Tabela intermediária da relação muitos para muitos entre adotante e animal."""

    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="favoritos",
        verbose_name="usuário",
        limit_choices_to={"tipo": Usuario.Tipo.ADOTANTE},
    )
    pet = models.ForeignKey(
        Pet,
        on_delete=models.CASCADE,
        related_name="favoritos",
        verbose_name="animal",
    )
    criado_em = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "favorito"
        verbose_name_plural = "favoritos"
        ordering = ["-criado_em"]
        constraints = [
            models.UniqueConstraint(
                fields=["usuario", "pet"],
                name="favorito_unico_por_usuario",
                violation_error_message="Este animal já está nos favoritos do usuário.",
            )
        ]

    def __str__(self):
        return f"{self.pet.nome} favoritado por {self.usuario}"


class Acompanhamento(models.Model):
    """Relato do adotante sobre a adaptação do animal depois da adoção."""

    pedido = models.ForeignKey(
        PedidoAdocao,
        on_delete=models.CASCADE,
        related_name="acompanhamentos",
        verbose_name="pedido de adoção",
        limit_choices_to={"status": StatusPedido.CONCLUIDO},
    )
    relato = models.TextField(help_text="Como o animal está se adaptando ao novo lar.")
    foto = models.ImageField(upload_to="acompanhamentos/%Y/%m/", blank=True)
    data = models.DateField(default=timezone.localdate)

    class Meta:
        verbose_name = "acompanhamento"
        verbose_name_plural = "acompanhamentos"
        ordering = ["-data"]

    def __str__(self):
        return f"Acompanhamento de {self.pedido.pet.nome} em {self.data:%d/%m/%Y}"

    def clean(self):
        # O pedido pode não estar definido aqui quando o campo veio vazio no formulário;
        # nesse caso o próprio campo já acusa o erro de obrigatório.
        pedido = getattr(self, "pedido", None)
        if pedido and pedido.status != StatusPedido.CONCLUIDO:
            raise ValidationError("Só é possível registrar acompanhamento de adoções concluídas.")
