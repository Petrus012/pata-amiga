from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.forms import inlineformset_factory

from .models import IDADE_MAXIMA, Pet, Raca, Vacina

TAMANHO_MAXIMO_FOTO_MB = 5


class PetForm(forms.ModelForm):
    """Cadastro e edição de animal pela própria ONG.

    Ficam de fora a ONG, que vem do usuário logado, e o status, que só muda pelo fluxo
    de adoção (aprovar, concluir, recusar). Assim a ONG não marca um animal como adotado
    sem um pedido por trás.
    """

    class Meta:
        model = Pet
        fields = [
            "nome",
            "especie",
            "raca",
            "sexo",
            "porte",
            "idade_aproximada",
            "castrado",
            "vacinado",
            "descricao",
            "foto",
        ]
        widgets = {
            "nome": forms.TextInput(attrs={"class": "form-control"}),
            "especie": forms.Select(attrs={"class": "form-select"}),
            "raca": forms.Select(attrs={"class": "form-select"}),
            "sexo": forms.Select(attrs={"class": "form-select"}),
            "porte": forms.Select(attrs={"class": "form-select"}),
            "idade_aproximada": forms.NumberInput(
                attrs={"class": "form-control", "min": 0, "max": IDADE_MAXIMA}
            ),
            "castrado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "vacinado": forms.CheckboxInput(attrs={"class": "form-check-input"}),
            "descricao": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
            "foto": forms.ClearableFileInput(attrs={"class": "form-control", "accept": "image/*"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Raças agrupadas por espécie, para a ONG não escolher Siamês para um cachorro.
        # A validação continua no Pet.clean(); o agrupamento só facilita a escolha.
        grupos = {}
        for raca in Raca.objects.select_related("especie"):
            grupos.setdefault(raca.especie.nome, []).append((raca.pk, raca.nome))
        self.fields["raca"].choices = [("", "Não informada"), *grupos.items()]

    def clean_foto(self):
        foto = self.cleaned_data.get("foto")
        # Só confere arquivos novos. Uma foto já salva não é enviada de novo na edição.
        if isinstance(foto, UploadedFile) and foto.size > TAMANHO_MAXIMO_FOTO_MB * 1024 * 1024:
            raise forms.ValidationError(
                f"A foto pode ter no máximo {TAMANHO_MAXIMO_FOTO_MB} MB."
            )
        return foto


# Vacinas na mesma tela do animal: uma linha por vacina, mais uma linha em branco para
# a próxima. Linha em branco é ignorada, e a caixa "remover" apaga a vacina ao salvar.
VacinaFormSet = inlineformset_factory(
    Pet,
    Vacina,
    fields=["nome", "data_aplicacao", "observacao"],
    extra=1,
    can_delete=True,
    widgets={
        "nome": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
        "data_aplicacao": forms.DateInput(
            format="%Y-%m-%d", attrs={"type": "date", "class": "form-control form-control-sm"}
        ),
        "observacao": forms.TextInput(attrs={"class": "form-control form-control-sm"}),
    },
)
