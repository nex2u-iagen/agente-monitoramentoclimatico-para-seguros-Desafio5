# SeguraMente — Documentação de Regras de Elegibilidade e Requisitos

**Versão:** 3.0  
**Data:** 13 de setembro de 2026

---

## 1. Regras de Classificação de Eventos Meteorológicos

**Implementação:** `seguramente/rules.py` → `classify_event()`

| Evento | Indicador | Limiar | Severidade | Código WMO |
|---|---|---|---|---|
| **Granizo** | `weather_code` | 96 ou 99 | Alta | 96, 99 |
| **Alagamento** | Precipitação atual | ≥ 30 mm | Crítica | Qualquer |
| **Ventos Fortes** | Rajada | ≥ 60 km/h | Alta | Qualquer |
| **Chuva Intensa** | Precipitação ou probabilidade | ≥ 10 mm ou ≥ 70% | Moderada | Qualquer |
| **Sem Evento Relevante** | Nenhum limiar atingido | — | Baixa | Qualquer |

**Prioridade:** Quando múltiplos limiares são atingidos, a ordem é: Granizo > Alagamento > Ventos Fortes > Chuva Intensa.

---

## 2. Regras de Elegibilidade de Segurados

**Implementação:** `seguramente/rules.py` → `evaluate_eligibility()`

Um segurado é **elegível** para receber alerta preventivo quando **TODAS** as condições abaixo são atendidas:

| # | Regra | Campo | Condição | Motivo de Bloqueio |
|---|---|---|---|---|
| 1 | Evento relevante | `WeatherEvent.relevance` | `True` | "evento abaixo do limiar de relevância" |
| 2 | Consentimento ativo | `InsuredProfile.consent` | `True` | "consentimento inativo" |
| 3 | Canal suportado | `InsuredProfile.channel` | ∈ {email, sms, push} | "canal não suportado" |
| 4 | Produto compatível | `InsuredProfile.product` | ∈ `PRODUCTS_BY_EVENT[event_type]` | "produto sem relação com o evento" |
| 5 | Contato preenchido | `InsuredProfile.contact` | ≠ "" | "contato ausente para o canal selecionado" |

### Mapeamento Evento → Produtos

| Tipo de Evento | Produtos Elegíveis |
|---|---|
| `chuva_intensa` | residencial, empresarial |
| `granizo` | automovel, residencial |
| `ventos_fortes` | residencial, empresarial, automovel |
| `alagamento` | residencial, empresarial |

### Perfis de Exemplo (CSV)

| ID | Nome | Produto | Canal | Consentimento | Status Esperado |
|---|---|---|---|---|---|
| P001 | Ana | residencial | email | true | Elegível (chuva) |
| P002 | Carlos | automovel | sms | true | Bloqueado (produto) |
| P003 | Mariana | residencial | push | true | Elegível (chuva) |
| P004 | Bruno | empresarial | email | true | Elegível (chuva) |
| P005 | Luiza | residencial | email | false | Bloqueado (consentimento) |
| P006 | Diego | residencial | email | true | Bloqueado (localidade) |
| P007 | Renata | vida | email | true | Bloqueado (produto) |

---

## 3. Tools dos Agentes (LangGraph)

Cada agente expõe suas funcionalidades como **tools** LangGraph que podem ser invocadas:

### Weather Agent — `seguramente/agents/weather_agent.py`

| Tool | Descrição | Args |
|---|---|---|
| `fetch_weather_data` | Busca dados meteorológicos via API Open-Meteo | `location: str` |
| `fetch_weather_from_observation` | Processa observação pré-definida (fixture) | `observation_json: str` |

### Event Agent — `seguramente/agents/event_agent.py`

| Tool | Descrição | Args |
|---|---|---|
| `classify_weather_event` | Classifica evento meteorológico | `observation_json: str` |

### Eligibility Agent — `seguramente/agents/eligibility_agent.py`

| Tool | Descrição | Args |
|---|---|---|
| `check_insured_eligibility` | Verifica elegibilidade dos segurados | `event_json: str, profiles_json: str` |

### Message Agent — `seguramente/agents/message_agent.py`

