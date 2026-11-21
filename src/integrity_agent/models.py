"""Shared evidence contracts; identifiers are stable content hashes."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

Tier = Literal["info", "review", "strong"]
FOOTER = "Anomalies are not proof of misconduct. Findings require expert human review."


def stable_id(prefix: str, value: Any) -> str:
    blob = json.dumps(value, sort_keys=True, default=str, separators=(",", ":")).encode()
    return prefix + "-" + hashlib.sha256(blob).hexdigest()[:20]


class Model(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Author(Model):
    id: str
    name: str
    orcid: str | None = None
    institutions: list[str] = Field(default_factory=list)
    works_count: int = 0


class Work(Model):
    id: str
    title: str
    year: int | None = None
    venue: str = ""
    doi: str | None = None
    pmcid: str | None = None
    arxiv_id: str | None = None
    author_id: str
    oa_urls: list[str] = Field(default_factory=list)
    topic_id: str | None = None


class Artifact(Model):
    work_id: str
    artifact_id: str
    source: str
    url: str
    linking_identifier: str = Field(min_length=1)
    sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    license: str
    retrieved_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    path: str
    media_type: str = ""
    parent_artifact_id: str | None = None
    relation: str = "identifier"


class Finding(Model):
    id: str
    detector: str
    kind: str
    tier: Tier
    work_ids: list[str] = Field(min_length=1)
    artifact_ids: list[str] = Field(min_length=1)
    statement: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    measurements: dict[str, Any] = Field(default_factory=dict)
    evidence_files: list[str] = Field(default_factory=list)
    evidence_sha256: dict[str, str] = Field(default_factory=dict)
    limitations: list[str] = Field(default_factory=list)


def finding(
    detector: str,
    kind: str,
    tier: Tier,
    work_ids: list[str],
    artifact_ids: list[str],
    statement: str,
    **kwargs: Any,
) -> Finding:
    values = dict(
        detector=detector,
        kind=kind,
        tier=tier,
        work_ids=sorted(set(work_ids)),
        artifact_ids=sorted(set(artifact_ids)),
        statement=statement,
        **kwargs,
    )
    return Finding(id=stable_id(detector, values), **values)


class Claim(Model):
    finding_id: str
    artifact_ids: list[str]
    text: str
    tier: Tier


class Stat(Model):
    work_id: str
    artifact_id: str
    group: str
    variable: str
    mean: str
    sd: str | None = None
    n: int = Field(gt=1)
    items: int = Field(default=1, gt=0)
    integer_scale_confirmed: bool = False
    scale: Literal["average", "sum"] = "average"
    source_text: str = ""


class Baseline(Model):
    work_id: str
    artifact_id: str
    variables: list[str]
    means: list[list[float]]
    sds: list[list[float]]
    ns: list[int]
    randomized: bool
    independent_variables_confirmed: bool = False


class Coverage(Model):
    work_id: str
    source: str
    status: Literal["ok", "skipped", "failed"]
    detail: str
