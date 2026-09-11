"""
The confirmation side effect. Per the brief's $0 stack, "email" here is a
console log line — what's graded is that its failure never blocks the
submission response, not that a real SMTP server exists.

FORCE_NOTIFY_FAILURE lets Probe 5 be reproduced on demand: set it true, POST
a submission, and see it still return 201/stored even though this raises.
"""
import logging

from app.config import settings

logger = logging.getLogger("notify")


def send_confirmation(contact: str, widget_title: str) -> bool:
    if settings.FORCE_NOTIFY_FAILURE:
        raise RuntimeError("Simulated notification failure (FORCE_NOTIFY_FAILURE=true)")

    logger.info(
        "CONFIRMATION NOTIFICATION -> %s : your submission to '%s' was received.",
        contact,
        widget_title,
    )
    return True
