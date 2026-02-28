# The Automaton Auditor: Final Architectural Report

**Project:** Automaton Auditor — Hierarchical LangGraph Swarm for Autonomous Code Governance  
**Author:** Heban-7  
**Date:** February 28, 2026  
**Repository:** https://github.com/Heban-7/automaton-auditor

---

## 1. Executive Summary

The Automaton Auditor is a production-grade, multi-agent AI system that autonomously audits GitHub repositories and PDF architectural reports against a structured 10-dimension rubric. It implements a **Digital Courtroom** metaphor: forensic detective agents collect objective evidence, three judicial agents argue from adversarial perspectives, and a chief justice synthesizes a final verdict using deterministic conflict-resolution rules.

The system is built on LangGraph with two parallel fan-out/fan-in stages, Pydantic-enforced state typing, sandboxed tool execution, and Gemini 2.5 Flash as the LLM backbone. It produces a structured Markdown audit report with executive summary, per-criterion breakdown with dissenting opinions, and a file-level remediation plan.

**Peer-Audit Result (Birkity/automaton-auditor-fde-week2):** 3.9/5.0 overall, with 8 of 10 criteria passing (score >= 3). Self-audit has not been run yet.

| Criterion                         | Score |
| --------------------------------- | ----- |
| Git Forensic Analysis             | 5/5   |
| State Management Rigor            | 5/5   |
| Graph Orchestration Architecture  | 5/5   |
| Safe Tool Engineering             | 3/5   |
| Structured Output Enforcement     | 5/5   |
| Judicial Nuance and Dialectics    | 4/5   |
| Chief Justice Synthesis Engine    | 3/5   |
| Theoretical Depth (Documentation) | 5/5   |
| Report Accuracy (Cross-Reference) | 2/5   |
| Architectural Diagram Analysis    | 2/5   |

---

## 2. Architecture Deep Dive

### 2.1 System Overview

The system is organized into three hierarchical layers that mirror a real courtroom proceeding:

1. **Layer 1 — Detective Layer (Forensic Evidence Collection):** Three specialized agents (RepoInvestigator, DocAnalyst, VisionInspector) run in **parallel** to collect objective, factual evidence. They do not form opinions — they produce structured `Evidence` objects containing what they found, where they found it, and their confidence level.

2. **Layer 2 — Judicial Layer (Dialectical Analysis):** Three judge agents (Prosecutor, Defense, TechLead) receive the **same aggregated evidence** and evaluate every rubric criterion through their distinct, conflicting persona lenses. The Prosecutor looks for gaps and security flaws. The Defense highlights effort and creative solutions. The Tech Lead evaluates practical viability. This creates genuine **dialectical tension** — the same evidence produces three different scores and arguments.

3. **Layer 3 — Supreme Court (Deterministic Synthesis):** The ChiefJustice resolves the dialectical conflict using **hardcoded Python rules**, not an LLM prompt. Named rules (Security Override, Fact Supremacy, Functionality Weight, Variance Re-evaluation) are applied in priority order. The final verdict is serialized as a structured Markdown report.

### 2.2 Dialectical Synthesis

Dialectical Synthesis is the core reasoning mechanism of the Judicial Layer. It follows the Thesis-Antithesis-Synthesis model:

- **Thesis (Prosecutor):** "This code has security flaws and missing parallel orchestration. Score: 1."
- **Antithesis (Defense):** "The engineer demonstrated deep understanding through iterative commits and sophisticated AST parsing. Score: 4."
- **Synthesis (ChiefJustice):** The ChiefJustice does not merely average the scores. It applies deterministic rules: if the Prosecutor identifies a confirmed security vulnerability, the Security Override rule caps the score at 3 regardless of the Defense's argument. If the Defense claims merit but all forensic evidence shows `found=False`, the Fact Supremacy rule overrules the Defense.

This process ensures that the final verdict is **auditable and reproducible** — the same evidence always produces the same verdict, because the synthesis logic is deterministic Python `if/else` code, not an LLM prompt that could vary between runs.

In practice, our peer-audit of Birkity's repository produced genuine dialectical tension on the Judicial Nuance criterion: the Prosecutor scored it 1 (noting `"Distinct prompts found: []"` from the regex-based prompt extractor), the Defense scored it 4 (arguing architectural intent), and the TechLead scored it 5 (confirming persona separation). The ChiefJustice's Variance Re-evaluation rule triggered, producing an explicit dissent summary documenting the disagreement.

### 2.3 Fan-In / Fan-Out Architecture

The StateGraph implements two distinct parallel fan-out/fan-in patterns:

