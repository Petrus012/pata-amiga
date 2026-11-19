from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth import views as auth_views
from django.shortcuts import redirect
from django.urls import reverse_lazy
from django.views.generic import CreateView

from .forms import CadastroForm


class EntrarView(auth_views.LoginView):
    template_name = "registration/login.html"
    redirect_authenticated_user = True

    def form_valid(self, form):
        messages.success(self.request, f"Bem-vindo de volta, {form.get_user()}.")
        return super().form_valid(form)


class SairView(auth_views.LogoutView):
    def dispatch(self, request, *args, **kwargs):
        # A mensagem é montada antes do logout: depois dele a sessão foi trocada e o
        # usuário da requisição já é anônimo.
        if request.method == "POST" and request.user.is_authenticated:
            messages.info(request, "Você saiu da sua conta.")
        return super().dispatch(request, *args, **kwargs)


class CadastroView(CreateView):
    form_class = CadastroForm
    template_name = "contas/cadastro.html"
    success_url = reverse_lazy("home")

    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            messages.info(request, "Você já está com a conta conectada.")
            return redirect("home")
        return super().dispatch(request, *args, **kwargs)

    def form_valid(self, form):
        resposta = super().form_valid(form)
        # Entrar automaticamente evita mandar quem acabou de se cadastrar para o login.
        login(self.request, self.object)
        messages.success(
            self.request,
            f"Conta criada. Bem-vindo à Pata Amiga, {self.object}.",
        )
        return resposta

    def form_invalid(self, form):
        messages.error(self.request, "Confira os campos destacados e tente de novo.")
        return super().form_invalid(form)
