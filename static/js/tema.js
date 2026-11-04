// Tema claro ou escuro do Bootstrap, controlado pelo atributo data-bs-theme do <html>.
// Este arquivo é carregado no <head> sem defer para aplicar o tema antes de a página
// ser desenhada. Carregado no fim do <body>, a página piscaria no tema errado.
(function () {
  const CHAVE = "pata-amiga:tema";
  const raiz = document.documentElement;
  const sistemaEscuro = window.matchMedia("(prefers-color-scheme: dark)");

  // O localStorage pode estar bloqueado (navegação privada, por exemplo).
  // Nesse caso o tema segue o sistema e a escolha vale só até recarregar a página.
  function temaSalvo() {
    try {
      return localStorage.getItem(CHAVE);
    } catch (erro) {
      return null;
    }
  }

  function salvarTema(tema) {
    try {
      localStorage.setItem(CHAVE, tema);
    } catch (erro) {}
  }

  function temaPreferido() {
    return temaSalvo() || (sistemaEscuro.matches ? "dark" : "light");
  }

  function aplicarTema(tema) {
    raiz.setAttribute("data-bs-theme", tema);

    const botao = document.getElementById("alternar-tema");
    if (!botao) {
      return;
    }
    const escuro = tema === "dark";
    const rotulo = escuro ? "Usar tema claro" : "Usar tema escuro";
    botao.querySelector("i").className = escuro ? "bi bi-sun-fill" : "bi bi-moon-stars-fill";
    botao.setAttribute("aria-label", rotulo);
    botao.setAttribute("title", rotulo);
  }

  aplicarTema(temaPreferido());

  // Enquanto o usuário não escolher um tema, a página acompanha o sistema operacional.
  sistemaEscuro.addEventListener("change", function () {
    if (!temaSalvo()) {
      aplicarTema(temaPreferido());
    }
  });

  document.addEventListener("DOMContentLoaded", function () {
    const botao = document.getElementById("alternar-tema");
    if (!botao) {
      return;
    }
    aplicarTema(raiz.getAttribute("data-bs-theme"));
    botao.addEventListener("click", function () {
      const novo = raiz.getAttribute("data-bs-theme") === "dark" ? "light" : "dark";
      salvarTema(novo);
      aplicarTema(novo);
    });
  });
})();
