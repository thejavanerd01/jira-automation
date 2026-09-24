# Contributing

This guide explains where things live and how to change them safely.
Read README.md first for setup and metric definitions.

## Project layout

```
dashboard.py        Streamlit page: layout, charts, narrative text, PPT button
ppt_export.py       build_deck(ctx) → .pptx bytes (one _slide_* function per slide)
jira_client.py      jira_search(jql) → all pages from /rest/api/2/search/
config.py           squads, sprints, quarters, status names (+ .env loading)
log_setup.py        logging to terminal + logs/squad-pulse.log, level from LOG_LEVEL
report/             all the numbers
  __init__.py       generate_report(squad, sprint) — fetch → compute → return dict
  queries.py        every JQL string
  issues.py         read one field from a Jira issue (story points, sprint, status…)
  sprint.py         selected sprint: committed, delivered, spillover, burndown
  history.py        previous sprints: velocity, committed vs completed
  backlog.py        backlog readiness and coverage
  quarter.py        quarterly burndown
  __main__.py       python -m report CST1  (prints the summary, no UI)
  diagnose.py       python -m report.diagnose CST1  (checks the Jira setup)
tests/
  factory.py        story(...) builds a fake Jira issue
  test_report.py    unit tests + an end-to-end test with a fake Jira
```

**Data flow:** `dashboard.py` → `report.generate_report()` → `queries.*` →
`jira_search()` → section modules → a flat `dict`. `dashboard.py` draws it
and passes a `ppt_ctx` dict to `ppt_export.build_deck()`.

**Rules that keep this easy to change**
1. `report/` never imports Streamlit or python-pptx. It only returns data.
2. Only `issues.py` reads `issue["fields"][...]`. Other code calls its helpers.
3. Only `queries.py` builds JQL.
4. `dashboard.py` never calls Jira. It only reads the dict from `generate_report()`.
5. The dashboard and the PPT use the same computed values, so the screen and the deck always match.
6. Log with `log = logging.getLogger(__name__)`, not `print()`. Use INFO for one
   summary line per step, DEBUG for per-story detail, WARNING for bad data or
   config, and `log.exception(...)` in an `except` block. Never log the token.
   `log_setup.setup_logging()` is called once by each entry point (`dashboard.py`,
   `report/__main__.py`, `report/diagnose.py`); don't call it from library code.

## Dev setup

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest -q            # 19 tests, under a second, no Jira needed
```

Run the tests before and after every change.

---

## Recipes

### Change a metric rule
Example: count "Closed" as finished too.
- If it's a setting, change `config.py` (`DONE_STATUSES = ["Done", "Closed"]`).
- If it's logic, edit the function in the matching `report/*.py` module. Each
  module's docstring states its rules.
- Update the test that covers the rule, and README section 6.

### Change what Jira returns
Example: include Bugs as well as Stories.
Edit `report/queries.py`. `_squad_stories()` is shared by the sprint, history
and quarter queries, so one edit changes all of them. Run `python -m report CST1`
to see the new JQL printed and check the result.

### Read a new Jira field
Example: Epic Link.
1. Add the field id to the `"fields"` list in `jira_client.py`. Put it in
   `config.py` if the id differs between Jira instances.
2. Add a helper to `report/issues.py`, e.g.
   `def epic(issue): return issue["fields"].get(config.EPIC_FIELD)`.
3. Use the helper wherever you need it.

### Add a new number to an existing section
Example: average story size in the sprint.
1. Compute it in the section module (`report/sprint.py`), from the data it
   already has.
2. Add it to the returned dict in `report/__init__.py`, e.g.
   `"avg_story_sp": ...`.
3. Show it in `dashboard.py` (e.g. inside a `kpi(...)` call) and, if it belongs
   in the deck, add it to `ppt_ctx`.
4. Add a test in `tests/test_report.py` using `story(...)` from `factory.py`.

### Add a whole new report section
Example: bugs raised per sprint.
1. **Query:** add a function to `report/queries.py`.
2. **Logic:** create `report/bugs.py` with a function that takes a list of
   issues and returns DataFrames or numbers. No Jira calls inside.
3. **Wire it:** in `report/__init__.py`, call
   `search(queries.your_query(...))`, pass the issues to your function, and add
   the results to the returned dict.
4. **Show it:** in `dashboard.py`, copy an existing block (between two
   `# ───` banner comments) and change it to read your new keys.
5. **Slide (optional):** in `ppt_export.py`, copy `_slide_quarter_burndown` as a
   starting point. Use the helpers: `_chrome` (title bar and footer), `_panel`,
   `_label_rows`, `_bar_chart`, `_line_chart`. Register the slide in
   `build_deck()` and pass its data through `ppt_ctx` in `dashboard.py`.
6. **Test:** add a unit test for your function, and extend `fake_jira` in the
   end-to-end test if the new query needs it.

### Change the look
- **Colours:** the constants at the top of `dashboard.py` and `ppt_export.py`
  (keep them the same in both).
- **Dashboard spacing and cards:** the CSS block in `dashboard.py`.
- **Slide positions:** measured in inches in each `_slide_*` function. Slides are
  13.333 × 7.5 in.

### Add a squad or a new sprint
Only `config.py` changes. See README section 8.

---

## Checking your change end to end

1. `python -m pytest -q`: all green.
2. `python -m report CST1`: the JQL is printed and the numbers look right.
3. `streamlit run dashboard.py`: click through a few squads and sprints.
4. Click **⬇ PPT** and open the deck in PowerPoint.

## Writing a test

```python
from factory import S5, story
from report import sprint

def test_blocked_stories_are_not_delivered():
    items = [story("A", sp=5, status="Blocked", sprints=(S5,))]
    r = sprint.analyse_sprint(items, "2026-09-19")
    assert r.delivered_sp == 0 and r.committed_sp == 5
```

`story()` arguments: `key, sp, status, resolved="YYYY-MM-DD", sprints=(S4, S5),
assignee`. `S4` and `S5` are `(name, start, end)` tuples, and you can define
your own.
