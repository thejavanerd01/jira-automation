"""
Squad Delivery Pulse report.

    from report import generate_report
    result = generate_report("CST1", "CST1 Q3-S5")

generate_report() is the only entry point the dashboard uses. It runs the
Jira queries (report/queries.py), hands the issues to one module per report
section, and returns a flat dict. See CONTRIBUTING.md for how to add to it.

    report/
      issues.py    read fields from a Jira issue (story points, sprint, status…)
      queries.py   every JQL string
      sprint.py    selected sprint: committed, delivered, spillover, burndown
      history.py   previous sprints: velocity, committed vs completed
      backlog.py   backlog readiness and coverage
      quarter.py   quarterly burndown
"""

import logging
import time

import config
from jira_client import jira_search

from . import backlog, history, queries, quarter, sprint

log = logging.getLogger(__name__)


def generate_report(squad_name, sprint_name=None, search=jira_search, today=None):
    """
    Build every number the dashboard shows for one squad and sprint.

    squad_name   key in config.SQUADS
    sprint_name  one of that squad's sprints; defaults to the latest
    search       function(jql) -> {"issues": [...]}; tests pass a fake here
    today        datetime used to cut off the quarterly "actual" line (tests)
    """
    squad = config.SQUADS[squad_name]
    selected = sprint_name or squad["sprints"][-1]
    earlier = history.previous_sprints(squad["sprints"], selected, config.HISTORY_SPRINTS)
    started = time.perf_counter()
    log.info("Report start: squad=%s sprint='%s' history=%s", squad_name, selected, earlier)

    # ── 1. Fetch from Jira ────────────────────────────────────────────────
    sprint_issues = search(queries.sprint_stories(squad, selected))["issues"]
    done_history = search(queries.done_stories_in(squad, earlier))["issues"] if earlier else []
    all_history = search(queries.all_stories_in(squad, earlier))["issues"] if earlier else []
    backlog_issues = search(queries.backlog_stories(squad))["issues"]
    quarter_candidates = search(queries.all_stories_in(squad, squad["sprints"]))["issues"]

    # ── 2. Selected sprint ────────────────────────────────────────────────
    start, end = sprint.sprint_dates(squad, selected, sprint_issues)
    current = sprint.analyse_sprint(sprint_issues, end)
    burndown_df = sprint.burndown(current, start, end)
    summary_df, issues_df, assignee_df, spillover_df = sprint.tables(current)

    # ── 3. Previous sprints ───────────────────────────────────────────────
    velocity = history.velocity_by_sprint(done_history, earlier)
    committed = history.committed_by_sprint(all_history, earlier)
    historical_df, average_velocity, sprint_history_df = history.history_tables(
        earlier, velocity, committed, selected, current.committed_sp, current.delivered_sp)

    # ── 4. Backlog ────────────────────────────────────────────────────────
    backlog_df, backlog_sp, ready_coverage, backlog_summary_df = backlog.analyse_backlog(
        backlog_issues, average_velocity)

    # ── 5. Quarter ────────────────────────────────────────────────────────
    quarter_df, quarter_summary = quarter.quarterly_burndown(
        squad, quarter_candidates, end, today=today)

    log.info("Report done: squad=%s sprint='%s' in %.1f s", squad_name, selected,
             time.perf_counter() - started)

    return {
        # selected sprint
        "sprint_name": selected,
        "sprint_start": start,
        "sprint_end": end,
        "committed_sp": current.committed_sp,
        "delivered_sp": current.delivered_sp,
        "spillover_sp": current.spillover_sp,
        "spillover_count": current.spillover_count,
        "velocity": current.delivered_sp,
        "commitment_pct": current.commitment_pct,
        "summary_df": summary_df,
        "issues_df": issues_df,
        "burndown_df": burndown_df,
        "assignee_df": assignee_df,
        "spillover_df": spillover_df,
        # history
        "historical_df": historical_df,
        "average_velocity": average_velocity,
        "sprint_history_df": sprint_history_df,
        # backlog
        "backlog_df": backlog_df,
        "backlog_summary_df": backlog_summary_df,
        "backlog_sp": backlog_sp,
        "ready_coverage": ready_coverage,
        # quarter
        "quarter_df": quarter_df,
        "quarter_summary": quarter_summary,
    }
