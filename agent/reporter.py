"""Reporter: a permanent Markdown incident report per incident — evidence,
plan (with the model's diagnosis), every tool call and result, and the
independent verification outcome. Served from the dashboard; in the full
design these land in Vultr Object Storage.
"""

from __future__ import annotations

import os
import time

from .config import settings
from .models import Incident


def write_report(inc: Incident) -> str:
    os.makedirs(settings.reports_dir, exist_ok=True)
    path = os.path.join(settings.reports_dir, f"incident-{inc.id}.md")
    lines = [
        f"# Incident {inc.id} — {inc.service}",
        "",
        f"- **Fault signature:** {inc.signature.value}",
        f"- **Final status:** {inc.status.value}",
        f"- **Opened:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(inc.opened_at))}",
    ]
    if inc.closed_at:
        lines.append(
            f"- **Closed:** {time.strftime('%Y-%m-%d %H:%M:%S UTC', time.gmtime(inc.closed_at))} "
            f"({inc.closed_at - inc.opened_at:.0f}s end to end)"
        )
    lines += ["", "## Evidence", ""]
    for k, v in inc.evidence.items():
        lines.append(f"- **{k}:** {v}")
    if inc.plan:
        lines += ["", "## Diagnosis & plan (Vultr Serverless Inference)", "", inc.plan.diagnosis, ""]
        for i, s in enumerate(inc.plan.steps, 1):
            lines.append(f"{i}. `{s.tool}` — {s.why}")
        if inc.plan.recalled_from_memory:
            lines.append("\n_This fix sequence was recalled from agent memory (proven fix)._")
    lines += ["", "## Tool calls", ""]
    for r in inc.results:
        mark = "REFUSED" if r.refused else ("ok" if r.ok else "FAILED")
        lines.append(f"- `{r.tool}` — {mark}: {r.output[:400]}")
        if r.refusal_reason:
            lines.append(f"  - Refusal reason: {r.refusal_reason}")
    lines += ["", "## Independent verification", "", f"```\n{inc.verification}\n```", ""]
    with open(path, "w") as fh:
        fh.write("\n".join(lines))
    return path
