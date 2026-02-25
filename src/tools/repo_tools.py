"""Forensic tools for the RepoInvestigator (Code Detective).

All git operations run inside tempfile.TemporaryDirectory() for sandboxing.
subprocess.run() is used exclusively -- never os.system().
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# Repository cloning
# ---------------------------------------------------------------------------


def clone_repo(url: str) -> tuple[str, tempfile.TemporaryDirectory]:
    """Clone *url* into an isolated temporary directory.

    Returns (repo_path, tmp_dir_handle).  The caller must keep the handle
    alive for as long as the repo is needed; when it goes out of scope (or
    `.cleanup()` is called) the directory is removed.
    """
    tmp = tempfile.TemporaryDirectory(prefix="auditor_")
    repo_dir = os.path.join(tmp.name, "repo")
    result = subprocess.run(
        ["git", "clone", "--depth=50", url, repo_dir],
        capture_output=True,
        text=True,
        timeout=120,
    )
    if result.returncode != 0:
        tmp.cleanup()
        raise RuntimeError(
            f"git clone failed (exit {result.returncode}): {result.stderr.strip()}"
        )
    return repo_dir, tmp


# ---------------------------------------------------------------------------
# Git history extraction
# ---------------------------------------------------------------------------


def extract_git_history(repo_path: str) -> dict[str, Any]:
    """Run ``git log`` and return structured commit data."""
    result = subprocess.run(
        [
            "git", "log", "--oneline", "--reverse",
            "--format=%H|%h|%s|%aI",
        ],
        capture_output=True,
        text=True,
        cwd=repo_path,
        timeout=30,
    )
    if result.returncode != 0:
        return {"error": result.stderr.strip(), "commits": [], "count": 0}

    commits = []
    for line in result.stdout.strip().splitlines():
        parts = line.split("|", 3)
        if len(parts) == 4:
            commits.append(
                {
                    "hash": parts[0],
                    "short_hash": parts[1],
                    "message": parts[2],
                    "timestamp": parts[3],
                }
            )
    return {"commits": commits, "count": len(commits)}


# ---------------------------------------------------------------------------
# File-system helpers
# ---------------------------------------------------------------------------


def check_file_exists(repo_path: str, relative: str) -> bool:
    """Check whether *relative* exists inside the cloned repo."""
    target = Path(repo_path) / relative
    return target.exists()


def read_file(repo_path: str, relative: str) -> str | None:
    """Read *relative* from the cloned repo, returning None if missing."""
    target = Path(repo_path) / relative
    if not target.is_file():
        return None
    return target.read_text(encoding="utf-8", errors="replace")


def scan_directory(repo_path: str, pattern: str = "*.py") -> list[str]:
    """Glob for files matching *pattern* under *repo_path*."""
    return [
        str(p.relative_to(repo_path))
        for p in Path(repo_path).rglob(pattern)
    ]


# ---------------------------------------------------------------------------
# AST-based code analysis
# ---------------------------------------------------------------------------


class _StructureVisitor(ast.NodeVisitor):
    """Walk an AST and collect structural signals."""

    def __init__(self) -> None:
        self.classes: list[dict] = []
        self.imports: list[str] = []
        self.calls: list[str] = []
        self.attributes: list[str] = []

    # -- classes ----------------------------------------------------------
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        bases = []
        for b in node.bases:
            if isinstance(b, ast.Name):
                bases.append(b.id)
            elif isinstance(b, ast.Attribute):
                bases.append(ast.unparse(b))
        self.classes.append({"name": node.name, "bases": bases, "lineno": node.lineno})
        self.generic_visit(node)

    # -- imports ----------------------------------------------------------
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append(alias.name)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            self.imports.append(f"{module}.{alias.name}")

    # -- function / method calls -----------------------------------------
    def visit_Call(self, node: ast.Call) -> None:
        try:
            self.calls.append(ast.unparse(node.func))
        except Exception:
            pass
        self.generic_visit(node)

    # -- attribute access ------------------------------------------------
    def visit_Attribute(self, node: ast.Attribute) -> None:
        try:
            self.attributes.append(ast.unparse(node))
        except Exception:
            pass
        self.generic_visit(node)


def analyze_python_file(source: str) -> dict[str, Any] | None:
    """Parse *source* with ``ast`` and return structural signals.

    Returns ``None`` if the file cannot be parsed.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    visitor = _StructureVisitor()
    visitor.visit(tree)
    return {
        "classes": visitor.classes,
        "imports": visitor.imports,
        "calls": visitor.calls,
        "attributes": visitor.attributes,
    }


