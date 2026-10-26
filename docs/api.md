# AutoPeças API

Referência técnica da API HTTP criada com FastAPI. A API é um serviço separado da interface Tkinter e reutiliza as regras de autenticação, permissões e persistência do projeto.

## Estado atual

A API está preparada para execução local, mas ainda não foi publicada na internet. Durante o desenvolvimento, usa o banco SQLite `autopecas.db` configurado para o Core. Não exponha o arquivo SQLite nem o servidor de desenvolvimento diretamente à internet.

Antes de disponibilizar acesso remoto, é necessário escolher uma hospedagem para a API, migrar para um banco gerenciado compartilhado (recomendação: PostgreSQL), configurar HTTPS, backups e um segredo persistente para assinatura dos tokens.

## Executar localmente

Instale as dependências a partir da raiz do projeto:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Inicie a API somente no computador local:

```powershell
.venv\Scripts\python.exe -m uvicorn api:create_app --factory --host 127.0.0.1 --port 8000
```

- Swagger UI: <http://127.0.0.1:8000/docs>
- OpenAPI JSON: <http://127.0.0.1:8000/openapi.json>
- Verificação de saúde: `GET /health`

A primeira execução cria o banco/migra os arquivos JSON conforme a inicialização do repositório. Para entrar, use uma conta já criada pela aplicação Core.

## Configuração

- `AUTOPECAS_DATABASE`: caminho do banco SQLite; por padrão usa `autopecas.db` na raiz do projeto.
- `AUTOPECAS_TOKEN_SECRET`: segredo usado para assinar tokens. Se omitido em desenvolvimento, é gerado aleatoriamente para o processo atual; reiniciar a API invalida os tokens. Em hospedagem, configure um segredo forte, privado e persistente por variável de ambiente ou gerenciador de segredos.

Não coloque segredos no código, no README, no repositório ou em arquivos enviados ao Git.

## Autenticação e permissões

1. Envie `POST /auth/login` com usuário e senha.
2. Use o `access_token` retornado no cabeçalho `Authorization: Bearer <token>`.
3. O token expira após oito horas.
4. A API reconsulta o usuário no banco a cada requisição autenticada, então contas removidas perdem acesso imediatamente.

| Perfil | Permissões |
| --- | --- |
| `user` (operacional) | Consulta produtos e histórico de vendas; registra vendas. |
| `admin` | Todas as permissões operacionais, além de criar/editar/excluir produtos, consultar relatório financeiro e gerenciar usuários. |

## Endpoints

### Autenticação

| Método | Rota | Acesso | Descrição |
| --- | --- | --- | --- |
| `POST` | `/auth/login` | Público | Valida credenciais e retorna token. |
| `GET` | `/auth/me` | Autenticado | Retorna o usuário e o perfil da sessão. |
| `GET` | `/health` | Público | Verifica se o processo está ativo. |

Corpo de login:

```json
{
  "username": "operador",
  "password": "senha-da-conta"
}
```

### Produtos

| Método | Rota | Acesso | Descrição |
| --- | --- | --- | --- |
| `GET` | `/products?q=<termo>` | Operacional ou admin | Lista produtos; busca opcional por nome, marca, número de fábrica ou categoria. |
| `POST` | `/products` | Admin | Cadastra produto. |
| `PUT` | `/products/{product_id}` | Admin | Atualiza produto. |
| `DELETE` | `/products/{product_id}` | Admin | Remove produto. Vendas antigas preservam o registro com vínculo de produto nulo. |

Exemplo de produto:

```json
{
  "nome": "Pastilha",
  "marca": "Bosch",
  "numero_fabrica": "PA-10",
  "categoria": "Freio",
  "quantidade": 12,
  "preco": 25.5
}
```

O status é calculado pelo saldo: zero unidades significa `Esgotado`; quantidade positiva significa `Disponível`.

### Vendas e relatório

| Método | Rota | Acesso | Descrição |
| --- | --- | --- | --- |
| `GET` | `/sales` | Operacional ou admin | Lista o histórico com produto, preço unitário, valor total, data e usuário responsável quando disponíveis. |
| `POST` | `/sales` | Operacional ou admin | Registra uma venda e atualiza o estoque em uma única transação. |
| `GET` | `/reports/sales?data_inicio=AAAA-MM-DD&data_fim=AAAA-MM-DD` | Admin | Retorna totais e vendas filtradas por período; datas são opcionais. |

Corpo de venda:

```json
{
  "produto_id": 1,
  "quantidade": 2
}
```

Uma venda rejeitada por produto inexistente ou saldo insuficiente retorna `409 Conflict` sem alterar estoque nem histórico. Vendas anteriores à auditoria permanecem sem atribuição de usuário/produto quando esses dados não existiam.

### Usuários

| Método | Rota | Acesso | Descrição |
| --- | --- | --- | --- |
| `POST` | `/admin/users` | Admin | Cria conta operacional. |
| `DELETE` | `/admin/users/{username}` | Admin | Remove conta, com as proteções existentes contra apagar a própria conta ou o último administrador. |

## Códigos de resposta relevantes

- `401 Unauthorized`: token ausente, inválido ou expirado; usuário da sessão não existe mais.
- `403 Forbidden`: perfil sem permissão para a operação.
- `404 Not Found`: produto inexistente em atualização/remoção.
- `409 Conflict`: usuário duplicado, operação administrativa não permitida ou venda sem saldo.
- `422 Unprocessable Entity`: corpo inválido, valores fora dos limites ou intervalo de datas inválido.

## Testes

A partir da raiz do projeto:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_api
```

A suíte usa bancos temporários e não deve modificar os dados de produção/desenvolvimento.

## Histórico da API

| Data | Alteração |
| --- | --- |
| 2026-10-23 | Primeira API FastAPI local: login com token, permissões por perfil, produtos, vendas, relatório financeiro e gerenciamento administrativo de usuários. Ainda não publicada na internet. |
| 2026-10-23 | Documentação da API separada do manual do Core para permitir evolução independente dos dois componentes. |
