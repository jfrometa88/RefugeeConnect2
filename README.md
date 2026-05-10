# RefugeeConnect AI 🌍
### *Bridging the Information Gap for Migrants and Asylum Seekers in Spain*

<p align="center">
  <img src="https://img.shields.io/badge/Gemma_4-Hackathon-blue?style=for-the-badge&logo=google" alt="Gemma 4 Hackathon"/>
  <img src="https://img.shields.io/badge/Track-Digital_Equity_&_Inclusivity-orange?style=for-the-badge" alt="Impact Track"/>
  <img src="https://img.shields.io/badge/Special_Tech-Ollama-green?style=for-the-badge" alt="Ollama Track"/>
  <img src="https://img.shields.io/badge/Status-Functional_MVP-brightgreen?style=for-the-badge" alt="Status"/>
</p>

---

## 🧭 Origin: A Personal Story

I arrived in Spain as a Cuban political asylum seeker — alone, without family or financial support. Despite speaking Spanish and having an engineering background, everything was new to me: the legal framework, the network of NGOs, the bureaucratic procedures for regularization, healthcare, and social assistance.

Over time, I learned to navigate this system. But I witnessed firsthand how much harder it was for others: people with language barriers, without technical knowledge, traveling with minor children, and vulnerable to misinformation spread through informal channels like social media. I watched people fall into traps — paying for legal procedures that were free, not knowing they could register (*empadronarse*) without a fixed address, or simply not finding the right help because they happened to walk into the wrong NGO office that day.

This fragmentation isn't anyone's fault. Organizations like **Cruz Roja**, **Cáritas**, and **ACCEM** do critical work under severe resource constraints, often relying on well-intentioned volunteers who may not have the information needed to guide people effectively. There is no centralized knowledge layer — and the cost of that gap is paid by the most vulnerable.

**RefugeeConnect AI** is my attempt to build that layer.

---

## 🎯 The Problem: A Fragmented Support Ecosystem

Every year, thousands of people arrive in Spain fleeing conflict or persecution, only to encounter a support ecosystem that is deeply fragmented:

| Challenge | Reality |
|---|---|
| **Information Silos** | Organizations lack coordinated information systems |
| **Geolocation Lottery** | Quality of guidance depends on which branch you visit |
| **Language Barriers** | Most resources exist only in Spanish |
| **Volunteer Dependency** | Guidance hinges on the specific knowledge of an individual |
| **Digital Illiteracy** | Many cannot effectively search for their own rights online |

> **Real example:** Knowing that Cruz Roja helped with my situation, I visited one branch — they couldn't guide me despite genuine effort. I tried another branch in the same city, and got the help I needed. The information existed. The coordination didn't.

---

## 💡 The Solution: A Dual-Inference Architecture

RefugeeConnect AI addresses these barriers through two complementary access modes, designed to be resilient even when one component is under load:

```
┌─────────────────────────────────────────────────────┐
│                  User Interface (Dash)              │
│           Multilingual: ES | EN | AR | FR           │
└──────────────────┬──────────────────────────────────┘
                   │
       ┌───────────┴───────────┐
       │                       │
       ▼                       ▼
┌─────────────┐       ┌─────────────────┐
│  AI Chat    │       │  Resource Map   │
│  Assistant  │       │  (Direct DB)    │
│             │       │                 │
│ Gemma 4 via │       │  OpenStreetMap  │
│ Google ADK  │       │  + SQLite       │
│ cloud/local │       │  (always on)    │
└─────────────┘       └─────────────────┘
       │                       │
       └───────────┬───────────┘
                   ▼
        ┌──────────────────┐
        │  SQLite Database │
        │  (Valencia NGOs) │
        └──────────────────┘
```

**AI Conversational Assistant** — Powered by Gemma 4 via Google ADK, it understands user needs in natural language and provides step-by-step guidance in their native language. An Orchestrator Agent uses a state-based decision tree to handle greetings, incomplete queries, and resource retrieval gracefully.

**Direct Resource Dashboard** — An interactive map (OpenStreetMap via Dash Leaflet) lets users filter and locate services (Legal, Health, Housing, Food, Employment) directly from the database — no AI dependency, always fast.

---

## 🚀 Key Features

