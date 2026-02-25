"""Detective-layer nodes: RepoInvestigator, DocAnalyst, VisionInspector,
and the EvidenceAggregator synchronisation node.

Each detective outputs structured Evidence objects without forming opinions.
"""

from __future__ import annotations

import base64
import json
import os
import traceback
from typing import Any

from langchain_openai import ChatOpenAI

from src.config import get_dimensions_for_artifact, load_rubric
from src.state import AgentState, Evidence
from src.tools.doc_tools import (
    cross_reference_paths,
    extract_file_paths_from_chunks,
    extract_images_from_pdf,
    ingest_pdf,
    search_keywords,
)
from src.tools.repo_tools import (
    analyze_graph_structure,
    check_file_exists,
    clone_repo,
    extract_git_history,
    extract_judge_prompts,
    read_file,
    scan_directory,
)


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _safe(func, *args, **kwargs):
    """Call *func* and return its result, or an error dict on failure."""
    try:
        return func(*args, **kwargs)
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


# ===================================================================
# Node: RepoInvestigator
# ===================================================================

def repo_investigator_node(state: AgentState) -> dict:
    """Clone the target repo and collect forensic evidence for every
    ``github_repo`` rubric dimension."""

    repo_url: str = state["repo_url"]
    evidences: list[Evidence] = []

    # -- clone -----------------------------------------------------------
    try:
        repo_path, tmp_handle = clone_repo(repo_url)
    except RuntimeError as exc:
        evidences.append(
            Evidence(
                goal="clone_repo",
                found=False,
                content=str(exc),
                location=repo_url,
                rationale="Git clone failed; cannot perform any repo analysis.",
                confidence=1.0,
            )
        )
        return {"evidences": {"repo": evidences}, "repo_path": ""}

    all_files = scan_directory(repo_path, "*.py")

    # -- per-dimension evidence collection --------------------------------
    dimensions = get_dimensions_for_artifact("github_repo")

    for dim in dimensions:
        dim_id = dim["id"]
        try:
            if dim_id == "git_forensic_analysis":
                evidences.extend(_collect_git_evidence(repo_path, dim))
            elif dim_id == "state_management_rigor":
                evidences.extend(_collect_state_evidence(repo_path, dim, all_files))
            elif dim_id == "graph_orchestration":
                evidences.extend(_collect_graph_evidence(repo_path, dim))
            elif dim_id == "safe_tool_engineering":
                evidences.extend(_collect_safety_evidence(repo_path, dim))
            elif dim_id == "structured_output_enforcement":
                evidences.extend(_collect_structured_output_evidence(repo_path, dim))
            elif dim_id == "judicial_nuance":
                evidences.extend(_collect_judicial_nuance_evidence(repo_path, dim))
            elif dim_id == "chief_justice_synthesis":
                evidences.extend(_collect_chief_justice_evidence(repo_path, dim))
            else:
                evidences.append(
                    Evidence(
                        goal=dim_id,
                        found=False,
                        content=None,
                        location="N/A",
                        rationale=f"No handler for dimension {dim_id}",
                        confidence=0.0,
                    )
                )
        except Exception:
            evidences.append(
                Evidence(
                    goal=dim_id,
                    found=False,
                    content=traceback.format_exc(),
                    location="N/A",
                    rationale="Exception during evidence collection.",
                    confidence=0.0,
                )
            )

    return {"evidences": {"repo": evidences}, "repo_path": repo_path}


# ---------------------------------------------------------------------------
# Per-dimension evidence helpers
# ---------------------------------------------------------------------------

def _collect_git_evidence(repo_path: str, dim: dict) -> list[Evidence]:
    history = extract_git_history(repo_path)
    count = history.get("count", 0)
    commits = history.get("commits", [])
    messages = [c["message"] for c in commits]
    summary = "\n".join(
        f"{c['short_hash']} {c['timestamp']} {c['message']}" for c in commits
    )

    progression_keywords = {
        "setup": ["setup", "init", "environment", "config", "install", "pyproject"],
        "tools": ["tool", "parse", "ast", "clone", "pdf", "doc"],
        "graph": ["graph", "node", "edge", "langgraph", "state", "judge", "justice"],
    }
    stages_found: list[str] = []
    for stage, kws in progression_keywords.items():
        if any(kw in m.lower() for m in messages for kw in kws):
            stages_found.append(stage)

    found = count > 3 and len(stages_found) >= 2
    return [
        Evidence(
            goal="git_forensic_analysis",
            found=found,
            content=summary[:2000],
            location="git log",
            rationale=(
                f"Found {count} commits covering stages: {stages_found}. "
                + ("Progression story detected." if found else "Weak or monolithic history.")
            ),
            confidence=0.9 if found else 0.5,
        )
    ]


