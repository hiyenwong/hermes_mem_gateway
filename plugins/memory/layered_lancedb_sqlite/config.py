from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable

import yaml


CONFIG_DIRNAME = "memory-providers/layered_lancedb_sqlite"
CONFIG_FILENAME = "config.yaml"


@dataclass
class ProviderConfig:
    memory_workspace: str = "default"
    profile_id: str = "default"
    allow_non_primary_durable_writes: bool = False
    promotion_min_score: float = 0.8
    recall_limit_per_layer: int = 4
    embedding_dimensions: int = 64
    gateway_platforms: list[str] = field(
        default_factory=lambda: ["gateway", "discord", "slack", "telegram", "whatsapp"]
    )
    storage_root: str = ""

    @classmethod
    def from_mapping(cls, values: Dict[str, Any] | None) -> "ProviderConfig":
        values = values or {}
        accepted = {field.name for field in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
        filtered = {key: value for key, value in values.items() if key in accepted}
        return cls(**filtered)

    def to_mapping(self) -> Dict[str, Any]:
        return asdict(self)

    def storage_base(self, hermes_home: str) -> Path:
        root = Path(self.storage_root) if self.storage_root else Path(hermes_home) / CONFIG_DIRNAME
        return root / self.profile_id / self.memory_workspace


def config_path(hermes_home: str) -> Path:
    return Path(hermes_home) / CONFIG_DIRNAME / CONFIG_FILENAME


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


def merge_overrides(config: ProviderConfig, values: Iterable[tuple[str, Any]]) -> ProviderConfig:
    data = config.to_mapping()
    for key, value in values:
        if value is None or key not in data:
            continue
        if isinstance(data[key], bool):
            data[key] = coerce_bool(value)
        else:
            data[key] = value
    return ProviderConfig.from_mapping(data)
