from django.contrib.auth.mixins import UserPassesTestMixin


class PerfilRequiredMixin(UserPassesTestMixin):
    """Base dos mixins de perfil.

    Anônimo é mandado para o login. Quem já está logado com o perfil errado recebe 403,
    porque redirecionar para o login de novo daria a impressão de senha incorreta.
    """

    def handle_no_permission(self):
        self.raise_exception = self.request.user.is_authenticated
        return super().handle_no_permission()


class AdotanteRequiredMixin(PerfilRequiredMixin):
    def test_func(self):
        return self.request.user.is_authenticated and self.request.user.eh_adotante


class OngRequiredMixin(PerfilRequiredMixin):
    def test_func(self):
        usuario = self.request.user
        # Ter o tipo ONG não basta: sem o registro de Ong não há animais nem pedidos
        # para mostrar, e as views usam usuario.ong diretamente.
        return usuario.is_authenticated and usuario.eh_ong and hasattr(usuario, "ong")