def _collect_state_evidence(repo_path: str, dim: dict, all_files: list[str]) -> list[Evidence]:
    findings = analyze_graph_structure(repo_path)
    state_file = read_file(repo_path, "src/state.py")
    if state_file is None:
        state_file = read_file(repo_path, "src/graph.py")

    has_pydantic = len(findings["pydantic_models"]) > 0
    has_typeddict = len(findings["typeddict_classes"]) > 0
    has_reducers = len(findings["operator_reducers"]) > 0

    found = (has_pydantic or has_typeddict) and has_reducers
    content_parts = []
    if state_file:
        content_parts.append(state_file[:2000])
    content_parts.append(f"Pydantic models: {findings['pydantic_models']}")
    content_parts.append(f"TypedDict classes: {findings['typeddict_classes']}")
    content_parts.append(f"Operator reducers: {findings['operator_reducers']}")

    return [
        Evidence(
            goal="state_management_rigor",
            found=found,
            content="\n".join(content_parts)[:3000],
            location="src/state.py",
            rationale=(
                f"Pydantic={has_pydantic}, TypedDict={has_typeddict}, Reducers={has_reducers}. "
                + ("Typed state with reducers confirmed." if found else "Missing typed state or reducers.")
            ),
            confidence=0.95 if found else 0.4,
        )
    ]


def _collect_graph_evidence(repo_path: str, dim: dict) -> list[Evidence]:
    findings = analyze_graph_structure(repo_path)
    graph_source = read_file(repo_path, "src/graph.py")

    sg = findings["state_graph_found"]
    edges = findings["add_edge_calls"]
    cond_edges = findings["add_conditional_edges_calls"]

    edge_targets = [e["call"] for e in edges]
    has_parallel = len(edges) >= 4

    found = sg and has_parallel
    return [
        Evidence(
            goal="graph_orchestration",
            found=found,
            content=(graph_source or "")[:3000],
            location="src/graph.py",
            rationale=(
                f"StateGraph={sg}, edges={len(edges)}, conditional_edges={len(cond_edges)}. "
                + ("Parallel fan-out/fan-in detected." if found else "Linear or missing graph.")
            ),
            confidence=0.9 if found else 0.3,
        )
    ]


def _collect_safety_evidence(repo_path: str, dim: dict) -> list[Evidence]:
    findings = analyze_graph_structure(repo_path)

    has_tempfile = findings["tempfile_usage"]
    has_subprocess = findings["subprocess_usage"]
    has_os_system = len(findings["os_system_calls"]) > 0

    tools_source = read_file(repo_path, "src/tools/repo_tools.py")

    found = has_tempfile and has_subprocess and not has_os_system
    return [
        Evidence(
            goal="safe_tool_engineering",
            found=found,
            content=(tools_source or "")[:2000],
            location="src/tools/repo_tools.py",
            rationale=(
                f"tempfile={has_tempfile}, subprocess={has_subprocess}, "
                f"os.system={has_os_system}. "
                + ("Safe sandboxed tooling." if found else "Security concerns detected.")
            ),
            confidence=0.95 if found else 0.3,
        )
    ]


def _collect_structured_output_evidence(repo_path: str, dim: dict) -> list[Evidence]:
    findings = analyze_graph_structure(repo_path)
    judges_source = read_file(repo_path, "src/nodes/judges.py")

    so_calls = findings["structured_output_calls"]
    bt_calls = findings["bind_tools_calls"]
    found = len(so_calls) > 0 or len(bt_calls) > 0

    return [
        Evidence(
            goal="structured_output_enforcement",
            found=found,
            content=(judges_source or "")[:2000],
            location="src/nodes/judges.py",
            rationale=(
                f"with_structured_output calls: {len(so_calls)}, "
                f"bind_tools calls: {len(bt_calls)}. "
                + ("Structured output enforced." if found else "No structured output enforcement.")
            ),
            confidence=0.9 if found else 0.2,
        )
    ]


def _collect_judicial_nuance_evidence(repo_path: str, dim: dict) -> list[Evidence]:
    prompts = extract_judge_prompts(repo_path)
    judges_source = read_file(repo_path, "src/nodes/judges.py")

    has_distinct = (
        prompts["prosecutor"] is not None
        and prompts["defense"] is not None
        and prompts["tech_lead"] is not None
    )
    found = has_distinct or (judges_source is not None and len(judges_source) > 200)

    return [
        Evidence(
            goal="judicial_nuance",
            found=found,
            content=(judges_source or "")[:3000],
            location="src/nodes/judges.py",
            rationale=(
                f"Distinct prompts found: {list(k for k, v in prompts.items() if v)}. "
                + ("Distinct personas confirmed." if found else "No persona separation detected.")
            ),
            confidence=0.8 if found else 0.2,
        )
    ]


