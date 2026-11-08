"""Core-loop tests: policy gate, planner JSON handling, verifier rules,
memory recall, executor refusal path, and a full engine loop with the
sandbox + LLM replaced by fakes (the live drill against real Docker runs
on the deployed instance — see tests/README.md)."""

import pytest

from agent import engine, executor, llm, planner, sandbox, verifier
from agent.memory import Store
from agent.models import FaultSignature, Incident, Plan, PlanStep, ToolResult
from agent.policy import ALLOWLIST, PolicyViolation, check_tool, kill_switch_active


# ---------------------------------------------------------------- policy
def test_allowlist_tools_pass():
    for tool in ALLOWLIST:
        check_tool(tool, {"service": "shopfront"})  # must not raise


@pytest.mark.parametrize(
    "tool", ["delete_database", "drop_table", "run_shell", "read_file", "rm_rf", ""]
)
def test_non_allowlist_tools_refused(tool):
    with pytest.raises(PolicyViolation):
        check_tool(tool, {})


def test_unknown_service_refused():
    with pytest.raises(PolicyViolation):
        check_tool("restart_service", {"service": "production-db"})


def test_kill_switch_file(tmp_path):
    f = tmp_path / "stop"
    assert kill_switch_active(str(f)) is False
    f.write_text("x")
    assert kill_switch_active(str(f)) is True


# ---------------------------------------------------------------- planner
def test_extract_json_plain_and_fenced():
    assert llm.extract_json('{"diagnosis": "x", "steps": []}')["diagnosis"] == "x"
    fenced = 'here you go:\n```json\n{"diagnosis": "y", "steps": []}\n```'
    assert llm.extract_json(fenced)["diagnosis"] == "y"


def test_extract_json_garbage_raises():
    with pytest.raises(llm.LLMError):
        llm.extract_json("no json here")


def test_chat_json_rotates_past_unparseable_replies(monkeypatch):
    # Regression: live incident 7113b12c34 (2026-11-07) died because the
    # primary model answered HTTP 200 with prose. Parse failures must rotate
    # to the next model just like transport failures.
    replies = {"m1": "Sorry, the service looks down.", "m2": '{"tool": "read_logs"}'}
    from agent.config import Settings

    monkeypatch.setattr(
        llm, "settings", Settings(inference_model="m1", inference_fallback_model="m2")
    )
    monkeypatch.setattr(llm, "chat", lambda messages, *a, **kw: replies[kw["model"]])
    assert llm.chat_json([{"role": "user", "content": "x"}]) == {"tool": "read_logs"}
    monkeypatch.setattr(llm, "chat", lambda messages, *a, **kw: "still prose")
    with pytest.raises(llm.LLMError):
        llm.chat_json([{"role": "user", "content": "x"}])


def test_build_plan_with_stubbed_llm(monkeypatch):
    monkeypatch.setattr(
        llm,
        "chat_json",
        lambda messages, **kw: {
            "diagnosis": "process is down",
            "steps": [
                {"tool": "read_logs", "args": {}, "why": "logs show a crash"},
                {"tool": "restart_service", "args": {}, "why": "process unreachable"},
            ],
        },
    )
    inc = Incident(signature=FaultSignature.PROCESS_DOWN, evidence={"health_probe": "unreachable"})
    plan = planner.build_plan(inc)
    assert plan.diagnosis == "process is down"
    assert [s.tool for s in plan.steps] == ["read_logs", "restart_service"]
    for s in plan.steps:
        check_tool(s.tool, s.args)


# ---------------------------------------------------------------- verifier
def test_verifier_pass_and_fail(monkeypatch):
    monkeypatch.setattr(verifier, "probe_health", lambda: (True, "health 200 OK"))
    monkeypatch.setattr(verifier, "probe_error_rate", lambda n=10: 0.0)
    assert verifier.verify(rounds=2, spacing_s=0)["passed"] is True

    monkeypatch.setattr(verifier, "probe_error_rate", lambda n=10: 0.9)
    assert verifier.verify(rounds=1, spacing_s=0)["passed"] is False

    monkeypatch.setattr(verifier, "probe_health", lambda: (False, "health HTTP 503"))
    monkeypatch.setattr(verifier, "probe_error_rate", lambda n=10: 0.0)
    assert verifier.verify(rounds=1, spacing_s=0)["passed"] is False


# ---------------------------------------------------------------- memory
def test_memory_recall_roundtrip():
    store = Store(":memory:")
    assert store.recall_fix("bad_deploy") is None
    store.record_proven_fix("bad_deploy", ["read_logs", "rollback_deploy"])
    assert store.recall_fix("bad_deploy") == ["read_logs", "rollback_deploy"]
    snap = store.memory_snapshot()
    assert snap[0]["signature"] == "bad_deploy" and snap[0]["successes"] == 1


