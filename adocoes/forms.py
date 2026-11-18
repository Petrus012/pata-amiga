from django import forms

from .models import (
    STATUS_EM_ABERTO,
    Acompanhamento,
    PedidoAdocao,
    StatusPedido,
)

# Cada botão do painel da ONG envia uma destas ações.
ACOES_DA_ONG = {
    "analisar": StatusPedido.EM_ANALISE,
    "aprovar": StatusPedido.APROVADO,
    "recusar": StatusPedido.RECUSADO,
    "concluir": StatusPedido.CONCLUIDO,
}


class PedidoAdocaoForm(forms.ModelForm):
    class Meta:
        model = PedidoAdocao
        fields = ["mensagem"]
        widgets = {
            "mensagem": forms.Textarea(
                attrs={
                    "rows": 6,
                    "class": "form-control",
                    "placeholder": "Conte um pouco sobre você, sua casa e sua rotina.",
                }
            )
        }

    def __init__(self, *args, pet, adotante, **kwargs):
        super().__init__(*args, **kwargs)
        self.pet = pet
        self.adotante = adotante

    def clean(self):
        # O animal e o adotante não são campos do formulário, então o Django não valida
        # a restrição de pedido aberto único nem a regra de animal já adotado. As duas
        # são conferidas aqui, antes de salvar, para o usuário ver uma mensagem em vez
        # de um erro 500. Se dois cliques chegarem juntos, o banco ainda barra o segundo.
        dados = super().clean()
        if PedidoAdocao.objects.filter(
            pet=self.pet, adotante=self.adotante, status__in=STATUS_EM_ABERTO
        ).exists():
            raise forms.ValidationError("Você já tem um pedido em aberto para este animal.")
        PedidoAdocao(pet=self.pet, adotante=self.adotante).clean()
        return dados


class ResponderPedidoForm(forms.Form):
    acao = forms.ChoiceField(choices=[(chave, chave) for chave in ACOES_DA_ONG])
    resposta = forms.CharField(
        required=False,
        label="Resposta ao adotante",
        widget=forms.Textarea(attrs={"rows": 4, "class": "form-control"}),
    )

    def clean(self):
        dados = super().clean()
        if dados.get("acao") == "recusar" and not dados.get("resposta", "").strip():
            self.add_error("resposta", "Explique ao adotante o motivo da recusa.")
        return dados


class AcompanhamentoForm(forms.ModelForm):
    class Meta:
        model = Acompanhamento
        fields = ["data", "relato", "foto"]
        widgets = {
            "data": forms.DateInput(
                format="%Y-%m-%d", attrs={"type": "date", "class": "form-control"}
            ),
            "relato": forms.Textarea(attrs={"rows": 5, "class": "form-control"}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control"}),
        }

    def __init__(self, *args, pedido, **kwargs):
        super().__init__(*args, **kwargs)
        # Com o pedido definido antes da validação, o clean() do modelo confere se a
        # adoção foi concluída.
        self.instance.pedido = pedido
