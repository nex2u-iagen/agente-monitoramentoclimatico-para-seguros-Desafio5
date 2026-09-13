# SeguraMente

## Sistema Multi-Agentes para Comunicação Preventiva com Segurados

MVP desenvolvido para o **Desafio 5 — InsurMinds**. Solução baseada em uma arquitetura multi-agentes com LangGraph que monitora dados meteorológicos, classifica eventos relevantes, aplica regras de elegibilidade, gera mensagens preventivas com IA e registra simulações de envio.

> **Nota:** O MVP não envia SMS, e-mail, WhatsApp ou notificações push. Todos os perfis são sintéticos e toda comunicação passa por revisão humana antes do registro da simulação.

---

## Arquitetura Multi-Agentes

```text
┌─────────────────────────────────────────────────────────────────┐
│                    SUPERVISOR AGENT                             │
│  Orquestra o pipeline completo via LangGraph StateGraph         │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐    ┌───────────────┐    ┌───────────────┐
│ Weather Agent │    │  Event Agent  │    │Eligibility Agt│
│  (coleta dados │    │ (classifica   │    │(verifica      │
│   meteorológ.) │    │  eventos)     │    │ elegibilidade)│
└───────────────┘    └───────────────┘    └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │  Message Agent    │
                    │ (gera mensagens)  │
                    └───────────────────┘
                              │
                              ▼
                    ┌───────────────────┐
                    │ Notification Agent│
                    │(simula/envia)     │
                    └───────────────────┘
```

### Componentes

| Agente | Responsabilidade | Tool(s) |
|--------|-----------------|---------|
| **Supervisor** | Orquestra pipeline completo, coordena agentes | — |
| **Weather Agent** | Coleta dados meteorológicos via Open-Meteo | `fetch_weather_data`, `fetch_weather_from_observation` |
| **Event Agent** | Classifica eventos climáticos por limiares | `classify_weather_event` |
| **Eligibility Agent** | Verifica elegibilidade dos segurados | `check_insured_eligibility` |
| **Message Agent** | Gera mensagens preventivas com LLM | `generate_preventive_message` |
| **Notification Agent** | Simula envio ou envia email real | `simulate_notification`, `send_email_notification` |

---

## Tools LangGraph

Cada tool é uma função decorada com `@tool` do LangChain, separada em módulos independentes:

```text
seguramente/tools/
├── __init__.py          # Exporta todas as tools
├── weather_tool.py      # fetch_weather_data, fetch_weather_from_observation
├── event_tool.py        # classify_weather_event
├── eligibility_tool.py  # check_insured_eligibility
├── message_tool.py      # generate_preventive_message
└── notification_tool.py # simulate_notification, send_email_notification
```

---

## Provedores LLM

Suporte múltiplos provedores via variável de ambiente `LLM_PROVIDER`:

| Provedor | Variável | Uso |
|----------|----------|-----|
| `openai` | `OPENAI_API_KEY` | Produção com modelos OpenAI |
| `openai-compatible` | `OPENAI_API_KEY` + `OPENAI_API_BASE` | APIs compatíveis (Ollama, etc.) |
| `gemini` | `GEMINI_API_KEY` | Google Gemini |
| `template` | (nenhuma) | Fallback offline para testes |

---

## Banco de Dados SQLite

O sistema usa SQLite como fonte primaria de dados (`data/seguramente.db`):

- **insured_profiles** — Perfis dos segurados (multi-produto por usuario)
- **simulation_records** — Registros de simulacoes/envios
- **agent_logs** — Logs detalhados de execucao de cada agente

### Setup inicial

```bash
python scripts/seed_db.py --reset    # popula o banco a partir do CSV
python scripts/seed_db.py            # adiciona novos registros (idempotente)
```

O CSV (`data/insured_profiles.csv`) e usado apenas como fonte inicial para popular o banco.
Apos o primeiro seed, o SQLite e a unica fonte de verdade.

---

## Webhook (FastAPI)

Endpoint para receber alertas externos de APIs de monitoramento meteorológico:

```bash
uvicorn webhook:app --host 0.0.0.0 --port 8000
```

| Endpoint | Método | Descrição |
|----------|--------|-----------|
| `/webhook/alert` | POST | Executa pipeline com localidade |
| `/webhook/fixture` | POST | Executa com cenário fixture pré-definido |
| `/webhook/health` | GET | Health check |
| `/webhook/runs` | GET | Lista últimas execuções |
| `/webhook/runs/{run_id}` | GET | Consulta logs de uma execução |

---

## Interface Streamlit

Dashboard com status em tempo real de cada agente:

```bash
streamlit run app.py
```

Funcionalidades:
- Status de execução de cada agente em tempo real
- Seleção de cenários reproduzíveis ou localidade real
- Escolha do provedor LLM
- Visualização de mensagens geradas
- Registro de simulações

