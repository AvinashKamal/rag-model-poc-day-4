# k6 trigger + result tool. Shells out to the k6 CLI directly rather than depending
# on an unverified community k6-mcp-server wrapper (see architecture plan, section 7).
# k6's Prometheus remote-write output is configured on the script/CLI side (infra/),
# this tool additionally captures a local JSON summary so an agent can read results
# without querying Grafana.

import json
import os
import shutil
import subprocess
import uuid
from pathlib import Path

from orchestrator_mcp.tools._localguard import target_is_local

_RESULTS_DIR = Path(__file__).resolve().parents[3] / "data" / "k6_results"


def trigger_k6_run(script_path: str, base_url: str = "http://localhost:8000") -> dict:
    if not target_is_local(base_url):
        return {"error": f"refusing to run k6 against non-local target '{base_url}'"}

    k6_path = shutil.which("k6")
    if k6_path is None:
        return {"error": "k6 binary not found on PATH"}

    script = Path(script_path)
    if not script.is_file():
        return {"error": f"script not found: {script_path}"}

    run_id = uuid.uuid4().hex[:12]
    _RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    summary_path = _RESULTS_DIR / f"{run_id}.json"

    proc = subprocess.run(
        [k6_path, "run", f"--summary-export={summary_path}", str(script)],
        # {**os.environ, ...}, not a bare {"BASE_URL": ...}: the latter
        # replaces the child's *entire* environment, dropping PATH/HOME/etc
        # that k6 itself needs to run.
        env={**os.environ, "BASE_URL": base_url},
        capture_output=True,
        text=True,
        timeout=600,
        # check=False, explicit: a nonzero k6 exit code (e.g. a threshold
        # breach) is an expected outcome to report back via `exit_code`
        # below, not a Python-level failure to raise on.
        check=False,
    )

    return {
        "run_id": run_id,
        "exit_code": proc.returncode,
        "summary_path": str(summary_path) if summary_path.exists() else None,
        "stderr_tail": proc.stderr[-2000:],
    }


def get_k6_summary(run_id: str) -> dict:
    summary_path = _RESULTS_DIR / f"{run_id}.json"
    if not summary_path.exists():
        return {"error": f"no summary for run_id '{run_id}'"}
    return json.loads(summary_path.read_text())
