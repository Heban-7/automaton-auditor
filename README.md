# Automaton Auditor

A hierarchical LangGraph agent swarm that performs autonomous code auditing using a Digital Courtroom architecture.

## Architecture

```
START
  -> ContextBuilder
  -> [RepoInvestigator || DocAnalyst || VisionInspector]   (parallel fan-out)
  -> EvidenceAggregator                                    (fan-in)
  -> [Prosecutor || Defense || TechLead]                   (parallel fan-out)
  -> ChiefJustice                                          (fan-in)
  -> ReportRenderer
  -> END
```

**Layer 1 -- Detective Layer** collects forensic evidence (git history, AST analysis, PDF content, diagram analysis) without forming opinions.

**Layer 2 -- Judicial Layer** applies three distinct persona lenses (adversarial Prosecutor, optimistic Defense, pragmatic Tech Lead) to every rubric criterion using `.with_structured_output()` for schema enforcement.

**Layer 3 -- Supreme Court** resolves dialectical conflict via deterministic Python rules (security override, fact supremacy, functionality weight, variance re-evaluation) and renders a structured Markdown audit report.

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- An OpenAI API key (GPT-4o is the default model)
- (Optional) A Google API key for Gemini vision analysis
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
# Edit .env and fill in your API keys
```

## Running the Auditor

```bash
# Audit a repository (no PDF report)
uv run python -m src --repo https://github.com/user/repo

# Audit a repository with a PDF report
uv run python -m src --repo https://github.com/user/repo --pdf path/to/report.pdf

# Specify a custom output directory
uv run python -m src --repo https://github.com/user/repo --pdf report.pdf --output-dir audit/report_onpeer_generated
```

The audit report will be written to `audit/report_onself_generated/report.md` by default.

## Project Structure

```
automaton-auditor/
  pyproject.toml          # Dependencies (managed via uv)
  .env.example            # Required environment variables
  rubric.json             # Machine-readable auditing rubric (the "Constitution")
  src/
    __init__.py
    __main__.py            # CLI entry point (python -m src)
    config.py              # Configuration loader (.env, rubric, LLM settings)
    state.py               # Pydantic models & TypedDict state with reducers
    graph.py               # Full StateGraph with fan-out/fan-in orchestration
    tools/
      __init__.py
      repo_tools.py        # Sandboxed git clone, git history, AST analysis
      doc_tools.py         # PDF parsing (docling/PyMuPDF), keyword search, image extraction
    nodes/
      __init__.py
      detectives.py        # RepoInvestigator, DocAnalyst, VisionInspector, EvidenceAggregator
      judges.py            # Prosecutor, Defense, TechLead with distinct system prompts
      justice.py           # ChiefJustice (deterministic rules) + Markdown report renderer
  audit/
    report_onself_generated/   # Self-audit output
    report_onpeer_generated/   # Peer-audit output
    report_bypeer_received/    # Received peer audit
  reports/                     # PDF reports
```

## Key Design Decisions

- **Pydantic over dicts**: All state and outputs use typed `BaseModel` / `TypedDict` schemas with `operator.add` and `operator.ior` reducers to prevent data loss during parallel execution.
- **AST over regex**: Code analysis uses Python's built-in `ast` module for structural verification rather than brittle regex patterns.
- **Sandboxed cloning**: All git operations run inside `tempfile.TemporaryDirectory()` using `subprocess.run()` with error handling. No `os.system()` calls.
- **Structured output enforcement**: All Judge LLM calls use `.with_structured_output(JudicialOpinion)` with retry logic.
- **Deterministic synthesis**: The ChiefJustice applies named Python rules (security override, fact supremacy, etc.) rather than delegating to an LLM.

## Observability

LangSmith tracing is enabled by setting the following in `.env`:

```
LANGCHAIN_TRACING_V2=true
LANGCHAIN_API_KEY=your-langsmith-key
LANGCHAIN_PROJECT=automaton-auditor
```
