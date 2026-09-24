"""
Quarterly burndown.

  quarter  = the entry in config.QUARTERS containing the selected sprint's end date
  scope    = SP of every story from the squad's sprints that END inside the quarter
             (each story counted once)
  weekly checkpoints = every Sunday from the first Sunday of the quarter
  Remaining SP  = scope − SP of those stories resolved as Done by the checkpoint
                  (left empty for checkpoints after today)
  Ideal         = straight line from scope to 0 at the last checkpoint
"""

from collections import defaultdict
from datetime import datetime, timedelta

import pandas as pd

import config
from . import issues as iss


def quarter_for(date_str):
    """(label, start, end) of the configured quarter containing date_str."""
    for label, (start, end) in config.QUARTERS.items():
        if start <= date_str <= end:
            return label, start, end
    raise Exception(f"No quarter in config.QUARTERS contains {date_str}.")


def stories_in_quarter(squad, candidate_issues, q_start, q_end):
    """
    Keep issues that were in at least one of the squad's sprints ending inside
    the quarter. Returns (issues, names of those sprints in configured order).
    """
    kept, sprints_seen = [], set()
    for issue in candidate_issues:
        in_quarter = False
        for text in iss.sprint_strings(issue):
            name, _, end = iss.parse_sprint(text)
            override = squad.get("sprint_dates", {}).get(name)
            end = override[1] if override else end
            if name in squad["sprints"] and end and q_start <= end <= q_end:
                in_quarter = True
                sprints_seen.add(name)
        if in_quarter:
            kept.append(issue)
    return kept, [s for s in squad["sprints"] if s in sprints_seen]


def sundays(q_start, q_end):
    start, end = iss.to_date(q_start), iss.to_date(q_end)
    day = start + timedelta(days=(6 - start.weekday()) % 7)
    weeks = []
    while day <= end:
        weeks.append(day.strftime(iss.DATE_FORMAT))
        day += timedelta(days=7)
    return weeks


def quarterly_burndown(squad, candidate_issues, sprint_end, today=None):
    """Returns (quarter_df, quarter_summary dict)."""
    label, q_start, q_end = quarter_for(sprint_end)
    quarter_issues, quarter_sprints = stories_in_quarter(squad, candidate_issues, q_start, q_end)

    scope = sum(iss.story_points(i) for i in quarter_issues)
    done_by_day = defaultdict(float)
    completed_stories = 0
    for issue in quarter_issues:
        if iss.is_done(issue):
            done_by_day[iss.resolved_date(issue)] += iss.story_points(issue)
            completed_stories += 1

    as_of = min(today or datetime.now(), iss.to_date(q_end)).strftime(iss.DATE_FORMAT)
    weeks = sundays(q_start, q_end)

    rows = []
    for i, week in enumerate(weeks):
        ideal = scope * (1 - i / (len(weeks) - 1)) if len(weeks) > 1 else 0
        done_so_far = sum(sp for day, sp in done_by_day.items() if day <= week)
        rows.append({
            "Week": week,
            "Ideal Remaining": round(ideal, 1),
            "Remaining SP": (scope - done_so_far) if week <= as_of else None,
        })

    quarter_df = pd.DataFrame(rows, columns=["Week", "Ideal Remaining", "Remaining SP"])
    summary = {
        "label": label,
        "start": q_start,
        "end": q_end,
        "scope_sp": scope,
        "completed_stories": completed_stories,
        "delivered_sp": sum(done_by_day.values()),
        "sprints": quarter_sprints,
    }
    return quarter_df, summary
