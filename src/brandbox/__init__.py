"""brandbox — Inject company logos into Microsoft 365 Outlook and Gmail contacts."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("brandbox")
except PackageNotFoundError:
    __version__ = "0.0.0"
