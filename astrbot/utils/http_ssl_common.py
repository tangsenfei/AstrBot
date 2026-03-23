import ssl
import logging
from typing import Any

logger = logging.getLogger(__name__)


def build_ssl_context_with_certifi(log_obj: Any = None) -> ssl.SSLContext:
    """Build SSL context with certifi certificates if available."""
    log = log_obj or logger
    try:
        import certifi
        context = ssl.create_default_context(cafile=certifi.where())
        return context
    except ImportError:
        log.debug("certifi not installed, using default SSL context")
        return ssl.create_default_context()