def analyze_graph_structure(repo_path: str) -> dict[str, Any]:
    """Scan all Python files for LangGraph / Pydantic structural signals."""
    findings: dict[str, Any] = {
        "state_graph_found": False,
        "add_edge_calls": [],
        "add_conditional_edges_calls": [],
        "pydantic_models": [],
        "typeddict_classes": [],
        "operator_reducers": [],
        "structured_output_calls": [],
        "bind_tools_calls": [],
        "os_system_calls": [],
        "tempfile_usage": False,
        "subprocess_usage": False,
        "files_analyzed": 0,
    }

    for py_file in scan_directory(repo_path, "*.py"):
        source = read_file(repo_path, py_file)
        if source is None:
            continue
        info = analyze_python_file(source)
        if info is None:
            continue

        findings["files_analyzed"] += 1

        for cls in info["classes"]:
            if "BaseModel" in cls["bases"]:
                findings["pydantic_models"].append(
                    {"file": py_file, "class": cls["name"]}
                )
            if "TypedDict" in cls["bases"]:
                findings["typeddict_classes"].append(
                    {"file": py_file, "class": cls["name"]}
                )

        for call in info["calls"]:
            if "StateGraph" in call:
                findings["state_graph_found"] = True
            if "add_edge" in call and "conditional" not in call:
                findings["add_edge_calls"].append({"file": py_file, "call": call})
            if "add_conditional_edges" in call:
                findings["add_conditional_edges_calls"].append(
                    {"file": py_file, "call": call}
                )
            if "with_structured_output" in call:
                findings["structured_output_calls"].append(
                    {"file": py_file, "call": call}
                )
            if "bind_tools" in call:
                findings["bind_tools_calls"].append(
                    {"file": py_file, "call": call}
                )
            if call in ("os.system",):
                findings["os_system_calls"].append({"file": py_file, "call": call})
            if "TemporaryDirectory" in call or "tempfile" in call:
                findings["tempfile_usage"] = True
            if "subprocess.run" in call or "subprocess.Popen" in call:
                findings["subprocess_usage"] = True

        for imp in info["imports"]:
            if "operator.add" in imp or "operator.ior" in imp or imp == "operator":
                findings["operator_reducers"].append({"file": py_file, "import": imp})

        if "operator.add" in source or "operator.ior" in source:
            if py_file not in [r["file"] for r in findings["operator_reducers"]]:
                findings["operator_reducers"].append(
                    {"file": py_file, "import": "inline_usage"}
                )

    return findings


def extract_judge_prompts(repo_path: str) -> dict[str, str | None]:
    """Try to extract system prompts from judge-related files."""
    prompts: dict[str, str | None] = {
        "prosecutor": None,
        "defense": None,
        "tech_lead": None,
    }
    judges_file = read_file(repo_path, "src/nodes/judges.py")
    if judges_file is None:
        return prompts

    current_label: str | None = None
    for line in judges_file.splitlines():
        lower = line.lower()
        if "prosecutor" in lower and ("prompt" in lower or '"""' in line or "'''" in line):
            current_label = "prosecutor"
        elif "defense" in lower and ("prompt" in lower or '"""' in line or "'''" in line):
            current_label = "defense"
        elif "tech_lead" in lower or "techlead" in lower:
            if "prompt" in lower or '"""' in line or "'''" in line:
                current_label = "tech_lead"

    for persona in prompts:
        pattern = re.compile(
            rf'{persona.upper()}.*?=\s*["\']{{3}}(.*?)["\']{{3}}',
            re.DOTALL | re.IGNORECASE,
        )
        match = pattern.search(judges_file)
        if match:
            prompts[persona] = match.group(1).strip()

    return prompts
