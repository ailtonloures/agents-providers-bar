# GEMINI.md

Instruções de contexto e padrões do projeto **Agents Providers Usage Bar** para o agente Antigravity.

## Visão Geral do Projeto

Monitor de cotas de assinatura para **Claude Code** e **Antigravity (Google AI)** composto por:
- **Backend Python (`backend/agents_usage/`)**: CLI `agents-usage` que consulta os provedores em paralelo, aplica cache local em `~/.cache/agents-providers-bar/usage.json` e retorna dados normalizados em texto ou JSON.
- **Extensão GNOME Shell 46 (`extension/agents-providers-bar@ailton.local/`)**: indicador na barra superior escrito em GJS (ESM) que invoca `agents-usage --json` via `Gio.Subprocess` e exibe cards de uso em um popup.

## Arquitetura e Arquivos-Chave

- `pyproject.toml`: empacotamento do pacote `agents_usage` (a partir de `backend/`), script `agents-usage = "agents_usage.cli:main"`, Python `>= 3.10`, **sem dependências externas**.
- `backend/agents_usage/models.py`: `QuotaWindow`, `ProviderUsage`, `UsageReport` e `format_reset_in`.
- `backend/agents_usage/cache.py`: `UsageCache` (TTL padrão `300s`, escrita atômica via `.tmp` + `os.replace`).
- `backend/agents_usage/cli.py`: `collect_provider`, `build_report`, `main`. Em `rate_limited` ou `error`, faz fallback para cache *stale* se houver janelas salvas.
- `backend/agents_usage/providers/claude.py`: lê `~/.claude/.credentials.json` e consulta `https://api.anthropic.com/api/oauth/usage`.
- `backend/agents_usage/providers/antigravity.py`: descobre hubs em `~/.gemini/antigravity/daemon/hub_*.json` (priorizando PIDs vivos) e consulta `GetUserStatus` via HTTP local.
- `extension/agents-providers-bar@ailton.local/extension.js`: UI GJS (`AgentsUsageIndicator`), timer de 300s e renderização dos cards.
- `scripts/install.sh` e `scripts/uninstall.sh`: instalação/remoção do wrapper `~/.local/bin/agents-usage` e do symlink da extensão GNOME.

## Comandos Principais

- **Validar tudo (lint + testes)**: `make check`
- **Testes unitários**: `make test` (ou `PYTHONPATH=backend python3 -m unittest discover -s backend/tests -v`)
- **Lint da extensão**: `make lint` (`node --check` em `extension.js` + `json.tool` em `metadata.json`)
- **Executar CLI**: `make run` ou `make json`
- **Instalar / Desinstalar**: `make install` / `make uninstall`

## Convenções e Regras de Desenvolvimento

1. **Zero dependências externas no backend**: mantenha `dependencies = []` em `pyproject.toml`. Use apenas a biblioteca padrão do Python.
2. **Tratamento de erros nos provedores**: funções `fetch_*_usage` não devem propagar exceções não tratadas para a CLI/UI; retorne `ProviderUsage` com `status` apropriado (`"ok"`, `"rate_limited"`, `"unauthenticated"`, `"unavailable"` ou `"error"`) e `error_message` descritiva.
3. **Testabilidade**: mantenha injeção de dependência simples nos coletores (`credentials_path`/`daemon_dir`, `http_get`/`http_post`) para que `backend/tests/` continue rodando isolado sem rede ou daemon real.
4. **Compatibilidade GNOME Shell 46**: `extension.js` deve usar imports ESM (`import ... from 'gi://...'` e `resource:///org/gnome/shell/...`) e permanecer compatível com `node --check`.
5. **Verificação obrigatória**: após qualquer alteração no código Python ou na extensão, execute `make check` antes de concluir.
