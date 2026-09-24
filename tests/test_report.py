"""
Unit tests for the report — run with:  python -m pytest -q
They use hand-built issues (tests/factory.py), so no Jira connection is needed.
Each test states the rule it protects; if you change a rule on purpose,
update the test and README section 6 together.
"""

import re
from datetime import datetime

import pytest

import config
from factory import S4, S5, SQUAD, sprint_string, story
from report import backlog, generate_report, history, issues, quarter, sprint


# ── issues.py ────────────────────────────────────────────────────────────────
def test_parse_sprint_reads_name_and_dates():
    assert issues.parse_sprint(sprint_string(*S5)) == ("CST1 Q3-S5", "2026-09-08", "2026-09-19")


def test_parse_sprint_handles_missing_dates():
    text = "Sprint@1[id=9,state=FUTURE,name=CST1 Q4-S1,startDate=<null>,endDate=<null>]"
    assert issues.parse_sprint(text) == ("CST1 Q4-S1", None, None)


def test_parse_sprint_accepts_object_format():
    value = {"id": 5, "state": "active", "name": "CST1 Q3-S5",
             "startDate": "2026-09-08T09:00:00.000Z", "endDate": "2026-09-19T17:00:00.000Z"}
    assert issues.parse_sprint(value) == ("CST1 Q3-S5", "2026-09-08", "2026-09-19")
    assert issues.parse_sprint({"name": "Future", "state": "future"}) == ("Future", None, None)


def test_missing_story_points_count_as_zero():
    assert issues.story_points(story("A", sp=None)) == 0


def test_done_needs_done_status_and_resolution_date():
    assert issues.is_done(story("A", status="Done", resolved="2026-09-10"))
    assert not issues.is_done(story("B", status="Done", resolved=None))
    assert not issues.is_done(story("C", status="In Review", resolved="2026-09-10"))


# ── sprint.py ────────────────────────────────────────────────────────────────
def sample_sprint():
    return [
        story("A", sp=5, status="Done", resolved="2026-09-10", assignee="Dev One"),   # delivered
        story("B", sp=3, status="Done", resolved="2026-09-19", assignee="Dev Two"),   # delivered on last day
        story("C", sp=2, status="Done", resolved="2026-09-22", assignee="Dev Two"),   # spillover (late)
        story("D", sp=8, status="In Progress", assignee="Dev One"),                   # still open
    ]


def test_sprint_committed_delivered_spillover():
    r = sprint.analyse_sprint(sample_sprint(), "2026-09-19")
    assert r.committed_sp == 18          # every story
    assert r.delivered_sp == 8           # A + B (on or before end date)
    assert r.spillover_sp == 2           # C finished after end date
    assert r.spillover_count == 1
    assert r.commitment_pct == pytest.approx(44.44)
    assert dict(r.delivered_by_assignee) == {"Dev One": 5, "Dev Two": 3}


def test_burndown_subtracts_delivered_sp_per_day():
    r = sprint.analyse_sprint(sample_sprint(), "2026-09-19")
    df = sprint.burndown(r, "2026-09-08", "2026-09-19")
    assert len(df) == 12                                         # every calendar day
    assert df.set_index("Date").loc["2026-09-10", "Remaining SP"] == 13
    assert df["Remaining SP"].iloc[-1] == 10                     # 18 - 8 delivered
    assert df["Ideal Remaining"].iloc[0] == 18 and df["Ideal Remaining"].iloc[-1] == 0


def test_sprint_dates_from_jira_or_config_override():
    assert sprint.sprint_dates(SQUAD, "CST1 Q3-S5", sample_sprint()) == ("2026-09-08", "2026-09-19")
    squad = {**SQUAD, "sprint_dates": {"CST1 Q3-S5": ["2026-09-09", "2026-09-20"]}}
    assert sprint.sprint_dates(squad, "CST1 Q3-S5", []) == ("2026-09-09", "2026-09-20")
    with pytest.raises(Exception, match="Could not find start/end dates"):
        sprint.sprint_dates(SQUAD, "CST1 Q3-S5", [])


# ── history.py ───────────────────────────────────────────────────────────────
def test_previous_sprints_window():
    assert history.previous_sprints(["S1", "S2", "S3", "S4", "S5"], "S5", 2) == ["S3", "S4"]
    assert history.previous_sprints(["S1", "S2"], "S1", 4) == []


