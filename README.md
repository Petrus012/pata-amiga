# Pata Amiga

Plataforma web de adoção responsável de animais, desenvolvida como trabalho prático da disciplina GAC116 (Programação Web) da Universidade Federal de Lavras.

> Esqueleto do README. Cada integrante preenche a seção sob sua responsabilidade (ver roteiro do grupo) e apaga este aviso antes do Checkpoint 2. Escrevam com as próprias palavras, sem copiar o texto do enunciado.

## Integrantes

| Nome | Matrícula | GitHub |
|---|---|---|
| Pyêtro Augusto Malaquias | 202320986 | [@Petrus012](https://github.com/Petrus012) |
| Lídio Júnior Pereira Batista | 202320988 | [@lidiojr0](https://github.com/lidiojr0) |
| João Vitor Givisiez Lessa | (preencher) | (preencher) |

## Descrição do projeto

<!-- Responsável: João. Dois ou três parágrafos: qual problema a aplicação resolve,
     quem são os perfis de usuário e o que cada um consegue fazer no sistema. -->

## Tecnologias utilizadas

- Python 3.12 ou superior (exigência do Django 6.1)
- Django 6.1.3
- SQLite (banco de dados relacional usado em desenvolvimento)
- Bootstrap 5 (interface da aplicação)
- django-jazzmin 3.0.5 (tema do ambiente administrativo)
- Pillow 13.0.0 (upload de imagens)

As versões exatas das dependências Python estão no `requirements.txt`.

## Instalação

<!-- Responsável: Pyêtro. Testar em um clone limpo antes de entregar. -->

```bash
git clone https://github.com/Petrus012/pata-amiga.git
cd pata-amiga

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python manage.py migrate
python manage.py seed            # popula o banco com dados de demonstração
python manage.py createsuperuser
```

## Execução

```bash
python manage.py runserver
```

- Aplicação: http://localhost:8000
- Ambiente administrativo: http://localhost:8000/admin

Usuários de demonstração criados pelo comando `seed`:

| Perfil | Usuário | Senha |
|---|---|---|
| ONG | (preencher) | (preencher) |
| Adotante | (preencher) | (preencher) |

## Principais funcionalidades

<!-- Responsável: João. Agrupar por perfil de usuário, sem repetir a descrição acima. -->

**Administrador**

- (preencher)

**ONG ou protetor**

- (preencher)

**Adotante**

- (preencher)

## Estrutura do projeto

<!-- Responsável: Lídio. Atualizar ao final, conferindo a árvore real do repositório. -->

```
pata-amiga/
├── core/              # configuração do projeto (settings, urls, wsgi)
├── contas/            # usuário customizado, perfis, autenticação e permissões
├── pets/              # espécies, raças, animais e vacinas
│   ├── fixtures/      # carga inicial de espécies e raças
│   └── migrations/    # histórico de alterações do banco
├── adocoes/           # pedidos de adoção, favoritos e acompanhamento
├── templates/         # templates compartilhados, base.html
├── static/
│   ├── css/           # ajustes visuais do ambiente administrativo
│   └── img/           # logo da aplicação
├── media/             # imagens enviadas pelos usuários (fora do versionamento)
├── LICENSE
├── manage.py
├── README.md
└── requirements.txt
```

## Modelo de dados

<!-- Opcional mas vale ponto em complexidade: incluir aqui o diagrama de entidades
     exportado do dbdiagram.io ou do próprio Django, como imagem em docs/. -->

## Organização do desenvolvimento

O repositório segue o fluxo com as branches `main` (versões apresentadas nos checkpoints), `develop` (integração) e `feature/*` (uma por frente de trabalho). As mensagens de commit seguem o padrão `tipo(escopo): descrição`.