def _collect_chief_justice_evidence(repo_path: str, dim: dict) -> list[Evidence]:
    justice_source = read_file(repo_path, "src/nodes/justice.py")

    deterministic_signals = []
    if justice_source:
        for signal in [
            "security_override", "fact_supremacy", "functionality_weight",
            "variance", "dissent", "cap", "override", "if ",
        ]:
            if signal.lower() in justice_source.lower():
                deterministic_signals.append(signal)

    found = justice_source is not None and len(deterministic_signals) >= 3
    return [
        Evidence(
            goal="chief_justice_synthesis",
            found=found,
            content=(justice_source or "")[:3000],
            location="src/nodes/justice.py",
            rationale=(
                f"Deterministic signals found: {deterministic_signals}. "
                + ("Hardcoded rules confirmed." if found else "Missing or LLM-only synthesis.")
            ),
            confidence=0.85 if found else 0.2,
        )
    ]


# ===================================================================
# Node: DocAnalyst
# ===================================================================

def doc_analyst_node(state: AgentState) -> dict:
    """Ingest the PDF report and collect evidence for ``pdf_report`` dimensions."""

    pdf_path: str = state.get("pdf_path", "")
    evidences: list[Evidence] = []

    if not pdf_path or not os.path.isfile(pdf_path):
        evidences.append(
            Evidence(
                goal="pdf_ingestion",
                found=False,
                content=None,
                location=pdf_path or "N/A",
                rationale="PDF file not found or not provided.",
                confidence=1.0,
            )
        )
        return {"evidences": {"doc": evidences}}

    try:
        chunks = ingest_pdf(pdf_path)
    except RuntimeError as exc:
        evidences.append(
            Evidence(
                goal="pdf_ingestion",
                found=False,
                content=str(exc),
                location=pdf_path,
                rationale="Failed to parse PDF.",
                confidence=1.0,
            )
        )
        return {"evidences": {"doc": evidences}}

    dimensions = get_dimensions_for_artifact("pdf_report")

    for dim in dimensions:
        dim_id = dim["id"]
        try:
            if dim_id == "theoretical_depth":
                evidences.extend(_collect_theoretical_depth(chunks, dim))
            elif dim_id == "report_accuracy":
                evidences.extend(
                    _collect_report_accuracy(chunks, dim, state)
                )
            else:
                evidences.append(
                    Evidence(
                        goal=dim_id,
                        found=False,
                        content=None,
                        location="PDF",
                        rationale=f"No handler for dimension {dim_id}",
                        confidence=0.0,
                    )
                )
        except Exception:
            evidences.append(
                Evidence(
                    goal=dim_id,
                    found=False,
                    content=traceback.format_exc(),
                    location="PDF",
                    rationale="Exception during evidence collection.",
                    confidence=0.0,
                )
            )

    return {"evidences": {"doc": evidences}}


def _collect_theoretical_depth(
    chunks: list[dict], dim: dict
) -> list[Evidence]:
    target_terms = [
        "Dialectical Synthesis",
        "Fan-In",
        "Fan-Out",
        "Metacognition",
        "State Synchronization",
    ]
    results = search_keywords(chunks, target_terms)

    substantive_terms: list[str] = []
    buzzword_terms: list[str] = []
    details: list[str] = []

    for term, matches in results.items():
        if not matches:
            buzzword_terms.append(f"{term} (not found)")
            continue
        total_context = " ".join(m["context"] for m in matches)
        if len(total_context) > 100:
            substantive_terms.append(term)
            details.append(f"{term}: {matches[0]['context'][:300]}")
        else:
            buzzword_terms.append(f"{term} (shallow)")

    found = len(substantive_terms) >= 2
    return [
        Evidence(
            goal="theoretical_depth",
            found=found,
            content="\n---\n".join(details)[:3000] if details else None,
            location="PDF report",
            rationale=(
                f"Substantive: {substantive_terms}. "
                f"Shallow/Missing: {buzzword_terms}. "
                + ("Deep explanations present." if found else "Mostly buzzwords or missing terms.")
            ),
            confidence=0.8 if found else 0.4,
        )
    ]


def _collect_report_accuracy(
    chunks: list[dict], dim: dict, state: AgentState
) -> list[Evidence]:
    claimed = extract_file_paths_from_chunks(chunks)

    repo_path = state.get("repo_path", "")
    if repo_path:
        existing = scan_directory(repo_path, "*")
    else:
        existing = []

    xref = cross_reference_paths(claimed, existing)
    verified = xref["verified"]
    hallucinated = xref["hallucinated"]

    found = len(hallucinated) == 0 and len(verified) > 0
    return [
        Evidence(
            goal="report_accuracy",
            found=found,
            content=json.dumps(xref, indent=2)[:2000],
            location="PDF report vs repo",
            rationale=(
                f"Verified paths: {len(verified)}, "
                f"Hallucinated paths: {len(hallucinated)}. "
                + ("All paths verified." if found else f"Hallucinated: {hallucinated[:5]}")
            ),
            confidence=0.9 if found else 0.5,
        )
    ]


