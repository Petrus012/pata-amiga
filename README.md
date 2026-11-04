# Pata Amiga

Plataforma web de adoção responsável de animais, desenvolvida como trabalho prático da disciplina GAC116 (Programação Web) da Universidade Federal de Lavras.

## Integrantes

| Nome | Matrícula | GitHub |
|---|---|---|
| Pyêtro Augusto Malaquias | 202320986 | [@Petrus012](https://github.com/Petrus012) |
| Lídio Júnior Pereira Batista | 202320988 | [@lidiojr0](https://github.com/lidiojr0) |
| João Vitor Givisiez Lessa | 202321062 | [@joao-givisiez](https://github.com/joao-givisiez) |

## Descrição do projeto

ONGs e protetores independentes divulgam animais para adoção em grupos de mensagem e redes sociais, onde as informações se perdem e não há registro de quem demonstrou interesse. O Pata Amiga reúne esses anúncios em um catálogo único e organiza o processo de adoção do primeiro contato até a entrega do animal.

O sistema tem três perfis de usuário com permissões distintas. O administrador trabalha pelo ambiente administrativo, modera os cadastros e verifica as instituições. A ONG cadastra e mantém os próprios animais, acompanha o histórico de vacinas e analisa os pedidos que recebe, sem acesso aos animais de outras instituições. O adotante navega o catálogo, favorita animais, envia pedidos de adoção e acompanha a resposta de cada um.

Um pedido de adoção percorre os estados pendente, em análise, aprovado, recusado e concluído. Quando um pedido é concluído, o animal sai do catálogo e os demais pedidos em aberto para aquele animal são recusados automaticamente, o que evita que duas pessoas sejam aprovadas para o mesmo animal. Depois da adoção, o adotante pode registrar acompanhamentos com fotos e relatos.

## Tecnologias utilizadas

- Python 3.12 ou superior (exigência do Django 6.1)
- Django 6.1.3
- SQLite (banco de dados relacional usado em desenvolvimento)
- Bootstrap 5 (interface da aplicação)
- django-jazzmin 3.0.5 (tema do ambiente administrativo)
- Pillow 13.0.0 (upload de imagens)

As versões exatas das dependências Python estão no `requirements.txt`.

## Instalação

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

O comando `seed` carrega a fixture de espécies e raças, cria as ONGs, os adotantes, os animais e alguns pedidos de adoção. Para recriar os dados do zero, use `python manage.py seed --limpar`.

## Execução

```bash
python manage.py runserver
```

- Aplicação: http://localhost:8000
- Ambiente administrativo: http://localhost:8000/admin

Usuários de demonstração criados pelo comando `seed`, todos com a senha `pataamiga123`:

| Perfil | Usuário |
|---|---|
| ONG | `patas.unidas` |
| ONG | `lar.dos.focinhos` |
| ONG | `amigo.fiel` |
| Adotante | `ana.souza` |
| Adotante | `bruno.lima` |
| Adotante | `carla.dias` |
| Adotante | `diego.rocha` |

O acesso ao ambiente administrativo exige um superusuário, criado com `python manage.py createsuperuser`.

## Principais funcionalidades

**Administrador**

- Acesso completo ao ambiente administrativo, com tema personalizado pelo Jazzmin
- Cadastro, consulta, edição e exclusão de todas as entidades do sistema
- Verificação das ONGs, editável diretamente na listagem
- Filtros por espécie, porte, sexo, status, castrado, vacinado e data de cadastro
- Busca por nome do animal, nome fantasia da ONG, CNPJ, cidade e usuário
- Registro de vacinas embutido na página do animal
- Gestão dos grupos ONG e Adotante e das permissões de cada um

**ONG ou protetor**

- Cadastro dos próprios animais, com foto, espécie, raça, porte, sexo e idade aproximada
- Controle do histórico de vacinas de cada animal
- Acompanhamento do status de cada animal entre disponível, em processo de adoção e adotado
- Análise dos pedidos de adoção recebidos, com aprovação ou recusa e resposta ao adotante

**Adotante**

- Navegação pelo catálogo de animais disponíveis, com busca e filtros
- Página de detalhe de cada animal, com informações de saúde e da instituição responsável
- Envio de pedidos de adoção, com mensagem de apresentação
- Favoritos, para acompanhar animais de interesse
- Consulta ao histórico dos próprios pedidos e ao retorno da ONG
- Registro de acompanhamentos após a adoção, com relato e foto

## Estrutura do projeto

```
pata-amiga/
├── core/              # configuração do projeto (settings, urls, wsgi)
├── contas/            # usuário customizado, perfis, autenticação e permissões
│   └── management/    # comando seed, com dados de demonstração
├── pets/              # espécies, raças, animais e vacinas
│   ├── fixtures/      # carga inicial de espécies e raças
│   └── migrations/    # histórico de alterações do banco
├── adocoes/           # pedidos de adoção, favoritos e acompanhamento
├── templates/         # templates compartilhados, base.html
├── static/
│   ├── css/           # ajustes visuais do ambiente administrativo
│   ├── img/           # logo da aplicação
│   └── js/            # alternador de tema claro e escuro
├── media/             # imagens enviadas pelos usuários (fora do versionamento)
├── LICENSE
├── manage.py
├── README.md
└── requirements.txt
```

## Modelo de dados

O projeto está dividido em três aplicativos, com dez modelos no total.

**contas**

- `Usuario` estende o `AbstractUser` do Django e acrescenta o tipo de conta, que separa administrador, ONG e adotante
- `Perfil` tem relação um para um com o usuário e guarda os dados que a ONG consulta na análise do pedido, como tipo de moradia e se já convive com outros animais
- `Ong` tem relação um para um com o usuário responsável e guarda nome fantasia, CNPJ, cidade e o indicador de instituição verificada

**pets**

- `Especie` e `Raca` formam a classificação dos animais, com raça vinculada a uma espécie e restrição de nome único dentro de cada espécie
- `Pet` referencia a espécie, a raça (opcional) e a ONG responsável, e controla o status entre disponível, em processo de adoção e adotado
- `Vacina` registra o histórico de vacinação de cada animal

**adocoes**

- `PedidoAdocao` liga um animal a um adotante e percorre cinco estados. Uma restrição condicional impede que o mesmo adotante tenha dois pedidos em aberto para o mesmo animal, mas permite nova solicitação se o pedido anterior foi recusado
- `Favorito` liga usuário e animal, com restrição de unicidade por par
- `Acompanhamento` registra os relatos enviados após a conclusão da adoção

As permissões dos grupos ONG e Adotante são criadas por migração de dados, junto com os próprios grupos, de modo que um banco recém-criado já nasce com os perfis configurados.

## Organização do desenvolvimento

O repositório segue o fluxo com as branches `main` (versões apresentadas nos checkpoints), `develop` (integração) e `feature/*` (uma por frente de trabalho). Cada alteração entra na `develop` por pull request, revisado por um integrante que não escreveu o código. As mensagens de commit seguem o padrão `tipo(escopo): descrição`.

A divisão de responsabilidades foi feita por aplicativo. Pyêtro ficou com `contas`, a configuração do projeto e a autenticação. Lídio ficou com `pets` e o ambiente administrativo. João ficou com `adocoes` e a interface.

## Licença

Distribuído sob a licença MIT. Veja o arquivo [LICENSE](LICENSE).
