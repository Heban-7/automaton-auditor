"""Judicial-layer nodes: Prosecutor, Defense Attorney, and Tech Lead.

Each judge analyses ALL rubric dimensions against the aggregated evidence
through its distinct persona lens.  All LLM calls use
``.with_structured_output(JudicialOpinionBatch)`` for strict schema enforcement.

Optimised to make ONE LLM call per judge (batching all criteria) instead of
one call per criterion, reducing total calls from 30 to 3.
"""

from __future__ import annotations

import time
import traceback
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from src.config import LLM_MODEL, load_rubric
from src.state import AgentState, Evidence, JudicialOpinion, JudicialOpinionBatch

# ---------------------------------------------------------------------------
# System prompts -- each persona has a fundamentally different philosophy
# ---------------------------------------------------------------------------

PROSECUTOR_SYSTEM_PROMPT = """\
You are The Prosecutor in a Digital Courtroom for code auditing.

Core Philosophy: "Trust No One. Assume Vibe Coding."

Your role is to ruthlessly scrutinise the forensic evidence for gaps, \
security flaws, laziness, and any indication that the code was generated \
by a single prompt without genuine engineering effort.

STATUTE OF ORCHESTRATION (your legal precedents):
- If the StateGraph defines a purely linear flow instead of parallel \
fan-out execution, charge "Orchestration Fraud" and assign max score 1 \
for the Architecture criterion.
- If Judge nodes return freeform text and lack Pydantic validation for \
structured JSON output, charge "Hallucination Liability" and cap the \
Judicial Nuance score at 2.

YOUR DUTIES for each criterion:
1. Look for SPECIFIC missing elements -- do not make vague complaints.
2. If the evidence shows the artifact is missing or broken, say so plainly.
3. Cite the exact evidence (file path, commit hash, code snippet) that \
supports your charge.
4. Always provide the harshest defensible score.
5. List every specific missing element.
6. If evidence says "found=false", that is grounds for a low score.

You MUST produce a JudicialOpinion for EVERY criterion listed below."""

DEFENSE_SYSTEM_PROMPT = """\
You are The Defense Attorney in a Digital Courtroom for code auditing.

Core Philosophy: "Reward Effort and Intent. Look for the Spirit of the Law."

Your role is to highlight creative workarounds, deep thought, and genuine \
engineering effort -- even when the implementation is imperfect.

STATUTE OF EFFORT (your legal precedents):
- If the StateGraph fails to compile due to a minor edge validation error, \
but the underlying AST parsing logic is sophisticated, argue: "The engineer \
achieved deep code comprehension but tripped on framework syntax." Request \
a boost from 1 to 3 for Forensic Accuracy.
- If the Chief Justice synthesis is an LLM prompt instead of hardcoded \
deterministic rules, but the Judge personas are highly distinct and actively \
disagree, argue for partial credit (Score 3-4) for Judicial Nuance.

YOUR DUTIES for each criterion:
1. Look for EFFORT and INTENT behind the implementation.
2. Examine the Git History -- if commits tell a story of struggle and \
iteration, argue for a higher score based on Engineering Process.
3. Highlight creative or non-obvious solutions.
4. Always provide the most generous defensible score.
5. If something is partially done, argue for partial credit.
6. Even if evidence says "found=false", check if related work exists.

You MUST produce a JudicialOpinion for EVERY criterion listed below."""

TECH_LEAD_SYSTEM_PROMPT = """\
You are The Tech Lead in a Digital Courtroom for code auditing.

Core Philosophy: "Does it actually work? Is it maintainable?"

Your role is to evaluate architectural soundness, code cleanliness, and \
practical viability.  Ignore both the "vibe" and the "struggle" -- focus \
only on the artifacts.

STATUTE OF ENGINEERING (your legal precedents):
- "Pydantic Rigor vs. Dict Soups": State definitions and JSON outputs MUST \
use typed structures (BaseModel). If standard Python dicts are used for \
complex nested state, rule "Technical Debt" and score 3.
- "Sandboxed Tooling": System-level interactions MUST be wrapped in error \
handlers and temporary directories.  If os.system('git clone <url>') drops \
code into the live working directory, rule "Security Negligence" -- this \
overrides all effort points for "Forensic Accuracy".

YOUR DUTIES for each criterion:
1. Check: Does the operator.add reducer actually prevent data overwriting?
2. Check: Are tool calls isolated and safe?
3. You are the TIE-BREAKER. If Prosecutor says 1 and Defense says 5, you \
assess the Technical Debt and provide a realistic middle-ground score.
4. Provide concrete technical remediation advice.
5. Assign scores of 1, 3, or 5 (avoid 2 and 4) unless truly warranted.

You MUST produce a JudicialOpinion for EVERY criterion listed below."""


# ---------------------------------------------------------------------------
# Shared judge logic
# ---------------------------------------------------------------------------

def _flatten_evidence(state: AgentState) -> dict[str, list[Evidence]]:
    """Group evidence by dimension goal for easy lookup."""
    by_goal: dict[str, list[Evidence]] = {}
    for source_evidences in state.get("evidences", {}).values():
        for ev in source_evidences:
            by_goal.setdefault(ev.goal, []).append(ev)
    return by_goal