- **Multilingual** — Native reasoning in English, Spanish, Arabic, and French
- **Local-First Privacy** — Run Gemma 4 locally via Ollama to protect sensitive user data in offline or privacy-critical environments
- **Hybrid Architecture** — Decoupled FastAPI backend + Plotly Dash frontend for scalability and independent maintenance
- **Safe Tool Design** — Tools return standardized strings (e.g., `NO_RECORDS`) to prevent hallucination loops in smaller local models
- **Resilient by Design** — The map interface works independently of the LLM; users always get *something* useful
- **Dual-Use Potential** — Useful not just for migrants, but also for NGO volunteers who need quick guidance themselves
- **Improved Responsiveness** — Input blocking during AI processing prevents duplicate messages; a status bar provides clear feedback during latency
- **Proximity-Aware Results** — A simulated user position is shown on the map as an icon; the assistant calculates driving distance and estimated travel time to each organization found, sorting results nearest-first
- **SLM-Optimized Orchestration** — Dedicated prompt strategy and consolidated tool architecture for Gemma 4's smaller local variants (E2B/E4B), enabling reliable deployment even on constrained hardware

---

## 🏗️ Technology Stack

| Layer | Technology |
|---|---|
| Model (Cloud) | Gemma 4 (31B) via Google AI Studio |
| Model (Local) | Gemma 4 (E2B/E4B) via Ollama & LiteLLM |
| Agent Framework | Google ADK (Agent Development Kit) |
| Routing & Distances | OSRM (Open Source Routing Machine) via router.project-osrm.org |
| Backend API | FastAPI (Asynchronous) |
| Frontend | Plotly Dash & Dash Leaflet (OpenStreetMap) |
| Database | SQLite |
| Package Manager | `uv` (reliable dependency resolution) |
| Infrastructure | Docker & Docker Compose |

---

## 🤖 Agent Architecture

The system evolved from an **Orchestrator → Multi-Agent → Tool Specialist** hierarchy to a more streamlined **Orchestrator → Tool** architecture, reducing latency and hallucination risk — especially important for smaller local models.

```
┌──────────────────────────────────────────────┐
│        Orchestrator Agent                    │
│     (State-based Decision Tree)              │
│                                              │
│ GREETING → PROFILE_CHECK → QUERY_PARSE       │
│       → RESOURCE_SEARCH → RESPONSE           │
└────────────────────┬─────────────────────────┘
                     │
    ┌────────────────┬────────────────┐
    ▼                ▼                ▼
[get_services] [get_rights]    [get_distances]
   tool           tool              tool
```

**Key design decisions:**
- State-based reasoning prevents ambiguous or looping responses
- Tools return normalized strings, not raw objects
- The map bypasses the LLM entirely for resilience and speed
- **Error Handling & API Resilience:** Robust retry logic handles 500 INTERNAL errors from the Google GenAI API via `google-adk`'s automatic retries; the Orchestrator maintains conversational state across API failures
- **Dynamic Prompting:** `config.py` detects the deployment environment (Cloud vs. Local) and serves specialized instruction sets — full-reasoning prompts for 31B, simplified Chain-of-Thought prompts for 2B/4B variants

---

## 🔬 Technical Pivot: Optimizing for Local SLMs (Gemma 4B/2B)

**Initial development was validated using Qwen via Ollama due to personal hardware limitations.** While occasionally tested on a more capable machine with Gemma 4's smaller local variants (2B and 4B via Ollama), significant new challenges emerged that required a dedicated engineering response.

While the 31B cloud model handled multiple specialized tools seamlessly, the 2B and 4B variants suffered from attention drift, entering repetitive tool-calling cycles without progressing. The root cause was excessive orchestration complexity for smaller context windows. The solution was consolidating from three separate tools into a single unified tool for local deployment, drastically reducing the model's decision surface.

**Smaller models frequently lost track of System Prompt constraints** once the context window filled with raw tool output. This caused state loss and infinite loops. Rather than fighting this tendency, the architecture was redesigned to leverage it: strict control instructions ("Data received. Now summarize and stop.") and reminder of user language were injected directly at the end of each tool's response. Placing directives at the point of highest model attention — the most recent tokens — proved far more reliable than relying on distant system prompt constraints.

