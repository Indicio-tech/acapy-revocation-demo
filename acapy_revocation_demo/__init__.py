import logging
from os import getenv
import sys

from colored import attr
from colored.colored import fg

from .controller.connection import Connection
from .controller.controller import Controller
from .controller.credential_exchange import CredentialExchange
from .controller.presentation_exchange import PresentationExchange


LOG_LEVEL = getenv("LOG_LEVEL", "debug")


class ColorFormatter(logging.Formatter):
    def __init__(self, fmt: str):
        self.default = logging.Formatter(fmt)
        self.formats = {
            logging.DEBUG: logging.Formatter(f'{attr("dim")}{fmt}{attr("reset")}'),
            logging.ERROR: logging.Formatter(f'{fg("red")}{fmt}{attr("reset")}'),
        }

    def format(self, record):
        formatter = self.formats.get(record.levelno, self.default)
        return formatter.format(record)


def logging_to_stdout():
    if sys.stdout.isatty():
        logger = logging.getLogger("acapy_revocation_demo")
        logger.setLevel(LOG_LEVEL.upper())
        ch = logging.StreamHandler()
        ch.setLevel(LOG_LEVEL.upper())
        ch.setFormatter(ColorFormatter("%(message)s"))
        logger.addHandler(ch)
    else:
        logging.basicConfig(
            stream=sys.stdout, level=LOG_LEVEL.upper(), format="%(message)s"
        )


__all__ = [
    "Controller",
    "Connection",
    "PresentationExchange",
    "CredentialExchange",
]