def test_carried_over_story_counts_once_for_velocity_but_in_each_sprint_for_commitment():
    carried = story("A", sp=5, status="Done", resolved="2026-09-03", sprints=(S4, S5))
    sprints = ["CST1 Q3-S4", "CST1 Q3-S5"]
    assert history.velocity_by_sprint([carried], sprints) == {"CST1 Q3-S4": 0, "CST1 Q3-S5": 5}
    assert history.committed_by_sprint([carried], sprints) == {"CST1 Q3-S4": 5, "CST1 Q3-S5": 5}


def test_average_velocity_is_zero_without_history():
    _, avg, table = history.history_tables([], {}, {}, "CST1 Q3-S1", 10, 8)
    assert avg == 0
    assert table.to_dict("records") == [{"Sprint": "CST1 Q3-S1", "Committed": 10, "Completed": 8}]


# ── backlog.py ───────────────────────────────────────────────────────────────
def test_readiness_is_case_insensitive_and_defaults_to_refinement(monkeypatch):
    monkeypatch.setattr(config, "BACKLOG_READY_STATUSES", ["Ready for Dev"])
    monkeypatch.setattr(config, "BACKLOG_BLOCKED_STATUSES", ["Blocked"])
    assert backlog.readiness("READY FOR DEV") == "Ready"
    assert backlog.readiness("blocked") == "Blocked"
    assert backlog.readiness("To Do") == "Needs refinement"


def test_ready_coverage_is_ready_sp_over_average_velocity(monkeypatch):
    monkeypatch.setattr(config, "BACKLOG_READY_STATUSES", ["Ready"])
    items = [story("A", sp=20, status="Ready", sprints=()), story("B", sp=5, status="To Do", sprints=())]
    _, sp, coverage, _ = backlog.analyse_backlog(items, average_velocity=10)
    assert sp == {"Ready": 20.0, "Needs refinement": 5.0, "Blocked": 0.0}
    assert coverage == 2.0


# ── quarter.py ───────────────────────────────────────────────────────────────
def test_quarterly_burndown_scope_and_cutoff():
    items = [
        story("A", sp=5, status="Done", resolved="2026-09-01", sprints=(S4,)),
        story("B", sp=3, status="Done", resolved="2026-09-15", sprints=(S5,)),
        story("C", sp=2, status="To Do", sprints=(S5,)),
    ]
    df, summary = quarter.quarterly_burndown(SQUAD, items, "2026-09-19", today=datetime(2026, 9, 16))
    assert summary["label"] == "Q3 2026"
    assert summary["scope_sp"] == 10 and summary["delivered_sp"] == 8 and summary["completed_stories"] == 2
    weeks = df.set_index("Week")["Remaining SP"]
    assert weeks["2026-07-05"] == 10          # first Sunday of the quarter
    assert weeks["2026-09-06"] == 5           # A done by then
    assert weeks["2026-09-13"] == 5           # B not yet (done 09-15)
    assert weeks.isna()["2026-09-20"]         # after "today": not plotted


# ── generate_report (end to end with a fake Jira) ───────────────────────────
def fake_jira(sprint_issues, backlog_issues):
    """A tiny stand-in for jira_search: filters issues by the sprint names in the JQL."""
    def search(jql):
        if "Sprint is EMPTY" in jql:
            return {"issues": backlog_issues}
        wanted = set(re.findall(r'"([^"]+)"', jql.split("Sprint", 1)[1]))
        found = [i for i in sprint_issues if wanted & set(issues.sprint_names(i))]
        if "statusCategory = Done" in jql:
            found = [i for i in found if issues.is_done(i)]
        return {"issues": found}
    return search


def test_generate_report_end_to_end(monkeypatch):
    monkeypatch.setitem(config.SQUADS, "TEST", SQUAD)
    monkeypatch.setattr(config, "BACKLOG_READY_STATUSES", ["Ready"])
    sprint_issues = sample_sprint() + [story("E", sp=6, status="Done", resolved="2026-09-02", sprints=(S4,))]
    backlog_issues = [story("F", sp=12, status="Ready", sprints=())]

    r = generate_report("TEST", search=fake_jira(sprint_issues, backlog_issues), today=datetime(2026, 9, 23))

    assert r["sprint_name"] == "CST1 Q3-S5"
    assert (r["committed_sp"], r["delivered_sp"], r["spillover_sp"]) == (18, 8, 2)
    assert r["historical_df"].to_dict("records") == [
        {"Sprint": "CST1 Q3-S3", "Velocity": 0}, {"Sprint": "CST1 Q3-S4", "Velocity": 6}]
    assert r["average_velocity"] == 3.0
    assert r["ready_coverage"] == 4.0                 # 12 ready SP / 3 avg velocity
    assert r["quarter_summary"]["scope_sp"] == 24     # 18 in S5 + 6 in S4
