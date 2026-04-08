"""eFuse Telemetry Generator — synthetic telemetry for automotive Zone Controller architectures."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("efuse-telemetry-generator")
except PackageNotFoundError:  # pragma: no cover
    __version__ = "0.0.0-dev"