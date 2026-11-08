"""Shared data models for the NightShift Ops control plane."""

from __future__ import annotations

import time
import uuid
from enum import Enum

from pydantic import BaseModel, Field


class FaultSignature(str, Enum):
    PROCESS_DOWN = "process_down"
    BAD_DEPLOY = "bad_deploy"
    DISK_PRESSURE = "disk_pressure"
    ERROR_SPIKE = "error_spike"
    UNKNOWN = "unknown"


class IncidentStatus(str, Enum):
    OPEN = "open"
    PLANNING = "planning"
    ACTING = "acting"
    VERIFYING = "verifying"
    CLOSED = "closed"
    REOPENED = "reopened"
    HALTED = "halted"
    FAILED = "failed"


class PlanStep(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)
    why: str = ""


class Plan(BaseModel):
    diagnosis: str
    steps: list[PlanStep] = Field(default_factory=list)
    recalled_from_memory: bool = False


class ToolResult(BaseModel):
    tool: str
    ok: bool
    output: str = ""
    refused: bool = False
    refusal_reason: str = ""


class AuditEvent(BaseModel):
    ts: float = Field(default_factory=time.time)
    incident_id: str | None = None
    kind: str  # detected|plan|tool_call|tool_result|refusal|verify|memory|report|kill|ask
    message: str
    data: dict = Field(default_factory=dict)


class Incident(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:10])
    service: str = "shopfront"
    signature: FaultSignature = FaultSignature.UNKNOWN
    status: IncidentStatus = IncidentStatus.OPEN
    opened_at: float = Field(default_factory=time.time)
    closed_at: float | None = None
    evidence: dict = Field(default_factory=dict)
    plan: Plan | None = None
    results: list[ToolResult] = Field(default_factory=list)
    verification: dict = Field(default_factory=dict)
    report_path: str | None = None


class AskRequest(BaseModel):
    request: str


class AskResponse(BaseModel):
    executed: bool
    refused: bool
    message: str
    proposed_tool: str | None = None
