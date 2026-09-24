"""
Every JQL query the report sends to Jira, built in one place.

Each function returns a JQL string. To change what data the report reads
(e.g. include Bugs as well as Stories), edit it here.
"""


def _quoted(names):
    return ",".join(f'"{name}"' for name in names)


def _squad_stories(squad):
    """Stories in the squad's project assigned to its members."""
    return f"""
    project = {squad["project"]}
    AND issuetype = Story
    AND assignee IN ({",".join(squad["members"])})"""


def sprint_stories(squad, sprint):
    """All stories in one sprint (any status)."""
    return f"""{_squad_stories(squad)}
    AND Sprint = "{sprint}"
    """


def done_stories_in(squad, sprints):
    """Finished stories in the given sprints — used for velocity history."""
    return f"""{_squad_stories(squad)}
    AND Sprint IN ({_quoted(sprints)})
    AND statusCategory = Done
    """


def all_stories_in(squad, sprints):
    """Every story in the given sprints (any status) — committed scope."""
    return f"""{_squad_stories(squad)}
    AND Sprint IN ({_quoted(sprints)})
    """


def backlog_stories(squad):
    """Open stories not yet in an active/closed sprint, narrowed by backlog_filter."""
    backlog_filter = squad.get("backlog_filter", "").strip()
    return f"""
    project = {squad["project"]}
    AND issuetype = Story
    AND statusCategory != Done
    AND (Sprint is EMPTY OR Sprint in futureSprints())
    {"AND " + backlog_filter if backlog_filter else ""}
    """
