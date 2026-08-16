# Cantordust AI Assessment

An autonomous multi-agent pipeline that extracts, cross-validates, and reports on technical data from conflicting manufacturer datasheets. Built with **LangGraph**, **Gemini 2.5 Flash**, and **FastAPI**.

## The Problem

Ramesh at SunBridge Trading (Kathmandu) needs to import a 5kW Deye solar inverter into Nepal. The factory sent two datasheets — one from 2023 (AM2-P1 variant) and one from 2024 (AM2 variant) — and they don't match. Some values conflict, some fields appear in only one document, and the table layouts make manual comparison error-prone.

This pipeline **autonomously** reads both PDFs, extracts the 5kW model specs, identifies every discrepancy, and produces a compliance-ready report for Ramesh's import agent.

---

## Quick Start

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) (recommended) or pip
- A [Google Gemini API key](https://aistudio.google.com/apikey)

### 1. Clone & Install

```bash
git clone <repo-url>
cd cantordust_task

# Using uv (recommended)
uv sync

```

### 2. Set Your API Key

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_api_key_here
```

### 3. Run the API Server

```bash
uvicorn main:app
```

The server starts at `http://127.0.0.1:8000`. Visit `http://127.0.0.1:8000/docs` for the Swagger UI.

### 4. Trigger the Pipeline

> **Note:** This pipeline takes ~30–60 seconds per loop (each loop involves 2 PDF extractions + 1 review). Use `curl` in the terminal instead of Swagger UI to avoid browser timeout errors.

```bash
curl -X 'POST' \
  'http://127.0.0.1:8000/run' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
  "source1": "https://www.deyeinverter.com/deyeinverter/2023/10/07/datasheet_sun-4-12k-g06p3-eu-am2-p1_231007_en.pdf",
  "source2": "https://www.deyeinverter.com/deyeinverter/2024/03/20/datasheet_sun-4-15k-g06p3-eu-am2_240318_en.pdf",
  "target_model": "SUN-5K-G06P3-EU-AM2 (5kW model)",
  "max_loops": 2
}'
```

### 5. View Outputs

After the pipeline completes:

| Output | Location | Description |
|:---|:---|:---|
| **Final Report** | `output/final_report.md` | Human-readable Markdown report for Ramesh |
| **Raw Agent Data** | `output/agent_results.json` | Complete JSON with all extraction histories, review results, and state |

---

## Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      FastAPI (main.py)                       │
│                  POST /run → build_graph()                   │
└───────────────────────────┬─────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                LangGraph State Machine (graphy.py)           │
│                                                              │
│   ┌──────────┐     ┌──────────┐                              │
│   │ Agent 1  │     │ Agent 2  │   ◄── Parallel Fan-Out       │
│   │ (PDF 1)  │     │ (PDF 2)  │                              │
│   └────┬─────┘     └────┬─────┘                              │
│        │                │                                    │
│        └───────┬────────┘                                    │
│                ▼                                             │
│        ┌──────────────┐                                      │
│        │   Reviewer   │   ◄── Fan-In (Audit)                 │
│        └──────┬───────┘                                      │
│               │                                              │
│        ┌──────┴───────┐                                      │
│        │  Pass?  Fail │                                      │
│        ▼              ▼                                      │
│   ┌──────────┐  ┌──────────┐                                 │
│   │ Reporter │  │  Router  │ ──► loop_count++ ──► Back to    │
│   │ (Final)  │  │ (Retry)  │     Agent 1 & 2                 │
│   └────┬─────┘  └──────────┘                                 │
│        │                                                     │
│        ▼                                                     │
│       END                                                    │
└─────────────────────────────────────────────────────────────┘
```

### Execution Flow (Step by Step)

#### Step 1 — Parallel Extraction (Fan-Out)

Two `AgentNode` instances run **simultaneously** via `asyncio`:

| Agent | Reads | Variant | Output Key |
|:---|:---|:---|:---|
| `Agent1_Extractor` | Source 1 PDF (2023) | AM2-P1 | `source1_history` |
| `Agent2_Extractor` | Source 2 PDF (2024) | AM2 | `source2_history` |

Each agent:
1. Receives the PDF URL dynamically from the API request (via `url_key` → state lookup)
2. Gets a forensic extraction prompt with column-isolation rules from `prompt.json`
3. Sends the PDF + prompt to **Gemini 2.5 Flash** using `UrlContext` (the LLM reads the PDF directly)
4. Receives structured JSON validated against the `ProductData` Pydantic schema
5. Appends the result to its history list in the shared state

**Key design choice:** Each agent processes **exactly one PDF**. This prevents cross-contamination where the LLM might mix up values between two documents.

#### Step 2 — Forensic Review (Fan-In)

The `Reviewer` node activates after **both** extractors finish.

It receives:
- The latest extraction from `source1_history[-1]`
- The latest extraction from `source2_history[-1]`

The reviewer performs:
1. **Full-field comparison** — every parameter, not just currents
2. **Exact string matching** — `"20+20"` vs `"13+13"` is a mismatch, period
3. **Delta calculation** — explicit arithmetic: `(20-13)/13 = 53.8%`
4. **Null rejection** — if an extractor returned empty values for core parameters, it flags this as an extraction failure
5. **Classification** — each conflict is labeled as either `MODEL_UPGRADE` or `EXTRACTION_ERROR`

The reviewer outputs a `ReviewResultSchema` with `review_passed: bool`, `conflicts: list`, and `instruction: str`.

**Thinking enabled:** The Reviewer uses Gemini's `thinking_config` with a 1024-token reasoning budget for deeper analysis.

#### Step 3 — Conditional Routing

```python
def should_continue(state):
    if review_passed:        return "success"      → Reporter
    if loop_count >= max:    return "max_retries"   → Reporter
    else:                    return "retry"          → Router → Agents
```

Three possible outcomes:

| Condition | Route | What Happens |
|:---|:---|:---|
| `review_passed = True` | → Reporter | All fields match or conflicts are properly classified |
| `loop_count >= max_loops` | → Reporter | Max retries reached, report generated with whatever data exists |
| Otherwise | → Router → Agents | `loop_count` increments, both agents re-extract with reviewer feedback |

#### Step 4 — Final Report Generation

The `Reporter` node receives:
- Full `source1_data` and `source2_data` as JSON
- `review_findings` from the auditor

It generates an 8-section Markdown report:

1. **Product Identity** — model + variant names from each source
2. **Manufacturer Identity** — legal name + factory address
3. **Referenced Standards** — IEC/EN standards from each source (never says "certified")
4. **Full Comparison Table** — every extracted parameter, side by side
5. **Technical Interpretation** — plain-language explanation of discrepancies
6. **Recommended Label Data** — what should appear on the product label
7. **Data Confidence & Layout Uncertainties** — where the pipeline was unsure
8. **Importer Paperwork Note** — what Ramesh still needs to chase

**Thinking enabled:** The Reporter also uses a 1024-token thinking budget.

---

## Project Structure

```
cantordust_task/
├── main.py              # FastAPI app — POST /run endpoint
├── prompt.json          # All agent prompts (extraction, review, report)
├── pyproject.toml       # Dependencies (uv/pip)
├── .env                 # GEMINI_API_KEY (not committed)
├── src/
│   ├── agents.py        # AgentNode class — reusable LangGraph node
│   ├── graphy.py        # LangGraph DAG definition + state schema
│   ├── llm.py           # GeminiEngine — async Gemini API wrapper
│   └── models.py        # Pydantic schemas (ProductData, ReviewResult)
├── output/
│   ├── final_report.md  # Generated Markdown report
│   └── agent_results.json  # Full pipeline state dump
```

### Key Files Explained

| File | Role |
|:---|:---|
| `src/agents.py` | Generic `AgentNode` class. Accepts an engine, prompt, output key, and optional PDF URL. Resolves URLs dynamically from state. Handles prompt variable injection via safe string replacement. |
| `src/graphy.py` | Defines the `AgentState` TypedDict, instantiates all 4 agent nodes, and builds the LangGraph `StateGraph` with parallel edges, conditional routing, and retry logic. |
| `src/llm.py` | `GeminiEngine` — a thin async wrapper around `google.genai`. Handles PDF ingestion via `UrlContext`, Pydantic schema injection, thinking config, and structured output parsing. |
| `src/models.py` | All Pydantic models: `RequestBody` (API input), `ProductData` (extraction schema with `extra='allow'`), `ReviewResultSchema` (audit output). |
| `prompt.json` | Externalized prompts for all agents. No prompts are hardcoded in Python. |

---

## API Reference

### `POST /run`

**Request Body:**

```json
{
  "source1": "https://example.com/datasheet_v1.pdf",
  "source2": "https://example.com/datasheet_v2.pdf",
  "target_model": "SUN-5K-G06P3-EU-AM2 (5kW model)",
  "max_loops": 2
}
```

| Field | Type | Description |
|:---|:---|:---|
| `source1` | `string` | URL to the first PDF datasheet |
| `source2` | `string` | URL to the second PDF datasheet |
| `target_model` | `string` | The specific model to extract (e.g. the 5kW variant) |
| `max_loops` | `int` | Maximum extraction→review→retry cycles (default: 4) |

**Response:**

```json
{
  "final_report": "**CRITICAL REVISION CONFLICT WARNING:**\n\n..."
}
```

---

## Dependencies

| Package | Purpose |
|:---|:---|
| `fastapi` | HTTP API framework |
| `uvicorn` | ASGI server |
| `langgraph` | Stateful agent orchestration (DAG with conditional routing) |
| `langchain` | LangGraph dependency |
| `google-genai` | Gemini 2.5 Flash API client |
| `pydantic` | Structured output validation |
| `python-dotenv` | Environment variable loading |
