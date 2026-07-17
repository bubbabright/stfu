# stfu/config.py — Centralized configuration
import logging
import os
import tomllib
from pathlib import Path
from dataclasses import dataclass, field


def _get_env(key: str, default: str) -> str:
    """Get env var with fallback, used for MQTT broker override."""
    return os.getenv(key, default)


CONFIG_PATH = Path(__file__).parent.parent / "stfu.toml"


def _validate_range(name: str, value: int, min_val: int, max_val: int) -> int:
    if not min_val <= value <= max_val:
        raise ValueError(f"{name} must be between {min_val} and {max_val}, got {value}")
    return value


def _validate_positive(name: str, value: float | int) -> float:
    if value <= 0:
        raise ValueError(f"{name} must be positive, got {value}")
    return value


def _validate_opacity(value: float) -> float:
    return _validate_range("opacity", value, 0.0, 1.0)


def _validate_log_level(value: str) -> str:
    valid = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}
    upper = value.upper()
    if upper not in valid:
        raise ValueError(f"log.level must be one of {valid}, got {value}")
    return upper


def _validate_transport(value: str) -> str:
    valid = {"stdio", "sse", "streamable-http"}
    if value not in valid:
        raise ValueError(f"mcp.transport must be one of {valid}, got {value}")
    return value


@dataclass
class VolumeConfig:
    step: int = 2
    default: int = 20  # Match stfu.toml default
    min_val: int = 0
    max_val: int = 100

    def __post_init__(self):
        self.step = _validate_range("volume.step", self.step, 1, 100)
        self.default = _validate_range("volume.default", self.default, self.min_val, self.max_val)
        self.min_val = _validate_range("volume.min_val", self.min_val, 0, 100)
        self.max_val = _validate_range("volume.max_val", self.max_val, 0, 100)
        if self.min_val >= self.max_val:
            raise ValueError("volume.min_val must be less than max_val")


@dataclass
class WebConfig:
    host: str = "0.0.0.0"
    port: int = 5000
    poll_interval_ms: int = 1000

    def __post_init__(self):
        self.port = _validate_range("web.port", self.port, 1, 65535)
        self.poll_interval_ms = _validate_positive("web.poll_interval_ms", self.poll_interval_ms)


@dataclass
class OverlayConfig:
    enabled: bool = True
    poll_interval_ms: int = 200
    transient_duration: float = 3.0
    opacity: float = 0.78
    font_family: str = "Segoe UI"
    font_size_mute: int = 85
    font_size_transient: int = 72

    def __post_init__(self):
        self.poll_interval_ms = _validate_positive(
            "overlay.poll_interval_ms", self.poll_interval_ms)
        self.transient_duration = _validate_positive(
            "overlay.transient_duration", self.transient_duration)
        self.opacity = _validate_opacity(self.opacity)
        self.font_size_mute = _validate_positive(
            "overlay.font_size_mute", self.font_size_mute)
        self.font_size_transient = _validate_positive(
            "overlay.font_size_transient", self.font_size_transient)


@dataclass
class MQTTConfig:
    enabled: bool = True
    broker: str = field(default_factory=lambda: _get_env("MQTT_BROKER", "192.168.1.215"))
    port: int = 1883
    ws_port: int = 9001
    topic_captions: str = "htpc/captions"
    topic_volume_state: str = "htpc/volume/state"
    topic_volume_set: str = "htpc/volume/set"

    def __post_init__(self):
        self.port = _validate_range("mqtt.port", self.port, 1, 65535)
        self.ws_port = _validate_range("mqtt.ws_port", self.ws_port, 1, 65535)
        if self.port == self.ws_port:
            raise ValueError("mqtt.port and mqtt.ws_port must differ")


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

    def __post_init__(self):
        self.white_threshold = _validate_positive("cc.white_threshold", self.white_threshold)
        self.pixel_threshold = _validate_positive("cc.pixel_threshold", self.pixel_threshold)
        self.scan_interval = _validate_positive("cc.scan_interval", self.scan_interval)

        region = self.capture_region
        required_keys = {"top_offset", "height_divisor", "width", "height"}
        if not required_keys.issubset(region.keys()):
            missing = required_keys - region.keys()
            raise ValueError(f"cc.capture_region missing keys: {missing}")
        region["height_divisor"] = _validate_range(
            "cc.capture_region.height_divisor", region["height_divisor"], 1, 10)
        region["width"] = _validate_positive("cc.capture_region.width", region["width"])
        region["height"] = _validate_positive("cc.capture_region.height", region["height"])
        region["top_offset"] = _validate_range(
            "cc.capture_region.top_offset", region["top_offset"], 0, 10000)


@dataclass
class MCPConfig:
    enabled: bool = True
    name: str = "stfu"
    transport: str = "stdio"

    def __post_init__(self):
        self.transport = _validate_transport(self.transport)


@dataclass
class LogConfig:
    level: str = "INFO"
    file: str = "logs/stfu.log"
    max_bytes: int = 5_242_880  # 5MB
    backup_count: int = 3

    def __post_init__(self):
        self.level = _validate_log_level(self.level)
        self.max_bytes = _validate_positive("log.max_bytes", self.max_bytes)
        self.backup_count = _validate_range("log.backup_count", self.backup_count, 0, 100)


@dataclass
class AppConfig:
    volume: VolumeConfig = field(default_factory=VolumeConfig)
    web: WebConfig = field(default_factory=WebConfig)
    overlay: OverlayConfig = field(default_factory=OverlayConfig)
    mqtt: MQTTConfig = field(default_factory=MQTTConfig)
    cc: CCConfig = field(default_factory=CCConfig)
    mcp: MCPConfig = field(default_factory=MCPConfig)
    log: LogConfig = field(default_factory=LogConfig)


# Valid keys per section for TOML validation
VALID_KEYS = {
    "volume": {"step", "default", "min_val", "max_val"},
    "web": {"host", "port", "poll_interval_ms"},
    "overlay": {"enabled", "poll_interval_ms", "transient_duration", "opacity",
                "font_family", "font_size_mute", "font_size_transient"},
    "mqtt": {"enabled", "broker", "port", "ws_port", "topic_captions",
             "topic_volume_state", "topic_volume_set"},
    "cc": {"enabled", "tesseract_cmd", "capture_region", "white_threshold",
           "pixel_threshold", "scan_interval"},
    "mcp": {"enabled", "name", "transport"},
    "log": {"level", "file", "max_bytes", "backup_count"},
}


def _validate_toml_section(section_name: str, section_data: dict) -> None:
    """Warn about unknown keys in TOML section."""
    valid = VALID_KEYS.get(section_name, set())
    unknown = set(section_data.keys()) - valid
    if unknown:
        log = logging.getLogger("stfu.config")
        log.warning("config.%s: unknown keys (ignored): %s", section_name, sorted(unknown))


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

    # Validate TOML sections
    for section_name, section_data in data.items():
        if section_name in VALID_KEYS:
            _validate_toml_section(section_name, section_data)

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
