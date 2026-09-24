"""
Backlog readiness: how much ready work is waiting for the next sprints.

Readiness comes from the story's status name (see config.BACKLOG_*_STATUSES):
  Ready             status in BACKLOG_READY_STATUSES
  Blocked           status in BACKLOG_BLOCKED_STATUSES
  Needs refinement  anything else

ready coverage = Ready SP ÷ average velocity  (sprints of ready work)
"""

import logging

import pandas as pd

import config
from . import issues as iss

log = logging.getLogger(__name__)

READINESS_STATES = ("Ready", "Needs refinement", "Blocked")
BACKLOG_COLUMNS = ["Key", "Summary", "Assignee", "Story Points", "Status", "Readiness"]


def readiness(status):
    status = status.lower()
    if status in (s.lower() for s in config.BACKLOG_READY_STATUSES):
        return "Ready"
    if status in (s.lower() for s in config.BACKLOG_BLOCKED_STATUSES):
        return "Blocked"
    return "Needs refinement"


def analyse_backlog(backlog_issues, average_velocity):
    """Returns (backlog_df, backlog_sp {state: SP}, ready_coverage, backlog_summary_df)."""
    backlog_df = pd.DataFrame(
        [{
            "Key": issue["key"],
            "Summary": issue["fields"]["summary"],
            "Assignee": iss.assignee_name(issue),
            "Story Points": iss.story_points(issue),
            "Status": iss.status_name(issue),
            "Readiness": readiness(iss.status_name(issue)),
        } for issue in backlog_issues],
        columns=BACKLOG_COLUMNS,
    )

    backlog_sp = {
        state: float(backlog_df.loc[backlog_df["Readiness"] == state, "Story Points"].sum())
        for state in READINESS_STATES
    }
    ready_coverage = round(backlog_sp["Ready"] / average_velocity, 1) if average_velocity else 0

    mapping = backlog_df.groupby("Status")["Readiness"].first().to_dict() if not backlog_df.empty else {}
    log.debug("Backlog status -> readiness: %s", mapping)
    if not backlog_df.empty and backlog_sp["Ready"] == 0:
        log.warning("No backlog story counts as Ready. Statuses seen: %s. Add the ready ones to "
                    "BACKLOG_READY_STATUSES in config.py.", sorted(mapping))
    log.info("Backlog: %d stories, %s, ready coverage %s sprints (avg velocity %s)",
             len(backlog_df), {k: v for k, v in backlog_sp.items()}, ready_coverage, average_velocity)

    backlog_summary_df = pd.DataFrame([
        {"Metric": "Refined Stories", "Value": int((backlog_df["Readiness"] == "Ready").sum())},
        {"Metric": "Unrefined Stories", "Value": int((backlog_df["Readiness"] != "Ready").sum())},
        {"Metric": "Ready SP", "Value": backlog_sp["Ready"]},
        {"Metric": "Needs Refinement SP", "Value": backlog_sp["Needs refinement"]},
        {"Metric": "Blocked SP", "Value": backlog_sp["Blocked"]},
        {"Metric": "Ready Coverage (sprints)", "Value": ready_coverage},
    ])
    return backlog_df, backlog_sp, ready_coverage, backlog_summary_df