**Differentiated prompting strategy.** Prompt engineering that works for 31B models is often too verbose or nuanced for 2B variants. A dynamic prompting strategy was implemented: now detects the deployment environment (Local vs. Cloud) and serves specialized instruction sets. Local prompts were simplified, trying to to prevent hallucinations and loops.

**Observability-driven debugging.** Internal loops were opaque until raw ADK–inference engine exchanges were made visible. A dedicated LiteLLM logging integration and Ollama debug mode were used to perform deep-packet analysis of JSON payloads. This revealed a layered set of root causes: Chat Template mismatches, absent stop tokens, and — critically — a payload-level incompatibility where LiteLLM serializes tool results with role: "tool" while Gemma's chat template expects role: "tool_responses". Since modifying library internals is not portable, a targeted monkey-patch was implemented at the _get_completion_inputs boundary, intercepting the assembled message list and rewriting the role field only for affected models, without replicating any internal logic. This fix applies transparently at startup with no changes to deployment dependencies.

**Inference Parameter Tuning for Local SLMs.** Reliable local deployment required explicit inference configuration beyond prompt engineering. For Gemma 2B/4B via Ollama: temperature=0.1 enforces near-deterministic instruction-following; num_ctx=8192 and num_predict: 2048 prevents silent context truncation — Ollama's default of 4k tokens caused the system prompt to be dropped as tool outputs filled the window. 

This experience reinforced a core lesson: local AI deployment is not just about quantization — it is about orchestration. Optimizing for Gemma 4's smaller variants required moving beyond standard prompting into active context management, payload-level compatibility engineering, and observability-driven development.

---

## ⚙️ Installation & Setup

### Prerequisites

