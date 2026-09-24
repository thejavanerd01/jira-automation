"""
Check the Jira setup for one squad and say exactly what to fix.

    python -m report.diagnose CST1
    python -m report.diagnose CST1 "CST1 Q3-S5"

Checks, in order:
  1. connection settings are filled in
  2. the custom field ids for Story Points and Sprint (looked up in Jira)
  3. the sprint name exists in Jira
  4. the squad's members match the assignees on that sprint's stories
  5. the sprint field on a real story carries the sprint's start/end dates
"""

import contextlib
import io
import sys

import config
from jira_client import jira_get, jira_search
from report import issues as iss
from report import queries

OK, WARN, FAIL = "  OK  ", " WARN ", " FAIL "


def say(tag, message):
    print(f"[{tag}] {message}")


def quiet(fn, *args, **kwargs):
    """Call jira_search without its JQL printout, to keep this report readable."""
    with contextlib.redirect_stdout(io.StringIO()):
        return fn(*args, **kwargs)


def check_settings():
    print("\n1. Connection settings")
    say(OK if config.JIRA_HOST != "jira.yourcompany.com" else FAIL, f"JIRA_HOST = {config.JIRA_HOST}")
    say(OK if config.BEARER_TOKEN else FAIL,
        "JIRA_BEARER_TOKEN is set" if config.BEARER_TOKEN else "JIRA_BEARER_TOKEN is empty — .env not loaded?")
    return bool(config.BEARER_TOKEN)


def check_field_ids():
    print("\n2. Custom field ids")
    try:
        fields = jira_get("/rest/api/2/field")
    except Exception as exc:
        say(FAIL, f"Could not read the field list: {exc}")
        return
    say(OK, "Connected to Jira")

    for label, setting, current, words in (
            ("Story Points", "STORY_POINTS_FIELD", config.STORY_POINTS_FIELD, ("story point",)),
            ("Sprint", "SPRINT_FIELD", config.SPRINT_FIELD, ("sprint",))):
        matches = [f for f in fields if f.get("custom") and any(w in f["name"].lower() for w in words)]
        ids = [f["id"] for f in matches]
        listing = ", ".join(f'{f["id"]} ("{f["name"]}")' for f in matches) or "none found"
        if current in ids:
            say(OK, f"{setting} = {current} ({label})")
        else:
            say(FAIL, f"{setting} = {current}, but Jira's {label} field(s): {listing}. "
                      f"Put the right id in .env as {setting}=...")


def check_sprint(squad, sprint):
    print(f"\n3. Sprint '{sprint}'")
    project_jql = f'project = {squad["project"]} AND Sprint = "{sprint}"'
    try:
        in_sprint = quiet(jira_search, project_jql)["issues"]
    except Exception as exc:
        say(FAIL, f"Jira rejected the sprint name (usually: no sprint with this exact name).\n        {exc}")
        suggest_sprint_names(squad)
        return None
    if not in_sprint:
        say(FAIL, f"No issues at all in this sprint in project {squad['project']}.")
        suggest_sprint_names(squad)
        return None
    say(OK, f"{len(in_sprint)} issues in project {squad['project']} are in this sprint")
    return in_sprint


def suggest_sprint_names(squad):
    try:
        recent = quiet(jira_search,
                       f'project = {squad["project"]} AND (Sprint in openSprints() OR Sprint in closedSprints()) '
                       f'ORDER BY updated DESC', limit=300)["issues"]
    except Exception:
        return
    names = sorted({n for i in recent for n in iss.sprint_names(i)})
    if names:
        print("        Sprint names Jira knows in this project (copy the exact spelling into config.py):")
        for name in names[-25:]:
            print(f"          {name}")


def check_members(squad, sprint, in_sprint):
    print("\n4. Squad members")
    mine = quiet(jira_search, queries.sprint_stories(squad, sprint))["issues"]
    if mine:
        say(OK, f"{len(mine)} stories in the sprint are assigned to the configured members")
        return mine
    assignees = sorted({(i["fields"]["assignee"] or {}).get("name", "?") + " / " +
                        (i["fields"]["assignee"] or {}).get("displayName", "?")
                        for i in in_sprint if i["fields"].get("assignee")})
    say(FAIL, "0 stories match `assignee IN (members)`. Members must be Jira usernames. "
              "Assignees on this sprint (username / display name):")
    for a in assignees:
        print(f"          {a}")
    return []


def check_sprint_dates(squad, sprint, stories):
    print("\n5. Sprint dates on a story")
    if squad.get("sprint_dates", {}).get(sprint):
        say(OK, f"Using sprint_dates from config.py: {squad['sprint_dates'][sprint]}")
        return
    sample = stories[0]
    raw = sample["fields"].get(config.SPRINT_FIELD)
    if not raw:
        say(FAIL, f"{sample['key']} has no value in {config.SPRINT_FIELD}. Fix SPRINT_FIELD (see check 2).")
        return
    parsed = [iss.parse_sprint(v) for v in raw]
    say(OK if any(p[0] == sprint and p[1] and p[2] for p in parsed) else FAIL,
        f"{sample['key']} sprint field parsed as (name, start, end): {parsed}")
    print(f"        raw value: {str(raw)[:400]}")


def main():
    squad_name = sys.argv[1] if len(sys.argv) > 1 else next(iter(config.SQUADS))
    squad = config.SQUADS[squad_name]
    sprint = sys.argv[2] if len(sys.argv) > 2 else squad["sprints"][-1]
    print(f"Diagnosing squad {squad_name}, sprint '{sprint}'")

    if not check_settings():
        return
    check_field_ids()
    in_sprint = check_sprint(squad, sprint)
    if in_sprint is None:
        return
    mine = check_members(squad, sprint, in_sprint)
    check_sprint_dates(squad, sprint, mine or in_sprint)
    print("\nDone. Fix every FAIL above, then run:  python -m report", squad_name)


if __name__ == "__main__":
    main()
