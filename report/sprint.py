"""
Metrics for the selected sprint: commitment, delivery, spillover, daily
burndown and per-assignee velocity.

Definitions (keep these in sync with README section 6):
  committed  = SP of every story in the sprint
  delivered  = SP of Done stories resolved on or before the sprint end date
  spillover  = SP of Done stories resolved after the sprint end date
  (stories that are not Done count toward committed only)
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import timedelta

import pandas as pd

import config
from . import issues as iss

log = logging.getLogger(__name__)

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
        log.info("Sprint '%s' dates from config.sprint_dates: %s → %s", sprint, override[0], override[1])
        return override[0], override[1]

    names_seen = set()
    for issue in sprint_issues:
        for value in iss.sprint_strings(issue):
            name, start, end = iss.parse_sprint(value)
            names_seen.add(name)
            if name and name.strip().casefold() == sprint.strip().casefold() and start and end:
                log.info("Sprint '%s' dates from Jira (%s): %s → %s", sprint, issue["key"], start, end)
                return start, end

    reason = _missing_dates_reason(sprint, sprint_issues, names_seen)
    log.warning(reason)
    if sprint_issues:
        log.debug("Raw sprint field on %s: %s", sprint_issues[0]["key"],
                  sprint_issues[0]["fields"].get(config.SPRINT_FIELD))
    raise Exception(reason)


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
            log.debug("%-12s %4s SP  %-14s resolved=%-10s -> OPEN (counts toward committed only)",
                      issue["key"], sp, iss.status_name(issue), iss.resolved_date(issue))
            continue

        day = iss.resolved_date(issue)
        if iss.to_date(day) <= end:
            log.debug("%-12s %4s SP  %-14s resolved=%-10s -> DELIVERED (%s)",
                      issue["key"], sp, iss.status_name(issue), day, who)
            result.delivered_sp += sp
            result.delivered_by_assignee[who] += sp
            result.delivered_by_day[day] += sp
        else:
            log.debug("%-12s %4s SP  %-14s resolved=%-10s -> SPILLOVER (after %s)",
                      issue["key"], sp, iss.status_name(issue), day, sprint_end)
            result.spillover_sp += sp
            result.spillover_count += 1
            result.spillover_rows.append({
                "Key": issue["key"],
                "Summary": fields["summary"],
                "Assignee": who,
                "Story Points": sp,
                "Resolved": resolved,
            })

    no_points = [i["key"] for i in sprint_issues if not iss.story_points(i)]
    if no_points:
        log.warning("%d stories have no story points (counted as 0): %s", len(no_points),
                    ", ".join(no_points[:20]) + (" …" if len(no_points) > 20 else ""))
    unresolved_done = [i["key"] for i in sprint_issues
                       if iss.status_name(i) in config.DONE_STATUSES and not iss.resolved_date(i)]
    if unresolved_done:
        log.warning("%d stories are %s but have no resolution date, so they are not counted as "
                    "delivered: %s", len(unresolved_done), "/".join(config.DONE_STATUSES),
                    ", ".join(unresolved_done[:20]))
    other_statuses = sorted({iss.status_name(i) for i in sprint_issues if iss.resolved_date(i)
                             and iss.status_name(i) not in config.DONE_STATUSES})
    if other_statuses:
        log.warning("Resolved stories with statuses not in DONE_STATUSES (not counted as delivered): %s. "
                    "Add them to DONE_STATUSES in config.py if they mean finished.", other_statuses)
    log.info("Sprint: %d stories, committed %s SP, delivered %s SP, spillover %s SP (%d stories), "
             "plan→done %s%%", len(sprint_issues), result.committed_sp, result.delivered_sp,
             result.spillover_sp, result.spillover_count, result.commitment_pct)
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
