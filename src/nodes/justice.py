"""Supreme-Court layer: ChiefJustice synthesis engine and report renderer.

The ChiefJustice resolves dialectical conflict using **deterministic Python
logic** (not an LLM prompt).  Named rules are applied in priority order:

1. Security Override   -- security flaws cap the score at 3
2. Fact Supremacy      -- forensic facts overrule judicial opinion
3. Functionality Weight -- Tech Lead carries the most weight on architecture
4. Variance Re-evaluation -- score spread > 2 triggers dissent + re-weighting
"""

from __future__ import annotations

import os
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from src.config import get_synthesis_rules, load_rubric
from src.state import (
    AgentState,
    AuditReport,
    CriterionResult,
    Evidence,
    JudicialOpinion,
)


# ---------------------------------------------------------------------------
# Deterministic conflict-resolution helpers
# ---------------------------------------------------------------------------

_SECURITY_KEYWORDS = [
    "security", "os.system", "shell injection", "unsanitized",
    "security negligence", "vulnerability",
]

_FACT_OVERRIDE_KEYWORDS = [
    "hallucination", "does not exist", "not found", "found=false",
    "missing", "no evidence",
]


def _prosecutor_flags_security(opinions: list[JudicialOpinion]) -> bool:
    """True when the Prosecutor's argument mentions a confirmed security flaw."""
    for op in opinions:
        if op.judge == "Prosecutor":
            lower = op.argument.lower()
            if any(kw in lower for kw in _SECURITY_KEYWORDS):
                return True
    return False


def _defense_overruled_by_facts(
    opinions: list[JudicialOpinion],
    evidence: list[Evidence],
) -> bool:
    """True when the Defense claims merit but detective evidence is negative."""
    defense_score = next(
        (op.score for op in opinions if op.judge == "Defense"), None
    )
    if defense_score is None or defense_score <= 2:
        return False

    all_missing = all(not ev.found for ev in evidence)
    if all_missing and evidence:
        return True

    for op in opinions:
        if op.judge == "Defense":
            lower = op.argument.lower()
            if any(kw in lower for kw in _FACT_OVERRIDE_KEYWORDS):
                return True
    return False


def _score_variance(opinions: list[JudicialOpinion]) -> float:
    scores = [op.score for op in opinions]
    if len(scores) < 2:
        return 0.0
    return max(scores) - min(scores)


def _weighted_score(opinions: list[JudicialOpinion], criterion_id: str) -> float:
    """Compute a weighted average.

    Weights: TechLead 0.45, Prosecutor 0.30, Defense 0.25
    For architecture-related criteria the TechLead weight rises to 0.55.
    """
    architecture_criteria = {"graph_orchestration", "state_management_rigor"}
    if criterion_id in architecture_criteria:
        weights = {"TechLead": 0.55, "Prosecutor": 0.25, "Defense": 0.20}
    else:
        weights = {"TechLead": 0.45, "Prosecutor": 0.30, "Defense": 0.25}

    total = 0.0
    w_sum = 0.0
    for op in opinions:
        w = weights.get(op.judge, 0.33)
        total += op.score * w
        w_sum += w

    return round(total / w_sum, 2) if w_sum else 3.0


# ===================================================================
# Node: ChiefJustice
# ===================================================================

