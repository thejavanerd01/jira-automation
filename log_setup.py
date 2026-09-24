"""
Logging setup, shared by the dashboard, the CLI and the diagnose command.

    from log_setup import setup_logging
    setup_logging()                       # once, at program start

    import logging
    log = logging.getLogger(__name__)     # in every module
    log.info("...")  log.debug("...")  log.exception("...")

Settings (in .env or the environment):
    LOG_LEVEL   DEBUG | INFO (default) | WARNING | ERROR
    LOG_FILE    path of the log file (default logs/squad-pulse.log, rotated at 5 MB)
                set LOG_FILE=none to log to the terminal only

Levels used in this project:
    INFO     one line per Jira call and per report step (what happened, counts, timing)
    DEBUG    every JQL query, every story and how it was counted, raw sprint values
    WARNING  something looks off but the report still runs
    ERROR    the report failed (with the full traceback)
"""

import logging
import logging.handlers
import os

import config  # noqa: F401  (loads .env so LOG_LEVEL / LOG_FILE are available)

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_LOG_FILE = os.path.join(PROJECT_DIR, "logs", "squad-pulse.log")
FORMAT = "%(asctime)s %(levelname)-7s %(name)-16s %(message)s"
_MARKER = "_squad_pulse_configured"


def setup_logging(console_level=None):
    """
    Configure the root logger once. Safe to call on every Streamlit rerun.
    console_level  optional higher level for the terminal only (the file keeps LOG_LEVEL)
    """
    root = logging.getLogger()
    level = getattr(logging, os.getenv("LOG_LEVEL", "INFO").upper(), logging.INFO)
    root.setLevel(level)
    if getattr(root, _MARKER, False):
        return
    formatter = logging.Formatter(FORMAT, datefmt="%Y-%m-%d %H:%M:%S")

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    if console_level is not None:
        console.setLevel(max(level, console_level))
    root.addHandler(console)

    log_file = os.getenv("LOG_FILE", DEFAULT_LOG_FILE)
    if log_file.lower() != "none":
        os.makedirs(os.path.dirname(os.path.abspath(log_file)), exist_ok=True)
        file_handler = logging.handlers.RotatingFileHandler(
            log_file, maxBytes=5_000_000, backupCount=3, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root.addHandler(file_handler)

    # Third-party libraries are noisy at DEBUG; keep them at WARNING.
    for noisy in ("urllib3", "watchdog", "streamlit", "PIL", "matplotlib", "fsevents"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    setattr(root, _MARKER, True)
    logging.getLogger(__name__).info(
        "Logging at %s to console%s", logging.getLevelName(level),
        "" if log_file.lower() == "none" else f" and {log_file}")
