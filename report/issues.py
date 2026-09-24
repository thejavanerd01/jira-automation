"""
Helpers for reading fields out of a Jira issue.

Every other module goes through these functions instead of touching
issue["fields"][...] directly. If your Jira returns a field differently,
fix it here once.
"""

import re
from datetime import datetime

import config

DATE_FORMAT = "%Y-%m-%d"


def story_points(issue):
    """Story points of an issue; missing or empty counts as 0."""
    return issue["fields"].get(config.STORY_POINTS_FIELD, 0) or 0


def assignee_name(issue):
    """Assignee display name, or "Unassigned"."""
    assignee = issue["fields"].get("assignee")
    return assignee["displayName"] if assignee else "Unassigned"


def status_name(issue):
    return issue["fields"]["status"]["name"]


def resolved_date(issue):
    """Resolution date as "YYYY-MM-DD", or None if unresolved."""
    resolved = issue["fields"].get("resolutiondate")
    return resolved[:10] if resolved else None


def is_done(issue):
    """True when the story is in a Done status and has a resolution date."""
    return status_name(issue) in config.DONE_STATUSES and resolved_date(issue) is not None


def sprint_strings(issue):
    """Raw values of the sprint custom field (one entry per sprint)."""
    return issue["fields"].get(config.SPRINT_FIELD) or []


def parse_sprint(sprint_value):
    """
    Read (name, start, end) from one sprint-field entry. Dates are "YYYY-MM-DD" or None.

    Jira returns the sprint field in one of two shapes, both handled here:
      string (Jira Server / older DC):
        "...Sprint@1a2b[id=5,state=ACTIVE,name=CST1 Q3-S5,startDate=2026-09-08T...,endDate=...]"
      object (newer Data Center / Cloud):
        {"id": 5, "state": "active", "name": "CST1 Q3-S5", "startDate": "2026-09-08T...", ...}
    """
    if isinstance(sprint_value, dict):
        def date_of(key):
            value = sprint_value.get(key)
            return value[:10] if value else None
        return sprint_value.get("name"), date_of("startDate"), date_of("endDate")

    text = str(sprint_value)
    name = re.search(r"name=([^,]+)", text)
    start = re.search(r"startDate=([^,\]]+)", text)
    end = re.search(r"endDate=([^,\]]+)", text)

    def date_or_none(match):
        return match.group(1)[:10] if match and "null" not in match.group(1) else None

    return (name.group(1) if name else None), date_or_none(start), date_or_none(end)


def sprint_names(issue):
    """Names of every sprint the issue has been in, oldest first."""
    names = []
    for text in sprint_strings(issue):
        name, _, _ = parse_sprint(text)
        if name:
            names.append(name)
    return names


def to_date(date_str):
    return datetime.strptime(date_str, DATE_FORMAT)
