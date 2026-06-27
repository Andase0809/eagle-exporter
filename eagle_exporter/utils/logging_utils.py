from __future__ import annotations

import logging
from typing import Callable, Optional


class CallbackLogHandler(logging.Handler):
    def __init__(self, callback: Callable[[str], None]) -> None:
        super().__init__()
        self.callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.callback(self.format(record) + "\n")
        except Exception:
            pass


def build_logger(name: str = "eagle_exporter") -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)
    logger.propagate = False

    console = logging.StreamHandler()
    console.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(console)
    return logger


def attach_ui_handler(
    logger: logging.Logger,
    callback: Optional[Callable[[str], None]],
) -> None:
    if callback is None:
        return

    for handler in logger.handlers:
        if isinstance(handler, CallbackLogHandler):
            return

    ui_handler = CallbackLogHandler(callback)
    ui_handler.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    logger.addHandler(ui_handler)
