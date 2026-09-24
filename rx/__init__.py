"""Rx — privacy-oriented browser under the Restore Privacy umbrella."""

__product__ = "Rx"
__umbrella__ = "Restore Privacy"

from rx.fence import VERSION as __version__

from rx.tabs import TabManager
from rx.privacy import PrivacyDefaults
from rx.extensions import ExtensionRegistry

__all__ = [
    "TabManager",
    "PrivacyDefaults",
    "ExtensionRegistry",
    "__product__",
    "__umbrella__",
    "__version__",
]