def chief_justice_node(state: AgentState) -> dict:
    """Synthesise the judicial opinions into a final AuditReport.

    Applies deterministic rules -- no LLM involved.
    """
    rubric = load_rubric()
    synthesis_rules = get_synthesis_rules()
    all_opinions = state.get("opinions", [])
    all_evidence = state.get("evidences", {})

    opinions_by_criterion: dict[str, list[JudicialOpinion]] = defaultdict(list)
    for op in all_opinions:
        opinions_by_criterion[op.criterion_id].append(op)

    evidence_by_goal: dict[str, list[Evidence]] = {}
    for source_evidences in all_evidence.values():
        for ev in source_evidences:
            evidence_by_goal.setdefault(ev.goal, []).append(ev)

    criteria_results: list[CriterionResult] = []

    for dim in rubric["dimensions"]:
        dim_id = dim["id"]
        dim_name = dim["name"]
        ops = opinions_by_criterion.get(dim_id, [])
        evs = evidence_by_goal.get(dim_id, [])

        if not ops:
            criteria_results.append(
                CriterionResult(
                    dimension_id=dim_id,
                    dimension_name=dim_name,
                    final_score=1,
                    judge_opinions=[],
                    dissent_summary="No judicial opinions were produced for this criterion.",
                    remediation="Ensure all three judges evaluate this criterion.",
                )
            )
            continue

        # -- Step 1: compute base weighted score -------------------------
        base_score = _weighted_score(ops, dim_id)

        # -- Step 2: apply deterministic rules ---------------------------
        final_score = round(base_score)
        dissent: str | None = None
        remediation_parts: list[str] = []

        # Rule: Security Override
        if _prosecutor_flags_security(ops):
            final_score = min(final_score, 3)
            remediation_parts.append(
                "SECURITY: The Prosecutor identified security concerns. "
                "Audit all shell/subprocess calls and ensure sandboxing."
            )

        # Rule: Fact Supremacy
        if _defense_overruled_by_facts(ops, evs):
            defense_op = next((o for o in ops if o.judge == "Defense"), None)
            if defense_op and defense_op.score > final_score:
                final_score = min(final_score, 3)
            remediation_parts.append(
                "EVIDENCE: The Defense's claims were overruled because forensic "
                "evidence does not support them. Verify that the artifacts exist."
            )

        # Rule: Functionality Weight (already baked into _weighted_score)

        # Rule: Variance Re-evaluation
        variance = _score_variance(ops)
        if variance > 2:
            scores_desc = ", ".join(f"{o.judge}={o.score}" for o in ops)
            dissent = (
                f"High disagreement (variance={variance}): {scores_desc}. "
            )
            pro = next((o for o in ops if o.judge == "Prosecutor"), None)
            defense = next((o for o in ops if o.judge == "Defense"), None)
            if pro and defense:
                dissent += (
                    f"The Prosecutor argued: '{pro.argument[:200]}...' "
                    f"The Defense countered: '{defense.argument[:200]}...' "
                )
            remediation_parts.append(
                "DISSENT: Significant disagreement among judges. "
                "Review the cited evidence carefully and address the specific "
                "gaps noted by the Prosecutor while preserving the strengths "
                "acknowledged by the Defense."
            )

        # Clamp score
        final_score = max(1, min(5, final_score))

        # Build remediation
        tech_lead_op = next((o for o in ops if o.judge == "TechLead"), None)
        if tech_lead_op:
            remediation_parts.insert(
                0,
                f"Tech Lead assessment: {tech_lead_op.argument[:300]}",
            )
        remediation = "\n".join(remediation_parts) if remediation_parts else (
            "No specific remediation needed -- criterion met."
        )

        criteria_results.append(
            CriterionResult(
                dimension_id=dim_id,
                dimension_name=dim_name,
                final_score=final_score,
                judge_opinions=ops,
                dissent_summary=dissent,
                remediation=remediation,
            )
        )

    # -- Aggregate -------------------------------------------------------
    scores = [cr.final_score for cr in criteria_results]
    overall = round(statistics.mean(scores), 2) if scores else 0.0

    exec_summary = _build_executive_summary(criteria_results, overall)
    remediation_plan = _build_remediation_plan(criteria_results)

    report = AuditReport(
        repo_url=state.get("repo_url", ""),
        executive_summary=exec_summary,
        overall_score=overall,
        criteria=criteria_results,
        remediation_plan=remediation_plan,
    )

    return {"final_report": report}


# ---------------------------------------------------------------------------
# Summary builders
# ---------------------------------------------------------------------------

def _build_executive_summary(
    criteria: list[CriterionResult], overall: float
) -> str:
    lines = [
        f"Overall Score: {overall}/5.0",
        "",
    ]
    for cr in criteria:
        tag = "PASS" if cr.final_score >= 3 else "FAIL"
        lines.append(f"- [{tag}] {cr.dimension_name}: {cr.final_score}/5")
    return "\n".join(lines)


def _build_remediation_plan(criteria: list[CriterionResult]) -> str:
    sections: list[str] = []
    for cr in sorted(criteria, key=lambda c: c.final_score):
        if cr.final_score >= 5:
            continue
        sections.append(
            f"### {cr.dimension_name} (Score: {cr.final_score}/5)\n\n"
            f"{cr.remediation}\n"
        )
    return "\n".join(sections) if sections else "All criteria met at maximum score."


# ===================================================================
# Node: Report Renderer  (Markdown serialisation)
# ===================================================================

def report_renderer_node(state: AgentState) -> dict:
    """Serialize the AuditReport to a Markdown file."""
    report: AuditReport | None = state.get("final_report")
    if report is None:
        return {}

    md = _render_markdown(report)

    out_dir = state.get("output_dir", "") or "audit/report_onself_generated"
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "report.md")
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(md)

    return {}


def _render_markdown(report: AuditReport) -> str:
    lines: list[str] = []

    lines.append("# Automaton Auditor -- Audit Report")
    lines.append("")
    lines.append(f"**Repository:** {report.repo_url}")
    lines.append(f"**Generated:** {datetime.now(timezone.utc).isoformat()}")
    lines.append(f"**Overall Score:** {report.overall_score}/5.0")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append(report.executive_summary)
    lines.append("")
    lines.append("---")
    lines.append("")

    # Criterion Breakdown
    lines.append("## Criterion Breakdown")
    lines.append("")

    for cr in report.criteria:
        lines.append(f"### {cr.dimension_name}")
        lines.append("")
        lines.append(f"**Score:** {cr.final_score}/5")
        lines.append("")

        # Judge opinions
        lines.append("#### Judge Opinions")
        lines.append("")
        for op in cr.judge_opinions:
            lines.append(f"**{op.judge}** (Score: {op.score}/5)")
            lines.append("")
            lines.append(f"> {op.argument}")
            lines.append("")
            if op.cited_evidence:
                lines.append(f"*Cited evidence:* {', '.join(op.cited_evidence)}")
                lines.append("")

        # Dissent
        if cr.dissent_summary:
            lines.append("#### Dissent")
            lines.append("")
            lines.append(cr.dissent_summary)
            lines.append("")

        # Remediation
        lines.append("#### Remediation")
        lines.append("")
        lines.append(cr.remediation)
        lines.append("")
        lines.append("---")
        lines.append("")

    # Remediation Plan
    lines.append("## Remediation Plan")
    lines.append("")
    lines.append(report.remediation_plan)
    lines.append("")

    return "\n".join(lines)