```
START
  -> ContextBuilder (loads rubric.json into state)
  |
  |-- Fan-Out Layer 1 (Detectives) ----------------------|
  |   -> RepoInvestigator  (clones repo, AST analysis)   |
  |   -> DocAnalyst        (PDF parsing, keyword search)  |  PARALLEL
  |   -> VisionInspector   (image extraction, vision LLM) |
  |-------------------------------------------------------|
  |
  -> EvidenceAggregator (fan-in: validates completeness)
  |
  -> Conditional Edge: has_evidence?
  |   NO  -> ReportRenderer -> END
  |   YES:
  |
  |-- Fan-Out Layer 2 (Judges) ------------------|
  |   -> Prosecutor  (adversarial lens)          |
  |   -> Defense     (optimistic lens)           |  PARALLEL
  |   -> TechLead    (pragmatic lens)            |
  |----------------------------------------------|
  |
  -> ChiefJustice (fan-in: deterministic synthesis)
  -> ReportRenderer (Markdown serialization)
  -> END
```

**Why Fan-Out/Fan-In matters:** In LangGraph, when multiple edges leave a single node, those target nodes execute **concurrently**. The `ContextBuilder` node has three outgoing edges — one to each detective — so all three run in parallel. The `EvidenceAggregator` node acts as the synchronization barrier: it only executes after all three detectives have completed and written their evidence to the shared state.

**State Reducers prevent data loss:** The `AgentState` uses `Annotated[Dict[str, List[Evidence]], operator.ior]` for the `evidences` field. This means when three parallel detectives each return `{"evidences": {"repo": [...]}}`, `{"evidences": {"doc": [...]}}`, and `{"evidences": {"vision": [...]}}`, the `operator.ior` reducer **merges** these dicts instead of one overwriting the others. Similarly, `Annotated[List[JudicialOpinion], operator.add]` concatenates the three judges' opinion lists.

**Conditional edges handle failure gracefully:** After the EvidenceAggregator, the `_check_evidence` function counts total evidence items. If zero evidence was collected (e.g., git clone failed and no PDF was provided), the graph short-circuits directly to the ReportRenderer, skipping the expensive judicial layer entirely.

### 2.4 Metacognition

Metacognition — the ability to think about thinking — is embedded in the system at multiple levels:

1. **The system evaluates evaluators.** The Automaton Auditor is designed to grade Week 2 submissions, which are themselves auditor swarms. This means the system must understand what makes a good evaluator: typed state, parallel orchestration, structured output, deterministic synthesis. It uses its own architecture as the standard against which it judges others.

2. **The MinMax feedback loop.** When the auditor runs against its own repository (self-audit), it produces a report identifying its own weaknesses. We have not yet run self-audit; instead, we ran the auditor against a peer's repository (Birkity). That run revealed bugs in our auditor: the `--output-dir` CLI argument was not plumbed through to the report renderer, the judge layer was making 30 individual LLM calls (hitting rate limits) instead of 3 batched calls, and error messages were being silently swallowed. We fixed these issues so that peer audits (and future self-audits) run correctly.

3. **The Detective layer evaluates code comprehension, not just code existence.** The RepoInvestigator doesn't just check if `src/state.py` exists — it uses AST parsing to verify that the file contains classes inheriting from `BaseModel` or `TypedDict`, that `operator.add` and `operator.ior` reducers are present, and that the `StateGraph` builder has parallel edge patterns. This structural understanding goes beyond surface-level validation.

4. **The Judicial layer evaluates evaluation quality.** The Prosecutor's system prompt includes instructions to charge "Orchestration Fraud" if the graph is linear, and "Hallucination Liability" if judges return freeform text. These are meta-evaluations: the system is judging whether another system's evaluation mechanisms are rigorous.

### 2.5 State Synchronization

State synchronization in this system is achieved through LangGraph's built-in reducer mechanism on the `AgentState` TypedDict:

```python
class AgentState(TypedDict):
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]  # dict merge
    opinions: Annotated[List[JudicialOpinion], operator.add]       # list concat
```

When parallel nodes complete, LangGraph applies these reducers to merge their outputs before the next synchronization node runs. The `evidence_aggregator` node serves as the synchronization barrier between the detective and judicial layers, ensuring all forensic evidence is available before any judge begins analysis.

---

## 3. Architectural Diagram

