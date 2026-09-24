"""
Build fake Jira issues for tests — no network needed.

    story("CST-1", sp=5, status="Done", resolved="2026-09-10", sprints=[S5])
"""

import config

S4 = ("CST1 Q3-S4", "2026-08-25", "2026-09-05")
S5 = ("CST1 Q3-S5", "2026-09-08", "2026-09-19")

SQUAD = {
    "project": "CST",
    "members": ["dev1", "dev2"],
    "sprints": ["CST1 Q3-S3", "CST1 Q3-S4", "CST1 Q3-S5"],
    "backlog_filter": 'labels = "CST1"',
}


def sprint_string(name, start, end, sprint_id=1):
    """Same shape as the sprint field Jira Server returns."""
    return (f"com.atlassian.greenhopper.service.sprint.Sprint@abc[id={sprint_id},rapidViewId=1,"
            f"state=CLOSED,name={name},startDate={start}T09:00:00.000-04:00,"
            f"endDate={end}T17:00:00.000-04:00,completeDate=<null>,sequence={sprint_id}]")


def story(key, sp=3, status="To Do", resolved=None, sprints=(S5,), assignee="Dev One", summary=None):
    return {
        "key": key,
        "fields": {
            "summary": summary or f"Story {key}",
            "assignee": {"name": assignee.lower().replace(" ", ""), "displayName": assignee} if assignee else None,
            "status": {"name": status},
            "created": "2026-08-01T10:00:00.000-0400",
            "resolutiondate": f"{resolved}T12:00:00.000-0400" if resolved else None,
            config.STORY_POINTS_FIELD: sp,
            config.SPRINT_FIELD: [sprint_string(*s, sprint_id=i) for i, s in enumerate(sprints)],
        },
    }
