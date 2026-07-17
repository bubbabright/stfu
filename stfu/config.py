# stfu/config.py — Centralized configuration
import tomllib
from pathlib import Path
from dataclasses import dataclass, field

CONFIG_PATH = Path(__file__).parent.parent / "stfu.toml"


@dataclass
class VolumeConfig:
    step: int = 2
    default: int = 50
    min_val: int = 0
    max_val: int = 100


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    poll_interval_ms: int = 1000


@dataclass
class OverlayConfig:
    enabled: bool = True
    poll_interval_ms: int = 200
    transient_duration: float = 3.0
    opacity: float = 0.78
    font_family: str = "Segoe UI"
    font_size_mute: int = 85
    font_size_transient: int = 72


@dataclass
class MQTTConfig:
    enabled: bool = True
    broker: str = "192.168.1.215"
    port: int = 1883
    ws_port: int = 9001
    topic_captions: str = "htpc/captions"
    topic_volume_state: str = "htpc/volume/state"
    topic_volume_set: str = "htpc/volume/set"


@dataclass
class CCConfig:
    enabled: bool = False
    tesseract_cmd: str = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    capture_region: dict = field(default_factory=lambda: {
        "top_offset": 601,
        "height_divisor": 2,
        "width": 2560,
        "height": 1440,
    })
    white_threshold: int = 500
    pixel_threshold: int = 200
    scan_interval: float = 0.5


@dataclass
class MCPConfig:
    enabled: bool = True
    name: str = "stfu"
    transport: str = "stdio"


@dataclass
class LogConfig:
    level: str = "INFO"
    file: str = "logs/stfu.log"
    max_bytes: int = 5_242_880  # 5MB
    backup_count: int = 3


@dataclass
class AppConfig:
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    web: WebConfig = field(default_factory=WebConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    cc: CCConfig = field(default_factory=CCConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    log: LogConfig = field(default_factory=LogConfig)


def _merge(base: dict, override: dict) -> dict:
    """Deep merge override into base."""
    for k, v in override.items():
        if k in base and isinstance(base[k], dict) and isinstance(v, dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def load_config(path: Path | None = None) -> AppConfig:
    """Load config from TOML file, falling back to defaults."""
    path = path or CONFIG_PATH
    data = {}
    if path.exists():
        with open(path, "rb") as f:
            data = tomllib.load(f)

    cfg = AppConfig()
    # Apply overrides section by section
    for section_name in ["volume", "web", "overlay", "mqtt", "cc", "mcp", "log"]:
        section_data = data.get(section_name, {})
        if section_data:
            section_obj = getattr(cfg, section_name)
            for k, v in section_data.items():
                if hasattr(section_obj, k):
                    setattr(section_obj, k, v)
    return cfg
