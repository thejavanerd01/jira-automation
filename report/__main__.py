"""
Command line check of the Jira connection and numbers, without the UI.

    python -m report CST1                  # latest sprint
    python -m report CST1 "CST1 Q3-S3"     # a specific sprint
"""

import logging
import sys

import config
from log_setup import setup_logging
from report import generate_report

setup_logging()

squad = sys.argv[1] if len(sys.argv) > 1 else next(iter(config.SQUADS))
sprint = sys.argv[2] if len(sys.argv) > 2 else None

try:
    result = generate_report(squad, sprint)
except Exception:
    logging.getLogger("report").exception("Report failed for %s / %s", squad, sprint or "latest sprint")
    sys.exit(1)
print(f"\n{squad} · {result['sprint_name']} ({result['sprint_start']} → {result['sprint_end']})\n")
print(result["summary_df"].to_string(index=False))