# ===================================================================
# Node: VisionInspector
# ===================================================================

def vision_inspector_node(state: AgentState) -> dict:
    """Extract images from the PDF and analyse architectural diagrams."""

    pdf_path: str = state.get("pdf_path", "")
    evidences: list[Evidence] = []

    if not pdf_path or not os.path.isfile(pdf_path):
        evidences.append(
            Evidence(
                goal="swarm_visual",
                found=False,
                content=None,
                location="N/A",
                rationale="No PDF available for image extraction.",
                confidence=1.0,
            )
        )
        return {"evidences": {"vision": evidences}}

    image_paths = extract_images_from_pdf(pdf_path)
    if not image_paths:
        evidences.append(
            Evidence(
                goal="swarm_visual",
                found=False,
                content=None,
                location=pdf_path,
                rationale="No images could be extracted from the PDF.",
                confidence=0.8,
            )
        )
        return {"evidences": {"vision": evidences}}

    try:
        analysis = _analyze_diagrams_with_vision(image_paths)
        evidences.append(
            Evidence(
                goal="swarm_visual",
                found=analysis.get("has_parallel_flow", False),
                content=json.dumps(analysis, indent=2)[:3000],
                location=pdf_path,
                rationale=analysis.get("rationale", "Vision analysis completed."),
                confidence=analysis.get("confidence", 0.5),
            )
        )
    except Exception:
        evidences.append(
            Evidence(
                goal="swarm_visual",
                found=False,
                content=traceback.format_exc(),
                location=pdf_path,
                rationale="Vision analysis failed.",
                confidence=0.1,
            )
        )

    return {"evidences": {"vision": evidences}}


def _analyze_diagrams_with_vision(image_paths: list[str]) -> dict:
    """Send images to a multimodal LLM for architectural analysis."""
    from src.config import VISION_MODEL

    llm = ChatOpenAI(model=VISION_MODEL)

    image_contents = []
    for img_path in image_paths[:5]:
        with open(img_path, "rb") as f:
            b64 = base64.b64encode(f.read()).decode()
        ext = img_path.rsplit(".", 1)[-1].lower()
        mime = {"png": "image/png", "jpg": "image/jpeg", "jpeg": "image/jpeg"}.get(
            ext, "image/png"
        )
        image_contents.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:{mime};base64,{b64}"},
            }
        )

    prompt = (
        "You are an expert software architecture reviewer. "
        "Analyze the following diagram(s) extracted from a project report. "
        "For each diagram determine:\n"
        "1. Type: Is it an accurate LangGraph State Machine diagram, "
        "a sequence diagram, or just generic flowchart boxes?\n"
        "2. Does it show parallel fan-out/fan-in for Detectives AND Judges?\n"
        "3. Does it show: START -> [Detectives in parallel] -> "
        "Evidence Aggregation -> [Judges in parallel] -> "
        "Chief Justice Synthesis -> END?\n\n"
        "Respond in JSON with keys: diagram_type (str), "
        "has_parallel_flow (bool), description (str), rationale (str), "
        "confidence (float 0-1)."
    )

    messages = [
        {
            "role": "user",
            "content": [{"type": "text", "text": prompt}] + image_contents,
        }
    ]

    response = llm.invoke(messages)
    try:
        return json.loads(response.content)
    except (json.JSONDecodeError, TypeError):
        return {
            "diagram_type": "unknown",
            "has_parallel_flow": False,
            "description": response.content[:1000] if response.content else "",
            "rationale": "Could not parse structured response from vision model.",
            "confidence": 0.3,
        }


# ===================================================================
# Node: EvidenceAggregator  (synchronisation / fan-in)
# ===================================================================

def evidence_aggregator_node(state: AgentState) -> dict:
    """Merge all detective evidence and pass through.

    The ``operator.ior`` reducer on ``evidences`` already merges the dicts
    contributed by each detective.  This node simply validates completeness.
    """
    evidences = state.get("evidences", {})
    rubric = load_rubric()
    all_dim_ids = {d["id"] for d in rubric["dimensions"]}

    covered = set()
    for source_evidences in evidences.values():
        for ev in source_evidences:
            covered.add(ev.goal)

    missing = all_dim_ids - covered
    if missing:
        filler: list[Evidence] = []
        for m in missing:
            filler.append(
                Evidence(
                    goal=m,
                    found=False,
                    content=None,
                    location="N/A",
                    rationale="No detective collected evidence for this dimension.",
                    confidence=0.0,
                )
            )
        return {"evidences": {"aggregator_fill": filler}}

    return {}
