"""
Squad Delivery Pulse — configuration.

Connection settings come from environment variables (or a .env file next to
this file). Squad definitions live below.
"""

import os

# Load .env next to this file (no extra package needed). Real env vars win.
_ENV_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
if os.path.exists(_ENV_FILE):
    with open(_ENV_FILE, encoding="utf-8") as _fh:
        for _line in _fh:
            _line = _line.strip()
            if _line and not _line.startswith("#") and "=" in _line:
                _key, _value = _line.split("=", 1)
                os.environ.setdefault(_key.strip(), _value.strip().strip('"').strip("'"))

# ── Jira connection ──────────────────────────────────────────────────────────
JIRA_HOST = (os.getenv("JIRA_HOST", "jira.yourcompany.com")
             .replace("https://", "").replace("http://", "").rstrip("/"))
BEARER_TOKEN = os.getenv("JIRA_BEARER_TOKEN", "")

# Optional: path to your corporate CA bundle if Jira uses an internal certificate
JIRA_CA_BUNDLE = os.getenv("JIRA_CA_BUNDLE", "")

# Custom field ids differ per Jira instance — find them at /rest/api/2/field
STORY_POINTS_FIELD = os.getenv("STORY_POINTS_FIELD", "customfield_10002")
SPRINT_FIELD = os.getenv("SPRINT_FIELD", "customfield_10004")

# ── Report settings ──────────────────────────────────────────────────────────
HISTORY_SPRINTS = 4          # how many sprints before the selected one feed the average velocity

# Quarters for the quarterly burndown. The quarter containing the selected
# sprint's end date is used. Weeks are plotted on Sundays, like the deck.
QUARTERS = {
    "Q1 2026": ("2026-01-01", "2026-03-31"),
    "Q2 2026": ("2026-04-01", "2026-06-30"),
    "Q3 2026": ("2026-07-01", "2026-09-30"),
    "Q4 2026": ("2026-10-01", "2026-12-31"),
    "Q1 2027": ("2027-01-01", "2027-03-31"),
}

# Status names that mean a story is finished (it also needs a resolution date).
DONE_STATUSES = ["Done"]

# Backlog readiness is decided by Jira status name (case-insensitive).
# Anything not listed as ready or blocked counts as "Needs refinement".
BACKLOG_READY_STATUSES = ["Ready", "Ready for Dev", "Ready for Development", "Groomed"]
BACKLOG_BLOCKED_STATUSES = ["Blocked", "On Hold"]

# ── Squads ───────────────────────────────────────────────────────────────────
#   project        Jira project key
#   members        Jira usernames used in `assignee IN (...)`
#   sprints        sprint names, oldest → newest. The last one is selected by default.
#                  Start/end dates are read from Jira's sprint field automatically.
#   backlog_filter extra JQL that picks this squad's backlog (label, component, team field…)
#   sprint_dates   optional overrides {"sprint name": ["YYYY-MM-DD", "YYYY-MM-DD"]}
SQUADS = {
    "CST1": {
        "project": "CST",
        "members": ["cst1.dev1", "cst1.dev2", "cst1.dev3", "cst1.dev4", "cst1.dev5"],
        "sprints": ["CST1 Q3-S1", "CST1 Q3-S2", "CST1 Q3-S3", "CST1 Q3-S4", "CST1 Q3-S5"],
        "backlog_filter": 'labels = "CST1"',
    },
    "CST2": {
        "project": "CST",
        "members": ["cst2.dev1", "cst2.dev2", "cst2.dev3", "cst2.dev4"],
        "sprints": ["CST2 Q3-S1", "CST2 Q3-S2", "CST2 Q3-S3", "CST2 Q3-S4", "CST2 Q3-S5"],
        "backlog_filter": 'labels = "CST2"',
    },
    "CST3": {
        "project": "CST",
        "members": ["cst3.dev1", "cst3.dev2", "cst3.dev3", "cst3.dev4", "cst3.dev5", "cst3.dev6"],
        "sprints": ["CST3 Q3-S1", "CST3 Q3-S2", "CST3 Q3-S3", "CST3 Q3-S4", "CST3 Q3-S5"],
        "backlog_filter": 'labels = "CST3"',
    },
    "CST4": {
        "project": "CST",
        "members": ["cst4.dev1", "cst4.dev2", "cst4.dev3"],
        "sprints": ["CST4 Q3-S1", "CST4 Q3-S2", "CST4 Q3-S3", "CST4 Q3-S4", "CST4 Q3-S5"],
        "backlog_filter": 'labels = "CST4"',
    },
}