# ---------------------------------------------------------------- executor
def test_executor_refuses_before_touching_anything():
    result = executor.run_tool("delete_database", {"service": "shopfront"}, incident_id="t1")
    assert result.refused is True
    assert result.ok is False
    assert "allowlist" in result.refusal_reason


def test_executor_idempotent_mutations(monkeypatch):
    calls = []
    monkeypatch.setitem(
        sandbox.TOOLS, "restart_service", lambda args: (calls.append(1), (True, "restarted"))[1]
    )
    r1 = executor.run_tool("restart_service", {}, incident_id="inc-9", round_no=1)
    r2 = executor.run_tool("restart_service", {}, incident_id="inc-9", round_no=1)
    assert r1.ok and r2.ok
    assert len(calls) == 1  # same-round retry was an idempotent skip
    # A later plan round (post failed verification) MUST re-apply the fix —
    # regression test for the live drill defect found 2026-11-07, where a
    # second fault injected mid-incident made the round-2 rollback a no-op.
    r3 = executor.run_tool("restart_service", {}, incident_id="inc-9", round_no=2)
    assert r3.ok
    assert len(calls) == 2


# ---------------------------------------------------------------- classify
def test_classify_signatures():
    assert sandbox.classify({"health_probe": "health unreachable: ConnectError"}) == FaultSignature.PROCESS_DOWN
    assert sandbox.classify({"health_probe": "health HTTP 503", "deploy_version": "v1.5.0-broken"}) == FaultSignature.BAD_DEPLOY
    assert (
        sandbox.classify({"health_probe": "health HTTP 503", "data_bytes": 100, "data_quota_bytes": 10})
        == FaultSignature.DISK_PRESSURE
    )


# ---------------------------------------------------------------- engine
def test_engine_full_loop_with_fakes(monkeypatch):
    monkeypatch.setattr(
        sandbox, "gather_evidence", lambda: {"health_probe": "health unreachable: ConnectError"}
    )
    monkeypatch.setattr(sandbox, "classify", lambda ev: FaultSignature.PROCESS_DOWN)
    monkeypatch.setattr(
        planner,
        "build_plan",
        lambda inc: Plan(
            diagnosis="process down",
            steps=[PlanStep(tool="restart_service", why="process unreachable")],
        ),
    )
    monkeypatch.setattr(
        executor,
        "run_tool",
        lambda tool, args=None, incident_id=None, **kw: ToolResult(tool=tool, ok=True, output="done"),
    )
    monkeypatch.setattr(engine, "verify", lambda: {"passed": True, "health_checks": ["ok"], "error_rate": 0.0})
    monkeypatch.setattr(engine.reporter, "write_report", lambda inc: "/tmp/report.md")
    inc = engine.handle_incident(Incident())
    assert inc.status.value == "closed"
    assert engine.store.recall_fix("process_down") == ["restart_service"]


def test_engine_replan_stores_deduped_proven_fix(monkeypatch):
    # Round 1 verification fails, round 2 re-applies the same tool and
    # passes. The stored proven fix must list the tool once — it is the
    # effective sequence, not a transcript (live double-break drill,
    # incident 600cc6d913, stored 'rollback -> rollback' before this fix).
    monkeypatch.setattr(
        sandbox, "gather_evidence", lambda: {"health_probe": "health HTTP 503"}
    )
    monkeypatch.setattr(sandbox, "classify", lambda ev: FaultSignature.BAD_DEPLOY)
    monkeypatch.setattr(
        planner,
        "build_plan",
        lambda inc: Plan(
            diagnosis="bad deploy",
            steps=[PlanStep(tool="rollback_deploy", why="release is broken")],
        ),
    )
    monkeypatch.setattr(
        executor,
        "run_tool",
        lambda tool, args=None, incident_id=None, **kw: ToolResult(tool=tool, ok=True, output="done"),
    )
    outcomes = iter(
        [
            {"passed": False, "health_checks": ["503"], "error_rate": 1.0},
            {"passed": True, "health_checks": ["ok"], "error_rate": 0.0},
        ]
    )
    monkeypatch.setattr(engine, "verify", lambda: next(outcomes))
    monkeypatch.setattr(engine.reporter, "write_report", lambda inc: "/tmp/report.md")
    inc = engine.handle_incident(Incident())
    assert inc.status.value == "closed"
    assert engine.store.recall_fix("bad_deploy") == ["rollback_deploy"]
