# AutoPeças

Sistema de gestão de estoque e vendas em evolução para uso desktop e acesso futuro por API/web.

## Componentes e documentação

- **Core desktop (Tkinter):** cadastro e manutenção de produtos, consulta de estoque, registro de vendas, relatórios financeiros, usuários e persistência SQLite. Manual de telas e histórico: [documentacao_core.docx](documentacao_core.docx).
- **API HTTP (FastAPI):** serviço separado para autenticação e acesso por clientes web/móveis. Endpoints, perfis, configuração local e histórico: [docs/api.md](docs/api.md).

Cada componente mantém sua documentação e histórico de alterações próprios. Este README é o ponto de entrada e reúne apenas instruções compartilhadas.
O antigo manual unificado foi preservado como [documentacao_telas_autopecas_legado.docx](documentacao_telas_autopecas_legado.docx); use os documentos acima para a referência atual.

## Requisitos e execução do Core

Python 3.14 ou compatível com as dependências do projeto. O Core usa Tkinter, SQLite local e arquivos JSON legados apenas como origem da migração inicial.

```powershell
.venv\Scripts\python.exe main.py
```

O banco `autopecas.db` é criado na pasta do projeto. Na primeira inicialização, dados válidos dos JSON legados são importados uma única vez; os arquivos originais são preservados como backup.

## Dependências da API

Instale dependências a partir da raiz do repositório:

```powershell
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

A API também pode ser executada em produção como aplicação web. Para isso, use variáveis de ambiente e um serviço de hospedagem online. Consulte [docs/api.md](docs/api.md) para execução, configuração, endpoints, permissões e requisitos antes de hospedagem.

## Deploy em nuvem (recomendado para acesso do celular)

Quando os usuários não estão na mesma rede, a solução correta é publicar o app em um serviço web. O fluxo mais simples é:

1. subir o backend em um provedor como Render ou Railway;
2. configurar uma variável `AUTOPECAS_TOKEN_SECRET` forte;
3. manter o banco em SQLite para teste ou migrar para PostgreSQL em produção;
4. enviar a URL pública para o usuário acessar pelo navegador do celular.

Exemplo de variáveis para ambiente:

```bash
AUTOPECAS_DATABASE=autopecas.db
AUTOPECAS_TOKEN_SECRET=sua-chave-secreta-forte
PORT=8000
```

Para deploy em Render, a configuração mais simples do serviço é usar o comando:

```bash
gunicorn api:app --workers 2 --bind 0.0.0.0:$PORT
```

O arquivo `Procfile` do projeto já usa esse comando para facilitar o deploy.

## Regras compartilhadas

- Estoque é controlado por unidades; zero unidades significa `Esgotado`, e quantidade positiva significa `Disponível`.
- Operadores consultam estoque e registram vendas; administradores também mantêm produtos, consultam relatórios financeiros e gerenciam usuários.
- O registro da venda e a redução do estoque acontecem na mesma transação.
- Vendas novas registram produto, preço unitário praticado e usuário responsável. Dados antigos sem esses vínculos não recebem atribuições inventadas.

## Testes

Execute toda a suíte:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py"
```

Testes específicos da API:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_api
```

## Atualizar documentação do Core

Para regenerar as capturas e o manual do Core:

```powershell
.venv\Scripts\python.exe screenshots_telas.py
.venv\Scripts\python.exe gerar_documentacao_telas.py
```

A documentação da API é mantida diretamente em `docs/api.md`.
