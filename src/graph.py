"""Automaton Auditor -- LangGraph StateGraph assembly.

Architecture
============
Two parallel fan-out / fan-in stages:

  START
    -> ContextBuilder
    -> [RepoInvestigator || DocAnalyst || VisionInspector]   (fan-out)
    -> EvidenceAggregator                                    (fan-in)
    -> [Prosecutor || Defense || TechLead]                   (fan-out)
    -> ChiefJustice                                          (fan-in)
    -> ReportRenderer
    -> END

Conditional edges handle missing evidence or node failures.
"""

from __future__ import annotations

import argparse

from dotenv import load_dotenv
from langgraph.graph import END, START, StateGraph

from src.config import load_rubric
from src.nodes.detectives import (
    doc_analyst_node,
    evidence_aggregator_node,
    repo_investigator_node,
    vision_inspector_node,
)
from src.nodes.judges import defense_node, prosecutor_node, tech_lead_node
from src.nodes.justice import chief_justice_node, report_renderer_node
from src.state import AgentState


# ---------------------------------------------------------------------------
# Lightweight wrapper nodes
# ---------------------------------------------------------------------------

def context_builder_node(state: AgentState) -> dict:
    """Load the rubric and inject dimensions into state."""
    rubric = load_rubric()
    return {"rubric_dimensions": rubric["dimensions"]}


def _check_evidence(state: AgentState) -> list[str]:
    """Conditional edge: fan-out to judges or skip to renderer."""
    evidences = state.get("evidences", {})
    total = sum(len(v) for v in evidences.values())
    if total == 0:
        return ["report_renderer"]
    return ["prosecutor", "defense", "tech_lead"]


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------

def build_graph() -> StateGraph:
    """Construct and return the compiled Automaton Auditor graph."""

    builder = StateGraph(AgentState)

    # -- add nodes -------------------------------------------------------
    builder.add_node("context_builder", context_builder_node)
    builder.add_node("repo_investigator", repo_investigator_node)
    builder.add_node("doc_analyst", doc_analyst_node)
    builder.add_node("vision_inspector", vision_inspector_node)
    builder.add_node("evidence_aggregator", evidence_aggregator_node)
    builder.add_node("prosecutor", prosecutor_node)
    builder.add_node("defense", defense_node)
    builder.add_node("tech_lead", tech_lead_node)
    builder.add_node("chief_justice", chief_justice_node)
    builder.add_node("report_renderer", report_renderer_node)

    # -- Detective fan-out -----------------------------------------------
    builder.add_edge(START, "context_builder")
    builder.add_edge("context_builder", "repo_investigator")
    builder.add_edge("context_builder", "doc_analyst")
    builder.add_edge("context_builder", "vision_inspector")

    # -- Detective fan-in ------------------------------------------------
    builder.add_edge("repo_investigator", "evidence_aggregator")
    builder.add_edge("doc_analyst", "evidence_aggregator")
    builder.add_edge("vision_inspector", "evidence_aggregator")

    # -- Conditional fan-out to judges (or skip to renderer) -------------
    builder.add_conditional_edges(
        "evidence_aggregator",
        _check_evidence,
        ["prosecutor", "defense", "tech_lead", "report_renderer"],
    )

    # -- Judge fan-in ----------------------------------------------------
    builder.add_edge("prosecutor", "chief_justice")
    builder.add_edge("defense", "chief_justice")
    builder.add_edge("tech_lead", "chief_justice")

    # -- Final -----------------------------------------------------------
    builder.add_edge("chief_justice", "report_renderer")
    builder.add_edge("report_renderer", END)

    return builder.compile()


# Compiled graph singleton
graph = build_graph()


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    load_dotenv()

    parser = argparse.ArgumentParser(
        description="Automaton Auditor -- run the Digital Courtroom swarm"
    )
    parser.add_argument(
        "--repo",
        required=True,
        help="GitHub repository URL to audit",
    )
    parser.add_argument(
        "--pdf",
        default="",
        help="Path to the PDF report (optional)",
    )
    parser.add_argument(
        "--output-dir",
        default="audit/report_onself_generated",
        help="Directory to write the audit report",
    )
    args = parser.parse_args()

    initial_state: AgentState = {
        "repo_url": args.repo,
        "pdf_path": args.pdf,
        "rubric_dimensions": [],
        "repo_path": "",
        "evidences": {},
        "opinions": [],
        "final_report": None,
    }

    print(f"Auditing repository: {args.repo}")
    if args.pdf:
        print(f"PDF report: {args.pdf}")
    print("Running the Digital Courtroom swarm...\n")

    result = graph.invoke(initial_state)

    report = result.get("final_report")
    if report:
        print(f"\nOverall Score: {report.overall_score}/5.0")
        print(f"Report written to: {args.output_dir}/report.md")
    else:
        print("\nNo report was generated.")


if __name__ == "__main__":
    main()