```
                        ┌─────────────┐
                        │    START     │
                        └──────┬──────┘
                               │
                        ┌──────▼──────┐
                        │ContextBuilder│
                        └──────┬──────┘
                               │
              ┌────────────────┼────────────────┐
              │                │                │
     ┌────────▼────────┐ ┌────▼─────┐ ┌────────▼────────┐
     │RepoInvestigator │ │DocAnalyst│ │VisionInspector  │
     │ (git, AST)      │ │ (PDF)    │ │ (diagrams)      │
     └────────┬────────┘ └────┬─────┘ └────────┬────────┘
              │                │                │
              └────────────────┼────────────────┘
                               │
                     ┌─────────▼─────────┐
                     │EvidenceAggregator  │
                     └─────────┬─────────┘
                               │
                    ┌──────────┼──────────┐
                    │          │          │
              ┌─────▼───┐ ┌───▼───┐ ┌───▼─────┐
              │Prosecutor│ │Defense│ │TechLead │
              │ (harsh)  │ │(kind) │ │(pragmatic│
              └─────┬───┘ └───┬───┘ └───┬─────┘
                    │          │          │
                    └──────────┼──────────┘
                               │
                     ┌─────────▼─────────┐
                     │   ChiefJustice    │
                     │  (deterministic)  │
                     └─────────┬─────────┘
                               │
                     ┌─────────▼─────────┐
                     │  ReportRenderer   │
                     └─────────┬─────────┘
                               │
                        ┌──────▼──────┐
                        │     END     │
                        └─────────────┘
```

The diagram shows two distinct fan-out/fan-in patterns: one for the three detectives (Layer 1) converging at the EvidenceAggregator, and one for the three judges (Layer 2) converging at the ChiefJustice. A conditional edge (not shown for clarity) can bypass the judicial layer entirely when zero evidence is collected.

---

## 4. Criterion-by-Criterion Breakdown of Peer-Audit Results

_The following breakdown describes our auditor's evaluation of the peer repository [Birkity/automaton-auditor-fde-week2](https://github.com/Birkity/automaton-auditor-fde-week2). Self-audit of our own repository has not been run yet._

### 4.1 Git Forensic Analysis — 5/5

All three judges unanimously scored 5/5. The peer's repository contains 23 commits demonstrating clear progression from environment setup through tool engineering to graph orchestration. The commit history is atomic and iterative, not a bulk upload.

### 4.2 State Management Rigor — 5/5

Unanimous 5/5. The peer's `AgentState` uses `TypedDict` with `Annotated` reducers (`operator.add`, `operator.ior`). `Evidence` and `JudicialOpinion` are Pydantic `BaseModel` classes with typed fields and validation constraints.

### 4.3 Graph Orchestration Architecture — 5/5

Unanimous 5/5. The peer's StateGraph has 15 edges and 2 conditional edges, implementing two distinct parallel fan-out/fan-in patterns. The conditional edge after the EvidenceAggregator handles the "no evidence" failure scenario.

### 4.4 Safe Tool Engineering — 3/5

All judges scored 5/5 for the peer's repo, but our auditor's ChiefJustice **Security Override** rule capped the final score at 3 because the Prosecutor's argument contained security-related keywords. The word "security" appearing in the Prosecutor's assessment (even positively — "safe sandboxed tooling") triggers the conservative cap. This is an area where our auditor's Security Override rule could be refined to distinguish between "security concern found" and "security measures confirmed."

### 4.5 Structured Output Enforcement — 5/5

Unanimous 5/5. The peer's judge LLM calls use `.with_structured_output()` bound to the Pydantic schema.

### 4.6 Judicial Nuance and Dialectics — 4/5

Significant dissent: Prosecutor scored 1, Defense scored 4, TechLead scored 5 (variance=4). Our auditor's regex-based prompt extractor reported `"Distinct prompts found: []"` for the peer's judges — a false negative caused by the extractor's limited regex pattern failing to match the peer's prompt format. The Defense correctly argued that persona separation exists architecturally. Our ChiefJustice's Variance Re-evaluation rule triggered, and the weighted score resolved to 4.

### 4.7 Chief Justice Synthesis Engine — 3/5

All judges scored 5/5 for the peer's Chief Justice, but our auditor's Security Override rule capped the score at 3 due to security keywords in the Prosecutor's argument. Same false-positive issue as criterion 4.4.

### 4.8 Theoretical Depth (Documentation) — 5/5

Majority 5/5 (Prosecutor gave 4/5). Four of five target terms were found with substantive context in the peer's PDF report: Dialectical Synthesis, Fan-In, Fan-Out, and Metacognition. The term "State Synchronization" was not found, which the Prosecutor correctly flagged.

### 4.9 Report Accuracy (Cross-Reference) — 2/5

