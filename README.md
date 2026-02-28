# Automaton Auditor

A hierarchical LangGraph agent swarm that performs autonomous code auditing using a Digital Courtroom architecture.

## Architecture

```
START
  -> ContextBuilder
  -> [RepoInvestigator || DocAnalyst || VisionInspector]   (parallel fan-out)
  -> EvidenceAggregator                                    (fan-in)
  -> (conditional: has evidence?)
      YES -> [Prosecutor || Defense || TechLead]           (parallel fan-out)
           -> ChiefJustice                                 (fan-in)
      NO  -> (skip judicial layer)
  -> ReportRenderer
  -> END
```

**Layer 1 -- Detective Layer** collects forensic evidence (git history, AST analysis, PDF content, diagram analysis) without forming opinions.

**Layer 2 -- Judicial Layer** applies three distinct persona lenses (adversarial Prosecutor, optimistic Defense, pragmatic Tech Lead) to every rubric criterion using `.with_structured_output()` for schema enforcement.

**Layer 3 -- Supreme Court** resolves dialectical conflict via deterministic Python rules (security override, fact supremacy, functionality weight, variance re-evaluation) and renders a structured Markdown audit report.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- A Google API key for Gemini (Gemini 2.5 Flash is the default model)
- (Optional) A LangSmith API key for tracing

## Setup

```bash
# Clone the repository
git clone https://github.com/Heban-7/automaton-auditor.git
cd automaton-auditor

# Install dependencies with uv
uv sync

# Configure environment
cp .env.example .env
# Edit .env and fill in your GOOGLE_API_KEY
```

## Running the Auditor

```bash
# Self-audit: run against your own repo (saves to audit/report_onself_generated/)
uv run python -m src --repo https://github.com/Heban-7/automaton-auditor \
    --pdf reports/final_report.pdf

# Peer-audit: run against an assigned peer's repo (saves to audit/report_onpeer_generated/)
uv run python -m src --repo https://github.com/peer/repo \
    --pdf path/to/peer_report.pdf \
    --output-dir audit/report_onpeer_generated

# Audit without a PDF report
uv run python -m src --repo https://github.com/user/repo
```

## Project Structure

```
automaton-auditor/
  pyproject.toml              # Dependencies (managed via uv)
  .env.example                # Required environment variables
  rubric.json                 # Machine-readable auditing rubric (the "Constitution")
  Dockerfile                  # Containerized runtime (optional)
  src/
    __init__.py
    __main__.py               # CLI entry point (python -m src)
    config.py                 # Configuration loader (.env, rubric, LLM model names)
    state.py                  # Pydantic models & TypedDict state with reducers
    graph.py                  # Full StateGraph with fan-out/fan-in orchestration
    tools/
      __init__.py
      repo_tools.py           # Sandboxed git clone, git history, AST analysis
      doc_tools.py            # PDF parsing (docling/PyMuPDF), keyword search, image extraction
    nodes/
      __init__.py
      detectives.py           # RepoInvestigator, DocAnalyst, VisionInspector, EvidenceAggregator
      judges.py               # Prosecutor, Defense, TechLead with distinct system prompts
      justice.py              # ChiefJustice (deterministic rules) + Markdown report renderer
  audit/
    report_onself_generated/  # Report when you audit your own repo (run with default --output-dir)
    report_onpeer_generated/  # Report when you audit a peer's repo (use --output-dir audit/report_onpeer_generated)
    report_bypeer_received/   # Report your peer's agent generated when auditing your repo (place here manually)
  reports/
    final_report.pdf          # Architectural report for peer agents to ingest
```

## Key Design Decisions

- **Pydantic over dicts**: All state and outputs use typed `BaseModel` / `TypedDict` schemas with `operator.add` and `operator.ior` reducers to prevent data loss during parallel execution.
- **AST over regex**: Code analysis uses Python's built-in `ast` module for structural verification rather than brittle regex patterns.
- **Sandboxed cloning**: All git operations run inside `tempfile.TemporaryDirectory()` using `subprocess.run()` with error handling. No `os.system()` calls.
- **Structured output enforcement**: All Judge LLM calls use `.with_structured_output(JudicialOpinionBatch)` with retry logic and exponential backoff.
- **Deterministic synthesis**: The ChiefJustice applies named Python rules (security override, fact supremacy, functionality weight, variance re-evaluation) rather than delegating to an LLM.
- **Batched judge calls**: Each judge evaluates all 10 criteria in a single LLM call (3 total API calls for the judicial layer) instead of 30 individual calls.

## Environment Variables

| Variable | Description | Required |
|---|---|---|
| `GOOGLE_API_KEY` | Google AI API key for Gemini | Yes |
| `LANGCHAIN_TRACING_V2` | Enable LangSmith tracing (`true`) | Optional |
| `LANGCHAIN_API_KEY` | LangSmith API key | Optional |
| `LANGCHAIN_PROJECT` | LangSmith project name | Optional |
| `LLM_MODEL` | Override the LLM model (default: `gemini-2.5-flash`) | Optional |
| `VISION_MODEL` | Override the vision model (default: `gemini-2.5-flash`) | Optional |

## Observability

LangSmith tracing is enabled by setting the following in `.env`:

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=automaton-auditor
```
