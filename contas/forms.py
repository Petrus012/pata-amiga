from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.db import transaction

from .models import Ong, Perfil, Usuario


class CadastroForm(UserCreationForm):
    """Cadastro público, com um formulário só para os dois perfis.

    Os campos de ONG e de adotante convivem na mesma tela e são mostrados conforme o
    tipo escolhido. A obrigatoriedade de cada bloco é resolvida no clean, porque o
    required do campo valeria para os dois perfis.
    """

    TIPOS = [
        (Usuario.Tipo.ADOTANTE, "Quero adotar um animal"),
        (Usuario.Tipo.ONG, "Represento uma ONG ou sou protetor"),
    ]

    tipo = forms.ChoiceField(
        label="Tipo de conta",
        choices=TIPOS,
        initial=Usuario.Tipo.ADOTANTE,
        widget=forms.RadioSelect,
    )
    first_name = forms.CharField(label="Nome", max_length=150)
    last_name = forms.CharField(label="Sobrenome", max_length=150, required=False)
    email = forms.EmailField(label="E-mail")
    cidade = forms.CharField(label="Cidade", max_length=80)
    telefone = forms.CharField(label="Telefone", max_length=20, required=False)

    nome_fantasia = forms.CharField(
        label="Nome da ONG ou do protetor",
        max_length=120,
        required=False,
    )
    cnpj = forms.CharField(label="CNPJ", max_length=18, required=False)

    tipo_moradia = forms.ChoiceField(
        label="Tipo de moradia",
        choices=[("", "Prefiro não informar")] + Perfil.Moradia.choices,
        required=False,
    )
    tem_outros_animais = forms.BooleanField(
        label="Já convivo com outros animais",
        required=False,
    )

    class Meta:
        model = Usuario
        fields = ["username", "first_name", "last_name", "email", "cidade", "telefone"]
        labels = {"username": "Nome de usuário"}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for nome, campo in self.fields.items():
            if nome == "tipo":
                continue
            if isinstance(campo.widget, forms.CheckboxInput):
                campo.widget.attrs.setdefault("class", "form-check-input")
            elif isinstance(campo.widget, forms.Select):
                campo.widget.attrs.setdefault("class", "form-select")
            else:
                campo.widget.attrs.setdefault("class", "form-control")

    def clean_email(self):
        email = self.cleaned_data["email"]
        if Usuario.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("Já existe uma conta com este e-mail.")
        return email

    def clean_cnpj(self):
        # O CNPJ é único no banco, e uma string vazia se repetiria entre as ONGs que
        # não informam o número. Guardar None evita o erro de duplicidade.
        cnpj = self.cleaned_data.get("cnpj", "").strip()
        if not cnpj:
            return None
        if Ong.objects.filter(cnpj=cnpj).exists():
            raise forms.ValidationError("Já existe uma ONG cadastrada com este CNPJ.")
        return cnpj

    def clean(self):
        dados = super().clean()
        if dados.get("tipo") == Usuario.Tipo.ONG and not dados.get("nome_fantasia"):
            self.add_error(
                "nome_fantasia",
                "Informe o nome da ONG ou do protetor responsável.",
            )
        return dados

    @transaction.atomic
    def save(self, commit=True):
        usuario = super().save(commit=False)
        usuario.tipo = self.cleaned_data["tipo"]
        usuario.cidade = self.cleaned_data["cidade"]
        usuario.telefone = self.cleaned_data["telefone"]
        usuario.save()

        if usuario.eh_ong:
            usuario.groups.add(Group.objects.get(name="ONG"))
            Ong.objects.create(
                responsavel=usuario,
                nome_fantasia=self.cleaned_data["nome_fantasia"],
                cnpj=self.cleaned_data["cnpj"],
                cidade=usuario.cidade,
                telefone=usuario.telefone,
            )
        else:
            usuario.groups.add(Group.objects.get(name="Adotante"))
            Perfil.objects.create(
                usuario=usuario,
                tipo_moradia=self.cleaned_data["tipo_moradia"],
                tem_outros_animais=self.cleaned_data["tem_outros_animais"],
            )

        return usuario