Failed. Our auditor has a race condition: the DocAnalyst runs in parallel with the RepoInvestigator, so `repo_path` is always empty when cross-referencing executes. The parallel fan-out means the DocAnalyst cannot access the cloned repo path. Our Fact Supremacy rule correctly overruled the Defense when evidence was `found=False`.

### 4.10 Architectural Diagram Analysis — 2/5

Failed. Our auditor's PyMuPDF image extractor could not extract images from the peer's PDF (likely vector-based diagrams embedded in a format PyMuPDF doesn't handle). The VisionInspector reported `"No images could be extracted from the PDF."` Our Fact Supremacy rule correctly overruled the Defense.

---

## 5. Reflection on the MinMax Feedback Loop

### 5.1 What Running the Auditor (Peer-Audit) Revealed

We have not yet run self-audit. Running our auditor against the peer's repository (Birkity/automaton-auditor-fde-week2) revealed several bugs and limitations in our own auditor:

1. **The `--output-dir` CLI argument was dead code.** It was parsed from the command line but never passed to the report renderer, which hardcoded `audit/report_onself_generated`. Fixed by adding `output_dir` to `AgentState` and having the renderer read it from state.

2. **All 30 judge LLM calls were silently failing.** The original code made 10 individual API calls per judge (30 total), and every 429 rate-limit error was caught by a bare `except Exception` that fell back to `score=1` with no logging. The report showed all 1/5 scores with "Failed to produce structured output after retries" — useless for debugging. Fixed by batching all 10 criteria into a single call per judge (3 total calls), adding exponential backoff for rate limits, and printing actual error messages.

3. **The Security Override rule has a false-positive problem.** The rule triggers whenever the Prosecutor's argument contains security-related keywords, even when the Prosecutor is praising the security measures. This caused Safe Tool Engineering and Chief Justice Synthesis to be capped at 3 despite unanimous 5/5 judge scores.

4. **The cross-reference race condition.** The DocAnalyst's `_collect_report_accuracy` reads `state["repo_path"]` during parallel execution, but the RepoInvestigator hasn't finished cloning yet. Result: 0 verified paths, 0 hallucinated paths.

### 5.2 How Our Auditor Was Updated

Based on the peer-audit run and the issues we observed:

- **Batched judge calls** reduced API usage from 30 calls to 3 calls, staying within free-tier rate limits.
- **Exponential backoff** with up to 120s delays handles transient 429 errors gracefully.
- **Visible error logging** now prints the actual exception type and message for every failed attempt.
- **The `--output-dir` parameter** now correctly flows through `AgentState` to the `report_renderer_node`.

### 5.3 What a Peer's Agent Could Catch When Auditing Our Repository

When a peer runs their auditor against our repository (Heban-7/automaton-auditor), they could identify:

- The Security Override false-positive issue: the rule should check whether the Prosecutor is reporting a confirmed vulnerability vs. confirming the absence of one.
- The cross-reference race condition: this requires moving the path-verification logic to a post-aggregation step.
- The `extract_judge_prompts` function uses regex to find system prompts, which fails on multi-line string formats that don't match the expected pattern.

---

## 6. Remediation Plan for Remaining Gaps (In Our Auditor)

_These are gaps in our own Automaton Auditor codebase, identified when running it against the peer's repository._

### 6.1 Report Accuracy Cross-Reference (Score: 2/5 on peer audit)

**Root cause:** Our DocAnalyst runs concurrently with the RepoInvestigator, so `repo_path` is empty when cross-referencing occurs.

**Fix:** Move the `_collect_report_accuracy` logic to the `EvidenceAggregator` node, which runs after all detectives complete and has access to the final `repo_path`.

### 6.2 Architectural Diagram Analysis (Score: 2/5 on peer audit)

**Root cause:** Our PyMuPDF-based `get_images()` cannot extract vector-based diagrams or rasterize PDF pages.

**Fix:** Add a fallback that rasterizes each PDF page at 200 DPI using PyMuPDF's `page.get_pixmap()` and sends the page images to the vision model.

### 6.3 Security Override False Positives

**Root cause:** Our rule triggers on any mention of security keywords in the Prosecutor's argument, including positive assessments like "safe sandboxed tooling," which incorrectly caps scores at 3.

**Fix:** Refine the rule to check for negative security signals specifically: look for phrases like "security flaw," "vulnerability found," "os.system detected" rather than the generic keyword "security."

### 6.4 Prompt Extraction False Negatives

**Root cause:** Our `extract_judge_prompts` regex expects a specific triple-quote string format and fails on other formats (e.g., the peer's prompt style).

**Fix:** Use AST analysis to find string assignments to variables matching `*_PROMPT` or `*_SYSTEM_PROMPT` patterns, which is format-agnostic.