---

## Regras e Limiares

| Evento | Regra | Severidade |
|--------|-------|------------|
| Granizo | Código meteorológico WMO 96 ou 99 | Alta |
| Alagamento | Precipitação atual ≥ 30 mm | Crítica |
| Ventos fortes | Rajada ≥ 60 km/h | Alta |
| Chuva intensa | Precipitação ≥ 10 mm ou probabilidade ≥ 70% | Moderada |
| Sem evento | Nenhum limiar atingido | Baixa |

### Requisitos de Elegibilidade

1. **Consentimento** — Segurado deve ter consentimento ativo
2. **Contato** — Deve possuir email válido cadastrado
3. **Produto** — Produto deve ter relação com o evento climático
4. **Canal** — Canal de notificação deve ser compatível
5. **Status** — Segurado deve estar ativo

Documentação completa: `docs/Regras_Elegibilidade_Requisitos.md`

---

## Requisitos

- Python 3.11 ou superior
- Chave de API OpenAI/Gemini (opcional para modo template)
- Credenciais SMTP (opcional para envio real)

## Instalacao

```bash
git clone <URL_DO_REPOSITORIO>
cd SeguraMente_Desafio5_Entrega
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python scripts/seed_db.py --reset    # popula o banco SQLite
```

## Configuração

Edite `.env` com suas credenciais:

```bash
# Provedor LLM (openai, openai-compatible, gemini, template)
LLM_PROVIDER=template

# OpenAI (opcional)
OPENAI_API_KEY=sua-chave-aqui
OPENAI_API_BASE=https://api.openai.com/v1
SEGURAMENTE_LLM_MODEL=gpt-4o-mini

# Gemini (opcional)
GEMINI_API_KEY=sua-chave-aqui

# SMTP para envio real (opcional)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=seu-email@gmail.com
SMTP_PASSWORD=sua-senha-de-app
SMTP_FROM=seu-email@gmail.com
```

## Execução

### Interface Streamlit
```bash
streamlit run app.py
```

### Webhook FastAPI
```bash
uvicorn webhook:app --host 0.0.0.0 --port 8000
```

### Demonstração CLI
```bash
# Modo offline (template)
python scripts/run_demo.py --scenario chuva_intensa --provider template --simulate --output evidence/demo_run_offline.json

# Modo com LLM
python scripts/run_demo.py --scenario chuva_intensa --provider openai --simulate --output evidence/demo_run_openai.json
```

## Testes

```bash
pytest -v
```

14 testes cobrindo:
- Classificação de eventos meteorológicos
- Verificação de elegibilidade
- Geração de mensagens com guardrails
- Simulação de notificações
- Pipeline completo via supervisor
- Persistência no banco de dados

## Estrutura do Projeto

```text
.
├── app.py                          # Interface Streamlit
├── webhook.py                      # API FastAPI webhook
├── fixtures.py                     # Cenarios fixture
├── data/
│   ├── insured_profiles.csv        # Fonte inicial de perfis
│   └── seguramente.db              # Banco SQLite (fonte primaria)
├── docs/
│   ├── Documentacao_Tecnica_Desafio_5_SeguraMente.pdf
│   └── Regras_Elegibilidade_Requisitos.md
├── evidence/                       # Evidencias de execucao
├── scripts/
│   ├── seed_db.py                  # Popula o banco SQLite
│   └── run_demo.py                 # Demo CLI
├── seguramente/
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py                 # AgentError, SeguraMenteState
│   │   ├── supervisor.py           # Orquestrador principal
│   │   ├── weather_agent.py
│   │   ├── event_agent.py
│   │   ├── eligibility_agent.py
│   │   ├── message_agent.py
│   │   └── notification_agent.py
│   ├── tools/
│   │   ├── __init__.py
│   │   ├── weather_tool.py
│   │   ├── event_tool.py
│   │   ├── eligibility_tool.py
│   │   ├── message_tool.py
│   │   └── notification_tool.py
│   ├── database.py                 # SQLite ORM
│   ├── llm_engine.py               # Multi-provider LLM
│   ├── llm.py                      # Provider classes
│   ├── models.py                   # Dataclasses
│   └── __init__.py
├── tests/
│   └── test_seguramente.py
├── .env.example
├── requirements.txt
├── LICENSE
└── README.md
```

## Dados e Limites

O banco `data/seguramente.db` contem perfis de segurados (sinteticos e para teste).
O sistema nao acessa sistemas de seguradoras, nao processa dados reais, nao decide cobertura, nao calcula indenizacao e nao realiza disparos externos. Esses limites sao intencionais para preservar o escopo didatico do Desafio 5.

## Licença

Este projeto está licenciado sob a **MIT License**. Consulte `LICENSE`.
