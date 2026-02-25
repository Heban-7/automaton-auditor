import operator
from typing import Annotated, Dict, List, Literal, Optional

from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# ---------------------------------------------------------------------------
# Detective Output
# ---------------------------------------------------------------------------


class Evidence(BaseModel):
    """A single piece of forensic evidence collected by a Detective agent."""

    goal: str = Field(description="The forensic goal this evidence addresses")
    found: bool = Field(description="Whether the artifact exists")
    content: Optional[str] = Field(
        default=None, description="Extracted content snippet"
    )
    location: str = Field(description="File path or commit hash")
    rationale: str = Field(
        description="Rationale for confidence in this evidence"
    )
    confidence: float = Field(
        ge=0.0, le=1.0, description="Confidence score 0-1"
    )


# ---------------------------------------------------------------------------
# Judge Output
# ---------------------------------------------------------------------------


class JudicialOpinion(BaseModel):
    """A single judge's opinion on one rubric criterion."""

    judge: Literal["Prosecutor", "Defense", "TechLead"]
    criterion_id: str
    score: int = Field(ge=1, le=5)
    argument: str
    cited_evidence: List[str]


# ---------------------------------------------------------------------------
# Chief Justice Output
# ---------------------------------------------------------------------------


class CriterionResult(BaseModel):
    """Final synthesized result for one rubric dimension."""

    dimension_id: str
    dimension_name: str
    final_score: int = Field(ge=1, le=5)
    judge_opinions: List[JudicialOpinion]
    dissent_summary: Optional[str] = Field(
        default=None,
        description="Required when score variance > 2",
    )
    remediation: str = Field(
        description="Specific file-level instructions for improvement"
    )


class AuditReport(BaseModel):
    """The complete audit report produced by the Chief Justice."""

    repo_url: str
    executive_summary: str
    overall_score: float
    criteria: List[CriterionResult]
    remediation_plan: str


# ---------------------------------------------------------------------------
# Graph State
# ---------------------------------------------------------------------------


class AgentState(TypedDict):
    repo_url: str
    pdf_path: str
    rubric_dimensions: List[Dict]
    repo_path: str
    evidences: Annotated[Dict[str, List[Evidence]], operator.ior]
    opinions: Annotated[List[JudicialOpinion], operator.add]
    final_report: Optional[AuditReport]
