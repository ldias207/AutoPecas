# AutoPeças

Sistema web-first para gestão de estoque, vendas e financeiro com controle de acesso por perfil de usuário.

## Visão geral

A aplicação principal agora é a versão web via FastAPI. O navegador é a interface oficial para vendedor e administrador, e o acesso aos módulos é controlado por permissões do usuário.

- **Web app principal:** consulta de estoque, registro de vendas, relatórios financeiros, cadastro de produtos para admin e controle de usuários.
- **Tkinter:** mantido apenas como legado ou ferramenta auxiliar; não é a interface principal de uso.
- **Banco de dados:** SQLite em ambiente local/teste e preparação para PostgreSQL em produção.

## Arquitetura atual

- **API:** [api.py](api.py)
- **Autenticação e permissões:** [auth.py](auth.py)
- **Persistência e regras de negócio:** [database.py](database.py)
- **Frontend web:** [static/index.html](static/index.html)
- **Documentação da API:** [docs/api.md](docs/api.md)

## Fluxo de acesso por perfil

- **Administrador:** pode acessar vendas, financeiro e cadastro de produtos.
- **Operador/Vendedor:** pode consultar estoque e registrar vendas.

As permissões são validadas no backend e também refletidas na navegação do front-end.

## Requisitos e execução local

Instale as dependências:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Inicie a aplicação web:

```powershell
.venv\Scripts\python.exe -m uvicorn api:app --host 127.0.0.1 --port 8000
```

Acesse:

```text
http://127.0.0.1:8000/
```

## Deploy em nuvem

Para acesso externo, a aplicação deve ser hospedada em um serviço web, como Render ou Railway. A configuração recomendada é:

1. usar a API FastAPI como aplicação principal;
2. definir `AUTOPECAS_TOKEN_SECRET`;
3. configurar a variável `PORT`;
4. manter a URL pública do app para acesso do celular/usuários remotos.

Exemplo de variáveis de ambiente:

```bash
AUTOPECAS_DATABASE=autopecas.db
AUTOPECAS_TOKEN_SECRET=sua-chave-secreta-forte
PORT=8000
```

Para deploy do Render, o comando mais simples é:

```bash
uvicorn api:app --host 0.0.0.0 --port $PORT
```

## Regras compartilhadas

- Estoque é controlado por unidades; zero unidades significa `Esgotado`, e quantidade positiva significa `Disponível`.
- Operadores consultam estoque e registram vendas; administradores também mantêm produtos, consultam relatórios financeiros e gerenciam usuários.
- O registro da venda e a redução do estoque acontecem na mesma transação.
- Vendas novas registram produto, preço unitário praticado e usuário responsável.

## Testes

Execute a suíte relevante:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_api tests.test_database
```

Ou a suíte completa:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

## Observação sobre o Tkinter

A interface desktop do Tkinter foi mantida apenas como base histórica/auxiliar. O sistema principal e o fluxo de uso real passam a ser o web, com acessos e permissões centralizados no backend.
