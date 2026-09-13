# Relatório Técnico — SeguraMente

**Sistema Multi-Agentes de Comunicação Preventiva**

Versão 3.0.0 | Desafio 5 InsurMinds

---

## Sumário

1. [Arquitetura da Solução](#1-arquitetura-da-solução)
2. [Descrição dos Agentes](#2-descrição-dos-agentes)
3. [Tecnologias Utilizadas](#3-tecnologias-utilizadas)
4. [Fluxo de Processamento](#4-fluxo-de-processamento)
5. [Regras de Negócio](#5-regras-de-negócio)
6. [Exemplos de Mensagens Geradas](#6-exemplos-de-mensagens-geradas)
7. [Persistência de Dados](#7-persistência-de-dados)
8. [Como Executar](#8-como-executar)

---

## 1. Arquitetura da Solução

### 1.1 Visão Geral

O SeguraMente é um sistema multi-agente que monitora condições meteorológicas, classifica eventos de risco, verifica elegibilidade de segurados, gera mensagens preventivas personalizadas via LLM e envia notificações por email com template HTML profissional.

### 1.2 Diagrama de Alto Nível

```
┌─────────────────────────────────────────────────────────────┐
│                    INTERFACES DE ENTRADA                     │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │  Streamlit    │  │   Webhook    │  │  Monitoramento   │   │
│  │  Dashboard    │  │   FastAPI    │  │  Multi-Cidade    │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         │                 │                    │              │
│         └─────────────────┼────────────────────┘              │
│                           ▼                                   │
│              ┌────────────────────────┐                       │
│              │   SUPERVISOR AGENT     │                       │
│              │   (LangGraph StateGraph)│                       │
│              └───────────┬────────────┘                       │
│                          │                                    │
│    ┌─────────────────────┼─────────────────────┐              │
│    ▼                     ▼                     ▼              │
│ ┌──────────┐      ┌──────────┐          ┌──────────┐         │
│ │Weather   │      │  Event   │          │Eligibility│         │
│ │Agent     │─────▶│  Agent   │─────────▶│  Agent    │         │
│ └──────────┘      └──────────┘          └──────────┘         │
│                                              │                │
│    ┌─────────────────────────────────────────┘                │
│    ▼                                                          │
│ ┌──────────┐      ┌──────────────┐                            │
│ │ Message  │─────▶│ Notification │                            │
│ │ Agent    │      │    Agent     │                            │
│ └──────────┘      └──────────────┘                            │
│                                              │                │
│                   ┌──────────────────────────┘                │
│                   ▼                                           │
│         ┌─────────────────┐     ┌─────────────────┐          │
│         │   SQLite DB     │     │   LLM Providers  │          │
│         │  (profiles,     │     │ OpenAI / Gemini  │          │
│         │   logs, sims)   │     │    / Template     │          │
│         └─────────────────┘     └─────────────────┘          │
└─────────────────────────────────────────────────────────────┘
```

### 1.3 Princípios Arquiteturais

- **Tools como Funções Puras**: Cada tool LangGraph (`@tool`) é uma função sem efeitos colaterais. Logging e persistência ficam a cargo do Supervisor.
- **Supervisor Orquestrador**: O agente supervisor coordena a execução sequencial dos 5 agentes especializados via LangGraph `StateGraph`.
- **Dois Caminhos de Execução**: `run_pipeline()` via grafo compilado (dados ao vivo) e `run_pipeline_from_observation()` via chamadas diretas (fixtures demonstrativos).
- **Human-in-the-Loop**: O envio real de email requer aprovação explícita (`approved=True`). O padrão é sempre simulação.
- **Multi-Provider LLM**: Troca transparente entre OpenAI, APIs compatíveis, Google Gemini e templates offline via variável de ambiente.

---

## 2. Descrição dos Agentes

O sistema é composto por 5 agentes especializados, cada um responsável por uma etapa do pipeline. Os agentes são wrappers organizacionais; a lógica reside nas tools LangGraph em `seguramente/tools/`.

### 2.1 Coletor Meteorológico

| Campo | Valor |
|---|---|
| **Arquivo** | `seguramente/tools/weather_tool.py` |
| **Tools** | `fetch_weather_data`, `fetch_weather_from_observation` |
| **Entrada** | Nome de localidade ou JSON de observação pré-definida |
| **Saída** | `WeatherObservation` (fonte, localização, lat/lon, temperatura, precipitação, vento, código WMO) |
| **API** | Open-Meteo (gratuita, sem chave de API) |

O agente consulta a API de geocodificação para resolver o nome da cidade em coordenadas, depois busca os dados meteorológicos atuais (temperatura, precipitação, velocidade do vento, rajadas, código WMO e probabilidade de precipitação horária).

### 2.2 Analista de Eventos

| Campo | Valor |
|---|---|
| **Arquivo** | `seguramente/tools/event_tool.py` |
| **Tool** | `classify_weather_event` |
| **Entrada** | JSON da `WeatherObservation` |
| **Saída** | `WeatherEvent` (tipo, severidade, relevância, justificativa, indicadores) |

Classifica o evento meteorológico usando limiares determinísticos. Prioridade: Granizo > Alagamento > Ventos Fortes > Chuva Intensa.

### 2.3 Verificador de Elegibilidade

| Campo | Valor |
|---|---|
| **Arquivo** | `seguramente/tools/eligibility_tool.py` |
| **Tool** | `check_insured_eligibility` |
| **Entrada** | JSON do evento, JSON dos perfis, localidade do evento |
| **Saída** | Lista de decisões (perfil, status "elegivel"/"bloqueado", motivos) |

Aplica 6 regras de negócio para determinar quais segurados devem receber notificação: relevância do evento, consentimento ativo, canal suportado, compatibilidade produto-evento, contato válido e correspondência geográfica.

### 2.4 Gerador de Mensagens

| Campo | Valor |
|---|---|
| **Arquivo** | `seguramente/tools/message_tool.py` |
| **Tool** | `generate_preventive_message` |
| **Entrada** | JSON do evento, JSON do perfil |
| **Saída** | `GeneratedMessage` (perfil, canal, destinatário, texto, provedor, modelo, timestamp) |

Gera mensagens preventivas personalizadas usando o LLM configurado. Inclui validação de guardrails (proibição de promessas de cobertura, solicitação de senhas) e limite de 500 caracteres.

### 2.5 Notificador

| Campo | Valor |
|---|---|
| **Arquivo** | `seguramente/tools/notification_tool.py` |
| **Tools** | `simulate_notification`, `send_email_notification` |
| **Entrada** | JSON da mensagem gerada |
| **Saída** | `SimulationRecord` (ID, perfil, canal, destinatário, texto, status, timestamp) |

Duas modalidades:
- **Simulação**: Registra no banco sem enviar nada. Status: "SIMULADO".
- **Email real**: Conecta via SMTP com STARTTLS, envia email HTML multipart (plain text + HTML) com template profissional, headers anti-spam (List-Unsubscribe, Precedence: bulk) e tratamento gracioso de falhas SMTP.

---

## 3. Tecnologias Utilizadas

### 3.1 Dependências Principais

| Dependência | Versão | Finalidade |
|---|---|---|
| LangGraph | >= 0.4.0 | Orquestração de agentes via StateGraph |
| LangChain | >= 0.3.0 | Framework core para LLMs e tools |
| LangChain OpenAI | >= 0.3.0 | Integração com OpenAI |
| LangChain Google GenAI | >= 2.0.0 | Integração com Google Gemini |
| Streamlit | >= 1.36 | Dashboard web interativo |
| FastAPI | >= 0.115.0 | API REST para webhooks |
| Uvicorn | >= 0.30.0 | Servidor ASGI para FastAPI |
| SQLAlchemy | >= 2.0 | ORM para SQLite |
| Python Dotenv | >= 1.0 | Carregamento de variáveis de ambiente |
| Requests | >= 2.31 | Cliente HTTP para APIs externas |
| Pydantic | >= 2.0 | Validação de request/response (FastAPI) |
| Pandas | >= 2.2 | Manipulação de dados no Streamlit |
| Pytest | >= 8.0 | Framework de testes |

### 3.2 APIs Externas

| API | Uso | Chave Necessária |
|---|---|---|
| Open-Meteo Forecast | Dados meteorológicos atuais | Não |
| Open-Meteo Geocoding | Geolocalização de cidades | Não |
| OpenAI API | Geração de mensagens (opcional) | Sim |
| Google Gemini API | Geração de mensagens (opcional) | Sim |
| SMTP (Gmail) | Envio real de emails (opcional) | Sim (App Password) |

### 3.3 Providers LLM Suportados

| Provider | Variável `LLM_PROVIDER` | Modelo Padrão |
|---|---|---|
| Template Offline | `template` | `guardrail-template-v1` |
| OpenAI | `openai` | `gpt-4.1-mini` |
| OpenAI-Compatible | `openai-compatible` | Configurável |
| Google Gemini | `gemini` | `gemini-3.1-flash-lite` |

---

## 4. Fluxo de Processamento

### 4.1 Pipeline Principal

O pipeline executa 5 etapas sequenciais. Cada etapa pode abortar o fluxo em caso de erro ou dados insuficientes.

```
┌─────────────┐    ┌─────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐
│  1. Weather  │───▶│  2. Event   │───▶│ 3. Eligibility│───▶│ 4. Message  │───▶│5. Notification│
│             │    │             │    │              │    │             │    │              │
│ Busca dados │    │ Classifica  │    │ Verifica     │    │ Gera texto  │    │ Simula ou    │
│ meteorológ. │    │ o evento    │    │ elegibilidade│    │ via LLM     │    │ envia email  │
└─────────────┘    └─────────────┘    └──────────────┘    └─────────────┘    └──────────────┘
```

### 4.2 Detalhamento por Etapa

#### Etapa 1 — Coletor Meteorológico

- **Entrada**: Nome da localidade (ex: "São Paulo") ou observação pré-definida (fixture)
- **Processo**: Geocodificação via Open-Meteo → busca de forecast atual
- **Saída**: `observation_data` com temperatura, precipitação, vento, rajadas, código WMO
- **Aborte**: Se localidade não encontrada ou API indisponível

#### Etapa 2 — Analista de Eventos

- **Entrada**: `observation_data` da etapa anterior
- **Processo**: Aplicação de limiares determinísticos (código WMO, mm de precipitação, km/h de rajada)
- **Saída**: `event_data` com tipo, severidade, relevância e justificativa
- **Aborte**: Se nenhum indicador ultrapassar os limiares (evento irrelevante)

#### Etapa 3 — Verificador de Elegibilidade

- **Entrada**: `event_data` + lista de perfis do banco + localidade do evento
- **Processo**: Verificação de 6 regras por perfil (relevância, consentimento, canal, produto, contato, geolocalização)
- **Saída**: `eligibility_data` com decisões "elegivel" ou "bloqueado" e motivos
- **Aborte**: Se nenhum perfil for elegível

#### Etapa 4 — Gerador de Mensagens

- **Entrada**: `event_data` + apenas perfis elegíveis
- **Processo**: Para cada perfil elegível, chama o LLM com system prompt + dados do evento e perfil
- **Saída**: `messages_data` com mensagens personalizadas por perfil
- **Guardrails**: Validação de comprimento (≤500 chars) e padrões proibidos

#### Etapa 5 — Notificador

- **Entrada**: `messages_data` + flag `approved`
- **Processo**: Se `approved=True`, envia email real via SMTP; senão, apenas simula
- **Saída**: `simulations_data` com registros de envio/simulação
- **Fallback**: Falhas SMTP resultam em simulação (não trava o pipeline)

### 4.3 Execução Multi-Cidade (Monitoramento)

O `run_monitor()` itera sobre todas as cidades distintas dos segurados ativos no banco, executando o pipeline completo para cada uma. Retorna um resumo agregado com: cidades escaneadas, alertas acionados e emails enviados.

### 4.4 Observabilidade

Cada execução gera um `run_id` único (ex: `RUN-FB30DC43C623`). Os logs de cada agente são persistidos no banco com:
- Nome do agente e ação executada
- Resumo de entrada e saída
- Status (started/completed/error)
- Timestamps de início e fim
- Duração em milissegundos
- Dados brutos (raw_input, raw_output)
- Provedor e modelo LLM utilizado

---

## 5. Regras de Negócio

### 5.1 Classificação de Eventos

| Evento | Condição | Severidade | Código WMO |
|---|---|---|---|
| Granizo | `weather_code in {96, 99}` | Alta | 96 ou 99 |
| Alagamento | `precipitação ≥ 30 mm` | Crítica | — |
| Ventos Fortes | `rajada ≥ 60 km/h` | Alta | — |
| Chuva Intensa | `precipitação ≥ 10 mm` OU `probabilidade ≥ 70%` | Moderada | — |

### 5.2 Mapeamento Produto × Evento

| Evento | Produtos Elegíveis |
|---|---|
| Chuva Intensa | Residencial, Empresarial |
| Granizo | Automóvel, Residencial |
| Ventos Fortes | Residencial, Empresarial, Automóvel |
| Alagamento | Residencial, Empresarial |

### 5.3 Regras de Elegibilidade

Um segurado é elegível somente se **todas** as condições forem atendidas:

1. O evento meteorológico é relevante
2. O segurado possui consentimento ativo
3. O canal de comunicação é suportado (email, sms, push)
4. O produto do segurado é compatível com o tipo de evento
5. O contato do segurado está preenchido
6. A cidade do segurado corresponde à localidade do evento

### 5.4 Guardrails LLM

Mensagens geradas são validadas contra padrões proibidos:

- Promessas de cobertura ("cobertura garantida")
- Indenização ("indenização", "indenizaremos", "indenizará")
- Aprovação de sinistro ("sinistro aprovado")
- Solicitação de credenciais ("senha", "token", "credencial", "código de segurança")
- Limite de 500 caracteres

---

## 6. Exemplos de Mensagens Geradas

### 6.1 Template Offline (Sem LLM)

Mensagens determinísticas geradas pelo `TemplateProvider` para o cenário de chuva intensa em São Paulo:

> Olá, Ana. Verifique calhas, ralos e áreas externas e acompanhe os comunicados oficiais diante da previsão de chuva intensa em sua região. Esta é uma orientação preventiva.

> Olá, Bruno. Verifique calhas, ralos e áreas externas e acompanhe os comunicados oficiais diante da previsão de chuva intensa em sua região. Esta é uma orientação preventiva.

**Provedor**: `template-offline` | **Modelo**: `guardrail-template-v1`

### 6.2 Mensagens via OpenAI (GPT-5-mini)

Mensagens personalizadas geradas pelo modelo GPT-5-mini para o mesmo cenário:

**Para Ana (residencial):**

> Olá Ana, há previsão de chuva intensa em São Paulo/SP. Para proteger sua residência, verifique e limpe calhas e ralos, guarde ou prenda objetos soltos na área externa, evite estacionar próximo a árvores ou locais que alagam, mantenha aparelhos eletrônicos e documentos em locais elevados e o celular carregado, e não circule por vias alagadas. Siga as orientações das autoridades locais e mantenha-se em lugar seguro.

**Para Bruno (empresarial):**

> Bruno, em São Paulo/SP há previsão de chuva intensa. Para reduzir riscos ao seu estabelecimento, verifique calhas e ralos, eleve e proteja equipamentos e documentos sensíveis e fixe materiais soltos no exterior. Evite deslocamentos não essenciais, acompanhe as atualizações meteorológicas e registre por foto qualquer dano, se ocorrer.

**Para Diego (residencial, Rio de Janeiro):**

> Diego, há previsão de chuva intensa no Rio de Janeiro/RJ. Para reduzir riscos em sua residência: verifique e limpe calhas e ralos, afaste ou prenda objetos soltos na área externa, proteja equipamentos elétricos elevando-os quando possível, evite transitar por áreas alagadas e mantenha-se atento às orientações dos órgãos oficiais. Priorize a segurança da sua família.

**Provedor**: `openai-compatible` | **Modelo**: `gpt-5-mini`

### 6.3 Comparação: Template vs. LLM

| Aspecto | Template Offline | LLM (GPT-5-mini) |
|---|---|---|
| Personalização | Genérica por evento | Personalizada por perfil e localidade |
| Tom | Padrão corporativo | Adaptativo (residencial vs. empresarial) |
| Ação específica | Verificação de calhas | Dicas contextualizadas por produto |
| Velocidade | Instantâneo | ~10-30 segundos por mensagem |
| Custo | Zero | Variável por provider |

### 6.4 Template de Email HTML

O sistema gera emails HTML profissionais com:

- **Cabeçalho**: Fundo azul escuro (#1a5276) com marca "SEGURAMENTE SEGUROS"
- **Banner de aviso**: Fundo laranja (#f39c12) com texto "AVISO DE TESTE"
- **Corpo**: Texto formatado com nome do destinatário
- **Rodapé**: Dados da empresa (endereço, CNPJ, telefone, site)
- **Anti-spam**: Headers `List-Unsubscribe`, `Precedence: bulk`, `X-Mailer`
- **Descadastro**: Link para `nao-responda@seguramenteseguros.com.br`

---

## 7. Persistência de Dados

### 7.1 Banco de Dados

**Engine**: SQLite com WAL journal mode  
**ORM**: SQLAlchemy declarative base  
**Caminho padrão**: `data/seguramente.db`

### 7.2 Tabelas

#### `insured_profiles`

| Coluna | Tipo | Restrição |
|---|---|---|
| `profile_id` | String | PRIMARY KEY |
| `name` | String | NOT NULL |
| `city` | String | NOT NULL |
| `state` | String | NOT NULL |
| `product` | String | NOT NULL |
| `channel` | String | NOT NULL |
| `consent` | Boolean | NOT NULL |
| `contact` | String | NOT NULL |

#### `simulation_records`

| Coluna | Tipo | Restrição |
|---|---|---|
| `id` | Integer | PRIMARY KEY, AUTOINCREMENT |
| `simulation_id` | String | NOT NULL |
| `profile_id` | String | NOT NULL |
| `channel` | String | NOT NULL |
| `recipient` | String | NOT NULL |
| `text` | Text | NOT NULL |
| `status` | String | NOT NULL |
| `created_at` | String | NOT NULL |

#### `agent_logs`

| Coluna | Tipo | Restrição |
|---|---|---|
| `id` | Integer | PRIMARY KEY, AUTOINCREMENT |
| `run_id` | String | NOT NULL, INDEXED |
| `agent_name` | String | NOT NULL |
| `action` | String | NOT NULL |
| `input_summary` | Text | nullable |
| `output_summary` | Text | nullable |
| `status` | String | NOT NULL |
| `started_at` | String | NOT NULL |
| `completed_at` | String | nullable |
| `duration_ms` | Float | nullable |
| `raw_input` | Text | nullable |
| `raw_output` | Text | nullable |
| `llm_provider` | String | nullable |
| `llm_model` | String | nullable |
| `location` | String | nullable |

### 7.3 Dados Iniciais (Seed)

21 perfis sintéticos distribuídos em 5 cidades brasileiras:

| Cidade | Clientes | Produtos |
|---|---|---|
| São Paulo, SP | Eliezer (4), Mariana B. (2), Ana, Carlos, Mariana | residencial, automovel, empresarial, vida |
| Rio de Janeiro, RJ | Adelson (2), Bruno | residencial, empresarial |
| Salvador, BA | Daniel (2), Luiza (consentimento inativo) | automovel, vida, residencial |
| Porto Alegre, RS | Denis (2), Diego | residencial, vida |
| São Joaquim, SC | Sami (2), Renata | empresarial, automovel, vida |

### 7.4 Fixtures Demonstrativos

| Cenário | Cidade | Evento | Precipitação | Rajada | Código WMO |
|---|---|---|---|---|---|
| `chuva_intensa_sp` | São Paulo | Chuva intensa | 18,0 mm | 34 km/h | 63 |
| `granizo_rj` | Rio de Janeiro | Granizo | 12,0 mm | 55 km/h | 96 |
| `ventos_fortes_ba` | Salvador | Ventos fortes | 2,0 mm | 78 km/h | 3 |
| `alagamento_rs` | Porto Alegre | Alagamento | 38,0 mm | 28 km/h | 65 |
| `granizo_sc` | São Joaquim, SC | Granizo | 8,0 mm | 48 km/h | 96 |

---

## 8. Como Executar

### 8.1 Pré-requisitos

- Python >= 3.12
- pip

### 8.2 Instalação

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 8.3 Configuração

```bash
cp .env.example .env
# Edite .env com suas chaves de API (opcional para modo offline)
```

### 8.4 População do Banco

```bash
python scripts/seed_db.py
```

### 8.5 Execução

**Dashboard Streamlit:**
```bash
streamlit run app.py
```

**Webhook FastAPI:**
```bash
uvicorn webhook:app --host 0.0.0.0 --port 8000
```

**Demo CLI:**
```bash
python scripts/run_demo.py
```

### 8.6 Testes

```bash
pytest -v
```

### 8.7 Endpoints Webhook

| Método | Rota | Descrição |
|---|---|---|
| GET | `/webhook/health` | Health check |
| POST | `/webhook/alert` | Dispara pipeline com localização |
| POST | `/webhook/fixture` | Dispara pipeline com cenário fixture |
| GET | `/webhook/runs/{run_id}` | Logs de execução por run_id |
| GET | `/webhook/runs` | Lista execuções recentes |
| POST | `/webhook/monitor` | Monitora todas as cidades |

---

*Documento gerado automaticamente — SeguraMente v3.0.0*
