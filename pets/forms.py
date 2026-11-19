from django import forms
from django.core.files.uploadedfile import UploadedFile
from django.db.models import Q
from django.forms import inlineformset_factory

from .models import (
    FAIXAS_ETARIAS,
    IDADE_MAXIMA,
    Especie,
    Pet,
    Raca,
    Vacina,
    filtro_faixa_etaria,
)

TAMANHO_MAXIMO_FOTO_MB = 5


class CatalogoFiltroForm(forms.Form):
    """Busca e filtros do catálogo, enviados pela URL (GET).

    Cada filtro vale sozinho: um valor inválido na URL, como uma espécie que não
    existe, é descartado sem derrubar os outros filtros.
    """

    q = forms.CharField(
        required=False,
        label="Buscar",
        widget=forms.TextInput(
            attrs={
                "class": "form-control",
                "type": "search",
                "placeholder": "Nome, raça, ONG ou cidade",
            }
        ),
    )
    especie = forms.ModelChoiceField(
        queryset=Especie.objects.all(),
        required=False,
        label="Espécie",
        empty_label="Todas as espécies",
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    porte = forms.ChoiceField(
        required=False,
        choices=[("", "Qualquer porte"), *Pet.Porte.choices],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    sexo = forms.ChoiceField(
        required=False,
        choices=[("", "Qualquer sexo"), *Pet.Sexo.choices],
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    faixa = forms.ChoiceField(
        required=False,
        label="Faixa etária",
        choices=[("", "Qualquer idade"), *[(c, r) for c, r, _, _ in FAIXAS_ETARIAS]],
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def valores(self):
        # Depois de is_valid(), cleaned_data guarda só os campos válidos. Os inválidos
        # ficam de fora, e por isso são ignorados um a um.
        self.is_valid()
        return {campo: valor for campo, valor in self.cleaned_data.items() if valor}

    @property
    def ativo(self):
        return bool(self.valores())

    def filtrar(self, animais):
        valores = self.valores()
        # Cada palavra precisa aparecer em algum lugar: "gato lavras" acha gatos de
        # ONGs de Lavras, e não todos os gatos mais tudo o que é de Lavras.
        for palavra in valores.get("q", "").split():
            animais = animais.filter(
                Q(nome__icontains=palavra)
                | Q(raca__nome__icontains=palavra)
                | Q(especie__nome__icontains=palavra)
                | Q(ong__nome_fantasia__icontains=palavra)
                | Q(ong__cidade__icontains=palavra)
            )
        if "especie" in valores:
            animais = animais.filter(especie=valores["especie"])
        if "porte" in valores:
            animais = animais.filter(porte=valores["porte"])
        if "sexo" in valores:
            animais = animais.filter(sexo=valores["sexo"])
        if "faixa" in valores:
            animais = animais.filter(filtro_faixa_etaria(valores["faixa"]))
        return animais


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

        # O Django 6.1 trocou o "---------" por "- Select an option -", ainda sem
        # tradução para o português. Os menus obrigatórios ganham um convite próprio.
        self.fields["especie"].empty_label = "Escolha a espécie"
        self.fields["sexo"].choices = [("", "Escolha o sexo"), *Pet.Sexo.choices]
        self.fields["porte"].choices = [("", "Escolha o porte"), *Pet.Porte.choices]

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