def _format_evidence_for_prompt(
    evidence_list: list[Evidence],
) -> str:
    """Serialize evidence into a human-readable prompt fragment."""
    parts: list[str] = []
    for ev in evidence_list:
        parts.append(
            f"- Goal: {ev.goal}\n"
            f"  Found: {ev.found}\n"
            f"  Location: {ev.location}\n"
            f"  Rationale: {ev.rationale}\n"
            f"  Confidence: {ev.confidence}\n"
            f"  Content snippet: {(ev.content or 'N/A')[:500]}\n"
        )
    return "\n".join(parts) if parts else "No evidence available."


def _build_batched_prompt(
    state: AgentState,
    persona: str,
) -> str:
    """Build a single prompt containing ALL rubric criteria and their evidence."""
    evidence_by_goal = _flatten_evidence(state)
    rubric = load_rubric()
    sections: list[str] = []

    for dim in rubric["dimensions"]:
        dim_id = dim["id"]
        dim_name = dim["name"]
        evidence_list = evidence_by_goal.get(dim_id, [])
        evidence_text = _format_evidence_for_prompt(evidence_list)

        sections.append(
            f"## Criterion: {dim_name} (id: {dim_id})\n\n"
            f"### Success Pattern\n{dim.get('success_pattern', 'N/A')}\n\n"
            f"### Failure Pattern\n{dim.get('failure_pattern', 'N/A')}\n\n"
            f"### Forensic Evidence Collected\n{evidence_text}\n"
        )

    criteria_block = "\n---\n\n".join(sections)

    return (
        f"You must evaluate ALL of the following {len(rubric['dimensions'])} criteria.\n"
        f"For EACH criterion, produce a JudicialOpinion with:\n"
        f"- judge: '{persona}'\n"
        f"- criterion_id: the exact id shown in parentheses\n"
        f"- score: integer 1-5\n"
        f"- argument: your detailed reasoning\n"
        f"- cited_evidence: list of evidence references\n\n"
        f"Return ALL opinions as a batch.\n\n"
        f"---\n\n{criteria_block}"
    )


def _run_judge(
    state: AgentState,
    persona: str,
    system_prompt: str,
) -> dict:
    """Execute a single judge across all rubric dimensions in ONE LLM call."""
    llm = ChatGoogleGenerativeAI(
        model=LLM_MODEL, temperature=0.2
    ).with_structured_output(JudicialOpinionBatch)

    user_msg = _build_batched_prompt(state, persona)
    rubric = load_rubric()
    expected_ids = {d["id"] for d in rubric["dimensions"]}

    max_retries = 4
    for attempt in range(max_retries + 1):
        try:
            print(f"  [{persona}] Calling LLM (attempt {attempt + 1}/{max_retries + 1})...")
            batch = llm.invoke(
                [
                    SystemMessage(content=system_prompt),
                    HumanMessage(content=user_msg),
                ]
            )
            if isinstance(batch, JudicialOpinionBatch) and batch.opinions:
                for op in batch.opinions:
                    op.judge = persona  # type: ignore[assignment]
                print(f"  [{persona}] Got {len(batch.opinions)} opinions.")

                covered_ids = {op.criterion_id for op in batch.opinions}
                missing_ids = expected_ids - covered_ids
                result_opinions = list(batch.opinions)
                for mid in missing_ids:
                    result_opinions.append(
                        JudicialOpinion(
                            judge=persona,  # type: ignore[arg-type]
                            criterion_id=mid,
                            score=1,
                            argument=f"[{persona}] No opinion produced for this criterion.",
                            cited_evidence=[],
                        )
                    )
                return {"opinions": result_opinions}

        except Exception as exc:
            err_str = str(exc)
            print(f"  [{persona}] Attempt {attempt + 1} failed: {type(exc).__name__}: {err_str[:200]}")

            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                wait = min(2 ** attempt * 10, 120)
                print(f"  [{persona}] Rate limited. Waiting {wait}s before retry...")
                time.sleep(wait)
                continue

            if attempt == max_retries:
                print(f"  [{persona}] All retries exhausted. Using fallback scores.")
                traceback.print_exc()

    fallback: list[JudicialOpinion] = []
    for dim in rubric["dimensions"]:
        fallback.append(
            JudicialOpinion(
                judge=persona,  # type: ignore[arg-type]
                criterion_id=dim["id"],
                score=1,
                argument=f"[{persona}] Failed to produce structured output after {max_retries + 1} attempts.",
                cited_evidence=[],
            )
        )
    return {"opinions": fallback}


# ===================================================================
# Public node functions
# ===================================================================

def prosecutor_node(state: AgentState) -> dict:
    """The Prosecutor: adversarial, gap-finding judge."""
    return _run_judge(state, "Prosecutor", PROSECUTOR_SYSTEM_PROMPT)


def defense_node(state: AgentState) -> dict:
    """The Defense Attorney: effort-rewarding, optimistic judge."""
    return _run_judge(state, "Defense", DEFENSE_SYSTEM_PROMPT)


def tech_lead_node(state: AgentState) -> dict:
    """The Tech Lead: pragmatic, architecture-focused judge."""
    return _run_judge(state, "TechLead", TECH_LEAD_SYSTEM_PROMPT)