| Tool | Descrição | Args |
|---|---|---|
| `generate_preventive_message` | Gera mensagem personalizada via LLM | `event_json: str, profile_json: str` |

### Notification Agent — `seguramente/agents/notification_agent.py`

| Tool | Descrição | Args | Modo |
|---|---|---|---|
| `simulate_notification` | Simula envio sem acionar canal real | `message_json: str` | Simulado |
| `send_email_notification` | Envia email real via SMTP | `message_json: str` | Real |

---

## 4. Verificação dos Requisitos

### Requisito 1: Consumir dados de uma API de meteorologia

**Status:** IMPLEMENTADO

- **Tool:** `fetch_weather_data` em `seguramente/agents/weather_agent.py`
- **API:** Open-Meteo (gratuita, sem chave)
- **Dados:** temperatura, precipitação, vento, rajadas, código WMO, probabilidade
- **Endpoint:** `https://api.open-meteo.com/v1/forecast`
- **Geocoding:** `https://geocoding-api.open-meteo.com/v1/search`

### Requisito 2: Indicar eventos climáticos relevantes

**Status:** IMPLEMENTADO

- **Tool:** `classify_weather_event` em `seguramente/agents/event_agent.py`
- **Regras:** Limiares documentados em `seguramente/rules.py`
- **Eventos:** granizo, alagamento, ventos fortes, chuva intensa
- **Severidade:** baixa, moderada, alta, crítica
- **Documentação:** Seção 1 deste documento + docstring em `classify_event()`

### Requisito 3: Aplica regras para determinar quais segurados devem receber notificação

**Status:** IMPLEMENTADO

- **Tool:** `check_insured_eligibility` em `seguramente/agents/eligibility_agent.py`
- **Regras:** 5 critérios documentados na Seção 2 deste documento
- **Código:** `seguramente/rules.py` → `evaluate_eligibility()`
- **Documentação:** Este arquivo + docstring na tool

### Requisito 4: Agente gera mensagem personalizada usando chamada de LLM

**Status:** IMPLEMENTADO

- **Tool:** `generate_preventive_message` em `seguramente/agents/message_agent.py`
- **Providers suportados:** OpenAI, OpenAI-compatible, Google Gemini, Template (offline)
- **Guardrails:** Rejeita mensagens com promessas de cobertura, pedidos de senha/token
- **Personalização:** Usa nome, produto, localidade do segurado no prompt

### Requisito 5: Envio real ou simulado das notificações

**Status:** IMPLEMENTADO (ambos os modos)

- **Tool simulada:** `simulate_notification` — registra sem enviar
- **Tool real:** `send_email_notification` — envia email via SMTP
- **Configuração SMTP:** `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`
- **Fallback:** Se SMTP não configurado, usa simulação automaticamente
- **Nota:** Para email real, configure as variáveis de ambiente SMTP no `.env`

### Requisito 6: Fluxo completo disponível para acompanhamento

**Status:** IMPLEMENTADO

- **Dashboard:** Streamlit com status de cada agente em tempo real
- **Logs:** Tabela `agent_logs` no SQLite com timestamps e duração
- **Webhook:** Endpoint FastAPI para disparar e consultar execuções
- **Fluxo visual:** Weather → Event → Eligibility → Message → Notification

---

## 5. Variáveis de Ambiente

```bash
# Provedor LLM (template | openai | openai-compatible | gemini)
LLM_PROVIDER=template

# OpenAI
OPENAI_API_KEY=
OPENAI_API_BASE=https://api.openai.com/v1

# Google Gemini
GEMINI_API_KEY=

# Modelo (opcional, muda por provider)
SEGURAMENTE_LLM_MODEL=

# SMTP (para envio real de email)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=
SMTP_PASSWORD=
SMTP_FROM=
```

---

## 6. Endpoints do Webhook

```bash
# Health check
GET /webhook/health

# Disparar alerta por localidade
POST /webhook/alert
{"location": "São Paulo", "approved": false}

# Disparar com fixture
POST /webhook/fixture
{"scenario": "granizo", "approved": true}

# Consultar logs de uma execução
GET /webhook/runs/{run_id}

# Listar execuções
GET /webhook/runs
```
