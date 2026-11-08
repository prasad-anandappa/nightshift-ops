"""Configuration — single source for env vars (DESIGN §2/§6)."""

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    inference_base_url: str = os.environ.get(
        "VULTR_INFERENCE_BASE_URL", "https://api.vultrinference.com/v1"
    )
    inference_api_key: str = os.environ.get("VULTR_INFERENCE_API_KEY", "")
    inference_model: str = os.environ.get(
        "VULTR_INFERENCE_MODEL", "deepseek-v4.1-flash-1017"
    )
    inference_fallback_model: str = os.environ.get(
        "VULTR_INFERENCE_FALLBACK_MODEL", "qwen3.8-flash-next"
    )
    sandbox_container: str = os.environ.get("SANDBOX_CONTAINER", "nightshift-shopfront")
    sandbox_service_url: str = os.environ.get(
        "SANDBOX_SERVICE_URL", "http://127.0.0.1:8081"
    )
    db_path: str = os.environ.get("NIGHTSHIFT_DB", "/opt/nightshift/nightshift.db")
    reports_dir: str = os.environ.get("NIGHTSHIFT_REPORTS", "/opt/nightshift/reports")
    kill_switch_file: str = os.environ.get("KILL_SWITCH_FILE", "/tmp/nightshift-stop")
    probe_interval_s: float = float(os.environ.get("PROBE_INTERVAL_S", "2"))
    probe_failure_threshold: int = int(os.environ.get("PROBE_FAILURE_THRESHOLD", "2"))


settings = Settings()
