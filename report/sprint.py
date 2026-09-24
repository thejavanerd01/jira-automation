"""
Metrics for the selected sprint: commitment, delivery, spillover, daily
burndown and per-assignee velocity.

Definitions (keep these in sync with README section 6):
  committed  = SP of every story in the sprint
  delivered  = SP of Done stories resolved on or before the sprint end date
  spillover  = SP of Done stories resolved after the sprint end date
  (stories that are not Done count toward committed only)
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

import config
from . import issues as iss

ISSUE_COLUMNS = ["Key", "Summary", "Assignee", "Status", "Story Points", "Created", "Resolved"]
SPILLOVER_COLUMNS = ["Key", "Summary", "Assignee", "Story Points", "Resolved"]


@dataclass
class SprintResult:
    committed_sp: float = 0
    delivered_sp: float = 0
    spillover_sp: float = 0
    spillover_count: int = 0
    issue_rows: list = field(default_factory=list)
    spillover_rows: list = field(default_factory=list)
    delivered_by_day: dict = field(default_factory=lambda: defaultdict(float))
    delivered_by_assignee: dict = field(default_factory=lambda: defaultdict(float))

    @property
    def commitment_pct(self):
        """Delivered ÷ committed, as a percentage with 2 decimals."""
        return round(self.delivered_sp / self.committed_sp * 100, 2) if self.committed_sp else 0


def sprint_dates(squad, sprint, sprint_issues):
    """
    (start, end) as "YYYY-MM-DD".
    Uses squad["sprint_dates"][sprint] if configured, otherwise the dates in
    Jira's sprint field on any issue from that sprint.
    """
    override = squad.get("sprint_dates", {}).get(sprint)
    if override:
        return override[0], override[1]

    names_seen = set()
    for issue in sprint_issues:
        for value in iss.sprint_strings(issue):
            name, start, end = iss.parse_sprint(value)
            names_seen.add(name)
            if name and name.strip().casefold() == sprint.strip().casefold() and start and end:
                return start, end

    raise Exception(_missing_dates_reason(sprint, sprint_issues, names_seen))


def _missing_dates_reason(sprint, sprint_issues, names_seen):
    """Explain why no dates were found, so the fix is obvious."""
    tip = "Run  python -m report.diagnose <SQUAD>  to check the setup."
    if not sprint_issues:
        return (f"Jira returned 0 stories for sprint '{sprint}'. Check that the sprint name in "
                f"config.py matches Jira exactly and that 'members' are Jira usernames. {tip}")
    if not any(iss.sprint_strings(i) for i in sprint_issues):
        return (f"Jira returned {len(sprint_issues)} stories but none has the sprint field "
                f"'{config.SPRINT_FIELD}'. SPRINT_FIELD in .env is probably the wrong custom field id. {tip}")
    return (f"No start/end dates for sprint '{sprint}' on its stories. Sprint names found: "
            f"{sorted(n for n in names_seen if n)}. If the sprint has no dates in Jira, add them "
            f"under sprint_dates in config.py. {tip}")


def analyse_sprint(sprint_issues, sprint_end):
    """Walk the sprint's stories once and accumulate every sprint metric."""
    result = SprintResult()
    end = iss.to_date(sprint_end)

    for issue in sprint_issues:
        sp = iss.story_points(issue)
        who = iss.assignee_name(issue)
        fields = issue["fields"]
        resolved = fields.get("resolutiondate")

        result.committed_sp += sp
        result.issue_rows.append({
            "Key": issue["key"],
            "Summary": fields["summary"],
            "Assignee": who,
            "Status": iss.status_name(issue),
            "Story Points": sp,
            "Created": fields.get("created"),
            "Resolved": resolved,
        })

        if not iss.is_done(issue):
            continue

        day = iss.resolved_date(issue)
        if iss.to_date(day) <= end:
            result.delivered_sp += sp
            result.delivered_by_assignee[who] += sp
            result.delivered_by_day[day] += sp
        else:
            result.spillover_sp += sp
            result.spillover_count += 1
            result.spillover_rows.append({
                "Key": issue["key"],
                "Summary": fields["summary"],
                "Assignee": who,
                "Story Points": sp,
                "Resolved": resolved,
            })

    return result


def burndown(result, sprint_start, sprint_end):
    """
    One row per calendar day of the sprint:
      Remaining SP     = committed − SP delivered up to that day
      Ideal Remaining  = straight line from committed to 0
    """
    rows = []
    remaining = result.committed_sp
    day = iss.to_date(sprint_start)
    end = iss.to_date(sprint_end)

    while day <= end:
        key = day.strftime(iss.DATE_FORMAT)
        completed = result.delivered_by_day.get(key, 0)
        remaining -= completed
        rows.append({"Date": key, "Completed SP": completed, "Remaining SP": remaining})
        day += timedelta(days=1)

    df = pd.DataFrame(rows)
    total_days = len(df) - 1
    if total_days > 0:
        df["Ideal Remaining"] = [
            max(0, result.committed_sp - i * result.committed_sp / total_days)
            for i in range(len(df))
        ]
    return df


def tables(result):
    """DataFrames shown by the dashboard: summary, issues, assignees, spillover."""
    summary_df = pd.DataFrame([
        {"Metric": "Committed SP", "Value": result.committed_sp},
        {"Metric": "Delivered SP", "Value": result.delivered_sp},
        {"Metric": "Spillover SP", "Value": result.spillover_sp},
        {"Metric": "Spillover Stories", "Value": result.spillover_count},
        {"Metric": "Velocity", "Value": result.delivered_sp},
        {"Metric": "Commitment %", "Value": result.commitment_pct},
    ])
    issues_df = pd.DataFrame(result.issue_rows, columns=ISSUE_COLUMNS)
    assignee_df = pd.DataFrame(
        [{"Assignee": a, "Velocity": v} for a, v in result.delivered_by_assignee.items()],
        columns=["Assignee", "Velocity"],
    )
    spillover_df = pd.DataFrame(result.spillover_rows, columns=SPILLOVER_COLUMNS)
    return summary_df, issues_df, assignee_df, spillover_df