- Python 3.13+
- [Ollama](https://ollama.com) (for local inference mode)
- Google AI Studio API Key (for cloud mode)
- Docker *(optional, but recommended)*

### Quick Start with Docker

```bash
git clone https://github.com/jfrometa88/RefugeeConnect2.git
cd RefugeeConnect2
docker-compose up --build
```

| Service | URL |
|---|---|
| Dashboard | http://localhost:8601 |
| API | http://localhost:8000 |

### Manual Setup (using `uv`)

`uv` resolves critical dependency conflicts between `google-adk` and `protobuf`:

```bash
uv sync

# Start the backend
uv run python api_app/IA_api.py

# In a separate terminal, start the frontend
uv run python dash_app/app.py
```

---

## 🔧 Gemma4 Tool Compatibility

Gemma's chat template expects `role="tool_responses"` for tool result messages, while LiteLLM's OpenAI-compatible default is `role="tool"`. Without correction, this mismatch causes agents to enter an **infinite tool-calling loop** — the model misinterprets the tool result as a new conversation turn and calls the tool again indefinitely.

This was identified through deep-packet inspection of raw JSON payloads via `litellm._turn_on_debug()` and verified bidirectionally using `qwen2.5` as a proxy: qwen completes normally with `role="tool"`, but enters the same loop when forced to `role="tool_responses"`, confirming the fix targets the exact behavior Gemma's chat template requires.

Two portable solutions are included. **Option B is active in this repository.**

### Option A — Runtime patch (see RefugeeConnect repository)

A targeted monkey-patch is applied at startup in `api_app/litellm_gemma_patch.py`, intercepting the assembled message list at the `_get_completion_inputs` boundary and rewriting the role field only for Gemma4 models — without modifying or replicating any internal library logic.

```
startup
  └── api_app/litellm_gemma_patch.py
        └── wraps _get_completion_inputs
              └── role "tool" → "tool_responses"  (gemma4 only)
```

No changes to installed packages. Works with a standard `uv sync` or `pip install -r requirements.txt`.

### Option B — Patched fork of `google-adk` *(default)*

The fix is applied directly inside `_content_to_message_param` in a maintained fork of `google-adk`.

> A pull request with this fix and full unit test coverage has been submitted upstream: [google/adk-python#5650](https://github.com/google/adk-python/issues/5650). If merged, both workarounds become unnecessary and can be removed.

---

## 📂 Project Structure

```
refugeeconnect-ai/
│
├── common/                         # Shared resources between containers
│   ├── data/
│   │   ├── schema.sql              # Database schema
│   │   ├── refugeeconnect.db       # SQLite database (Valencia NGOs)
│   │   └── logs/
│   │       └── logs.log
│   └── utils/
│       ├── tools.py                # Shared utilities
│       └── logger.py               # Logging configuration
│
├── api_app/                        # FastAPI Backend Container
│   ├── IA_api.py                   # FastAPI entry point
│   ├── agents/
│   │   ├── agent_manager.py        # AI architecture configuration
│   │   ├── agent.py                # Agent setup
│   │   └── tracing_plugin.py       # AI trace configuration
│   ├── config.py                   # Model & inference mode config (Cloud/Local detection)
│   ├── Dockerfile.api
│   └── requirements.txt
│
├── dash_app/                       # Dash Frontend Container
│   ├── app.py                      # Dash application entry point
│   ├── TRANSLATION.json            # i18n configuration (ES/EN/AR/FR)
│   ├── Dockerfile.dash
│   └── requirements.txt
│
├── docker-compose.yml
├── pyproject.toml
└── uv.lock
```

---

## 🌐 Scope & Honest Limitations

This project is a **functional proof of concept**, not a finished product. These constraints are deliberate:

- **Geographic scope:** Limited to Valencia (where I live and have personal experience)
- **Database coverage:** A representative sample of local NGOs — not exhaustive
- **Translation:** The AI translates responses dynamically, but static dashboard labels returned from the database are not yet translated (a known technical debt)
- **Local model testing:** Initial development used `qwen` as a proxy model via Ollama due to hardware limitations; Gemma E2B/E4B were subsequently tested and the architecture was adapted accordingly.
- **Session Management:** Currently lacks adequate session handling; interactions are treated in a volatile context suitable for demo purposes
- **Memory Optimization:** Relies on `InMemoryService` for session memory, which carries risks of data loss and high RAM consumption under load
- **Flow Optimization:** Further testing is required to optimize deep LLM data flow error handling to prevent frontend freezes during catastrophic API failures
- **User position:** Currently based on a fixed mock coordinate (Plaza del Ayuntamiento, Valencia). Real geolocation via browser API or manual input is planned but not yet implemented

The goal is to demonstrate **viability and impact** — to show what's possible, and invite the organizations, institutions, and developers who have the resources to take it further.

---

## 🔭 Vision: Beyond the Prototype

The concept is extensible in multiple directions:

- **Geographic expansion** — Beyond Valencia to all of Spain, or other countries
- **Population scope** — The same architecture serves homeless individuals, people with addictions, elderly without support, and children at risk (most NGOs already serve these groups)
- **Dual use** — A tool not just for people in need, but for NGO volunteers who need quick answers when helping others
- **Data partnerships** — Formal collaboration with organizations to keep the database current and comprehensive
- **Vector Database Integration (RAG)** — Transitioning from pure SQLite queries to a Retrieval-Augmented Generation architecture using vector databases to handle complex legal texts more efficiently in resource-constrained environments
- **Real geolocation** — Replace the mock position with browser-based or user-provided coordinates for genuinely personalized proximity routing
- **Broader SLM support** — The orchestration patterns developed for Gemma E2B/E4B are applicable to other small local models, enabling deployment on a wider range of NGO hardware

---

## 🎯 Hackathon Tracks

This project is submitted to the **Gemma 4 Good Hackathon** under:

1. **Impact Track — Digital Equity & Inclusivity:** Breaking language and bureaucratic barriers for one of the most underserved populations in Europe.
2. **Special Technology Track — Ollama:** Showcasing Gemma 4 running locally for privacy-centric humanitarian use cases, where sensitive personal data must never leave the user's environment.

---

## 👤 Author

**[Jorge Israel Frometa Moya]**

This project was built from personal necessity, with a personal computer and personal experience. It is submitted with the hope that it reaches people who can give it the resources it deserves.

- **Kaggle:** [@jorgefrometa]
- **LinkedIn:** [www.linkedin.com/in/jorge-israel-frometa-moya]

---

## 🙏 Acknowledgments

- **Google DeepMind** — for the Gemma 4 models and the hackathon opportunity
- **Google** — for the Agent Development Kit (ADK)
- **Cruz Roja, Cáritas, ACCEM, and all NGOs in Spain** — for the work they do every day under difficult conditions
- **Everyone who shared their story** — the people I met navigating the same system, whose experiences shaped every design decision here