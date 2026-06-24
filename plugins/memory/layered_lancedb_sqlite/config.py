from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


CONFIG_DIRNAME = "memory-providers/layered_lancedb_sqlite"
CONFIG_FILENAME = "config.yaml"
ENV_FILENAME = ".env"
PROFILE_ENV_DIRNAME = "profiles"

ENV_KEY_MAP = {
    "LAYERED_MEMORY_WORKSPACE": "memory_workspace",
    "LAYERED_MEMORY_PROFILE_ID": "profile_id",
    "LAYERED_MEMORY_ALLOW_NON_PRIMARY_DURABLE_WRITES": "allow_non_primary_durable_writes",
    "LAYERED_MEMORY_SHARED_WRITER_EMAILS": "shared_writer_emails",
    "LAYERED_MEMORY_SHARED_EXPLICIT_REQUIRED": "shared_explicit_required",
    "LAYERED_MEMORY_PROMOTION_MIN_SCORE": "promotion_min_score",
    "LAYERED_MEMORY_RECALL_LIMIT_PER_LAYER": "recall_limit_per_layer",
    "LAYERED_MEMORY_EMBEDDING_DIMENSIONS": "embedding_dimensions",
    "LAYERED_MEMORY_GATEWAY_PLATFORMS": "gateway_platforms",
    "LAYERED_MEMORY_STORAGE_ROOT": "storage_root",
    "LAYERED_MEMORY_MAINTENANCE_MAX_RECORDS_PER_DAY": "maintenance_max_records_per_day",
    "LAYERED_MEMORY_PREFER_USER_ID_ALT": "prefer_user_id_alt",
    "LAYERED_MEMORY_RECALL_PLATFORM_SCOPED": "recall_platform_scoped",
    "LAYERED_MEMORY_DEFAULT_TTL_HOURS": "default_ttl_hours",
}


@dataclass
class ProviderConfig:
    memory_workspace: str = "default"
    profile_id: str = "default"
    allow_non_primary_durable_writes: bool = False
    shared_writer_emails: list[str] = field(default_factory=list)
    shared_explicit_required: bool = True
    promotion_min_score: float = 0.8
    recall_limit_per_layer: int = 4
    embedding_dimensions: int = 64
    gateway_platforms: list[str] = field(
        default_factory=lambda: ["gateway", "discord", "slack", "telegram", "whatsapp"]
    )
    storage_root: str = ""
    maintenance_max_records_per_day: int = 1000
    prefer_user_id_alt: bool = False
    recall_platform_scoped: bool = False
    default_ttl_hours: int = 0

    @classmethod
    def from_mapping(cls, values: Dict[str, Any] | None) -> "ProviderConfig":
        values = values or {}
        accepted = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {key: value for key, value in values.items() if key in accepted}
        return cls(**filtered)

    def to_mapping(self) -> Dict[str, Any]:
        return asdict(self)

    def storage_base(self, hermes_home: str) -> Path:
        root = (
            Path(self.storage_root)
            if self.storage_root
            else Path(hermes_home) / CONFIG_DIRNAME
        )
        return root / self.profile_id / self.memory_workspace


def config_path(hermes_home: str) -> Path:
    return Path(hermes_home) / CONFIG_DIRNAME / CONFIG_FILENAME


def hermes_env_path(hermes_home: str) -> Path:
    return Path(hermes_home) / ENV_FILENAME


def profile_env_path(hermes_home: str, profile_id: str) -> Path:
    return Path(hermes_home) / PROFILE_ENV_DIRNAME / profile_id / ENV_FILENAME


def parse_env_file(path: Path) -> Dict[str, str]:
    if not path.exists():
        return {}
    values: Dict[str, str] = {}
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        values[key.strip()] = value
    return values


def _coerce_env_value(key: str, value: str) -> Any:
    if key in {
        "allow_non_primary_durable_writes",
        "shared_explicit_required",
        "prefer_user_id_alt",
        "recall_platform_scoped",
    }:
        return coerce_bool(value)
    if key in {"promotion_min_score"}:
        return float(value)
    if key in {
        "recall_limit_per_layer",
        "embedding_dimensions",
        "maintenance_max_records_per_day",
        "default_ttl_hours",
    }:
        return int(value)
    if key in {"gateway_platforms", "shared_writer_emails"}:
        return [item.strip() for item in value.split(",") if item.strip()]
    return value


def load_env_overrides(hermes_home: str, profile_id: str = "") -> Dict[str, Any]:
    merged: Dict[str, Any] = {}
    for path in [
        hermes_env_path(hermes_home),
        profile_env_path(hermes_home, profile_id) if profile_id else None,
    ]:
        if path is None:
            continue
        raw = parse_env_file(path)
        for env_key, config_key in ENV_KEY_MAP.items():
            if env_key in raw:
                merged[config_key] = _coerce_env_value(config_key, raw[env_key])
    return merged


def load_env_config(hermes_home: str, profile_id: str = "") -> ProviderConfig:
    merged = load_env_overrides(hermes_home, profile_id)
    return ProviderConfig.from_mapping(merged)


def load_config(hermes_home: str) -> ProviderConfig:
    path = config_path(hermes_home)
    if not path.exists():
        return ProviderConfig()
    data = yaml.safe_load(path.read_text()) or {}
    return ProviderConfig.from_mapping(data)


def save_config(values: Dict[str, Any], hermes_home: str) -> Path:
    path = config_path(hermes_home)
    path.parent.mkdir(parents=True, exist_ok=True)
    config = ProviderConfig.from_mapping(values)
    path.write_text(yaml.safe_dump(config.to_mapping(), sort_keys=True))
    return path


def coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "on"}
    return bool(value)


def merge_overrides(
    config: ProviderConfig, values: Iterable[tuple[str, Any]]
) -> ProviderConfig:
    data = config.to_mapping()
    for key, value in values:
        if value is None or key not in data:
            continue
        if isinstance(data[key], bool):
            data[key] = coerce_bool(value)
        elif isinstance(data[key], list) and isinstance(value, str):
            data[key] = [item.strip() for item in value.split(",") if item.strip()]
        else:
            data[key] = value
    return ProviderConfig.from_mapping(data)
