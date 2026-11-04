from django.views.generic import ListView

from .models import Pet


class CatalogoView(ListView):
    template_name = "pets/catalogo.html"
    context_object_name = "pets"
    paginate_by = 12

    def get_queryset(self):
        # Animais em processo de adoção continuam visíveis, porque o pedido ainda pode
        # não dar certo. Só os já adotados saem do catálogo.
        return Pet.objects.exclude(status=Pet.Status.ADOTADO).select_related(
            "especie", "raca", "ong"
        )
