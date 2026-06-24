import json
import logging
from typing import Any


logger = logging.getLogger("gold_analysis")
logging.basicConfig(level=logging.INFO, format="%(message)s")


def log_event(level: int, event: str, **context: Any) -> None:
    payload = {"event": event, **context}
    logger.log(level, json.dumps(payload, ensure_ascii=False, default=str))
