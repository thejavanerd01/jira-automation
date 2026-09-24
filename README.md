# Squad Delivery Pulse

A Streamlit dashboard that builds the **Squad Delivery Pulse** sprint report from
Jira. Pick a squad and a sprint, and the page shows the same five views as the
deck. One click exports them as an editable PowerPoint.

```
Jira REST API ──► jira_client.py ──► report/ ──► dashboard.py ──► browser
 (/rest/api/2/search/)  (fetch, page)   (all metrics)  (charts + UI)
                                                           │
                                                           └──► ppt_export.py ──► .pptx
```

---

## 1. Contents

| File | What it does |
|---|---|
| `dashboard.py` | Streamlit UI. Squad/sprint selectors, the five report sections, the PPT download |
| `report/` | `generate_report(squad, sprint)`: runs the Jira queries and computes every number the UI shows. One module per section (see CONTRIBUTING.md) |
| `jira_client.py` | `jira_search(jql)`: POSTs JQL to `/rest/api/2/search/` with a bearer token and returns all pages |
| `ppt_export.py` | `build_deck(ctx)`: builds the 5-slide deck with native, editable PowerPoint charts |
| `config.py` | Squads, sprint lists, quarters, backlog status names. Reads connection settings from `.env` |
| `.env.example` | Template for `.env` (host, token, custom field IDs) |
| `requirements.txt` | Python packages |
| `tests/` | Unit tests that run without Jira: `python -m pytest -q` |
| `CONTRIBUTING.md` | How the code is organised and how to change it |

---

## 2. Prerequisites

- **Python 3.9 or newer** (`python --version`)
- **Package access:** `pip` can install from PyPI or your company mirror
- **Network:** the machine can reach Jira over HTTPS directly. `jira_client.py`
  does not use an HTTP proxy.
- **Jira Server / Data Center** with a **Personal Access Token**
  (Jira → your avatar → Profile → Personal Access Tokens → Create token)

---

## 3. Setup (one time)

### 3.1 Install

**macOS / Linux**
```bash
cd squad-pulse
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

**Windows (Command Prompt)**
```bat
cd squad-pulse
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

### 3.2 Fill in `.env`

```ini
JIRA_HOST=jira.yourcompany.com          # host only, no https://
JIRA_BEARER_TOKEN=<your personal access token>
STORY_POINTS_FIELD=customfield_XXXXX
SPRINT_FIELD=customfield_XXXXX
# JIRA_CA_BUNDLE=C:\certs\corp-ca.pem    # only if you get SSL certificate errors
```

To find the two custom field IDs, open `https://<JIRA_HOST>/rest/api/2/field`
in a browser where you're logged in to Jira. Search the page for
`"Story Points"` and `"Sprint"`, and copy each `"id"` (for example
`customfield_10002`).

`.env` holds your token. Don't commit it (it's already in `.gitignore`).

### 3.3 Fill in `config.py`

**Squads.** Add one entry per squad:

```python
SQUADS = {
    "CST1": {
        "project": "CST",                                  # Jira project key
        "members": ["jdoe", "asmith", "bkumar"],           # Jira usernames (not display names)
        "sprints": ["CST1 Q3-S1", "CST1 Q3-S2",            # exact sprint names, oldest → newest
                    "CST1 Q3-S3", "CST1 Q3-S4", "CST1 Q3-S5"],
        "backlog_filter": 'labels = "CST1"',               # JQL that selects this squad's backlog
        # "sprint_dates": {"CST1 Q3-S5": ["2026-09-08", "2026-09-19"]},   # optional override
    },
}
```

- **`members`**: the usernames used in `assignee IN (...)`. To find a username,
  open the person's Jira profile and read it from the URL (`?name=jdoe`).
- **`sprints`**: spelled exactly as in Jira. The last one is the default in the
  dropdown.
- **`backlog_filter`**: any JQL that picks the squad's backlog stories, such as
  `labels = "CST1"`, `component = "Household API"` or `"Team" = 123`. Leave it
  empty to use the whole project backlog.
- **`sprint_dates`**: only needed if a sprint has no start/end date in Jira.

**Backlog readiness.** List your workflow's status names:

```python
BACKLOG_READY_STATUSES   = ["Ready", "Ready for Dev", "Groomed"]
BACKLOG_BLOCKED_STATUSES = ["Blocked", "On Hold"]
```

Any other status counts as **Needs refinement**.

**Other settings**
- `HISTORY_SPRINTS = 4`: how many earlier sprints feed the average velocity
- `DONE_STATUSES = ["Done"]`: status names that count as finished
- `QUARTERS`: quarter start and end dates for the quarterly burndown

---

## 4. Run

### 4.1 Test the Jira connection first

```bash
python -m report CST1                    # latest sprint in the CST1 list
python -m report CST1 "CST1 Q3-S3"       # a specific sprint
```

Each JQL query and `Response status: 200` are printed, followed by a summary:

```
CST1 · CST1 Q3-S5 (2026-09-08 → 2026-09-19)

           Metric  Value
     Committed SP  45.00
     Delivered SP  39.00
     Spillover SP   6.00
Spillover Stories   2.00
         Velocity  39.00
     Commitment %  86.67
```

If you get an error instead, run the setup check. It tests each part against
your Jira and tells you what to fix:

```bash
python -m report.diagnose CST1
```

It checks the connection, looks up the correct `STORY_POINTS_FIELD` /
`SPRINT_FIELD` ids, confirms the sprint name (and lists the real names if yours
doesn't match), compares `members` with the sprint's actual assignees, and shows
the raw sprint field with the dates it read. See also section 9.

### 4.2 Start the dashboard

```bash
streamlit run dashboard.py
```

Open **http://localhost:8501**.

To let colleagues on the same network open it, run:
```bash
streamlit run dashboard.py --server.address 0.0.0.0
```
Then share `http://<your-machine-name>:8501`.

Stop the dashboard with **Ctrl+C**.

---

## 5. Using the dashboard

1. **Squad**: pick a squad from `config.SQUADS`.
2. **Sprint**: pick any sprint in that squad's list. The latest is selected by
   default.
3. Read the five sections (section 6).
4. **Add notes** (under the status narrative): optional free text. It is added
   to slide 1 of the PowerPoint.
5. **⬇ PPT**: downloads `<squad>_<sprint>_Pulse.pptx`.

Results are cached for **15 minutes** per squad and sprint. To pull fresh data
sooner, stop and restart the dashboard.

---

## 6. What each section shows

### 6.1 Sprint pulse | one-page squad view

**KPI cards**

| Card | Formula |
|---|---|
| **Velocity** | SP of stories in a `DONE_STATUSES` status (default `Done`) resolved **on or before** the sprint end date. The subtitle shows the average of the previous `HISTORY_SPRINTS` sprints |
| **Plan → Done** | Velocity ÷ committed SP (committed = SP of every story in the sprint) |
| **Ready backlog** | Ready backlog SP ÷ average velocity = how many sprints of ready work are available |
| **Carryover** | Committed − delivered. Subtitle splits it into *finished late* (Done after the sprint end) and *still open* (not Done) |

**Velocity trend**: completed SP for the previous sprints plus the selected one
(orange), with a dotted average line.

**Status narrative**: generated from the numbers:
- *What changed*: velocity vs. average, carryover
- *Why it matters*: plan → done %, and ready coverage (healthy if ≥ 1.5 sprints)
- *Action next sprint*: added when plan → done < 85%, coverage < 1.5, backlog
  has blocked SP, or anything carried over

### 6.2 Velocity and backlog health

- **Completed vs. committed**: per sprint. Committed = all stories in that
  sprint. Completed = Done stories counted against their most recent sprint
- **Backlog depth by readiness**: SP split into Ready / Needs refinement /
  Blocked, with ready coverage in the centre

### 6.3 Sprint burndown and scope movement

- **Actual**: committed SP minus SP completed each day (by resolution date)
- **Ideal**: a straight line from committed SP down to 0 on the last day
- **Spillover panel**: stories finished after the sprint end
- **End-of-sprint readout**: remaining, delivered and late SP

### 6.4 Quarterly burndown and scope movement

- **Quarter**: the entry in `config.QUARTERS` that contains the selected
  sprint's end date
- **Scope**: every story from the squad's sprints that end inside the quarter,
  each counted once
- **Actual**: scope minus Done SP resolved by each Sunday checkpoint. It stops
  at today
- **Ideal**: a straight line from scope down to 0 at quarter end
- **Readout**: quarter period, completed stories, SP delivered, scope, and
  on-track status

### 6.5 Team allocation and story-point distribution

- One row per assignee: **Planned SP** (their stories in the sprint),
  **Done SP** (delivered inside the sprint), **Carryover** (planned − done),
  and notes listing their open and late story keys
- **Facilitation prompts**:
  - flags anyone whose planned SP is more than 1.6× the team average
  - suggests pairing when anything carried over
  - flags backlog grooming when ready coverage is under 1.5

Role shows as *Engineer* and capacity as *100%* for everyone. Jira doesn't hold
those, so edit them in `dashboard.py` if you want different values.

---

## 7. How the data flows

When you pick a squad and sprint, `generate_report()` runs these Jira queries
(each paged until complete):

| # | Purpose | JQL |
|---|---|---|
| 1 | Stories in the selected sprint | `project = P AND issuetype = Story AND assignee IN (members) AND Sprint = "<sprint>"` |
| 2 | Velocity history (Done only) | `... AND Sprint IN (<previous sprints>) AND statusCategory = Done` |
| 3 | Committed per previous sprint | `... AND Sprint IN (<previous sprints>)` |
| 4 | Backlog | `project = P AND issuetype = Story AND statusCategory != Done AND (Sprint is EMPTY OR Sprint in futureSprints()) AND <backlog_filter>` |
| 5 | Quarter scope | `... AND Sprint IN (<all squad sprints>)`, then filtered to sprints ending in the quarter |

Fields requested: `summary, assignee, status, created, resolutiondate`, plus
the story-points and sprint custom fields.

**Sprint dates** are read from the sprint field string that Jira Server returns:
`...[id=123,state=ACTIVE,name=CST1 Q3-S5,startDate=2026-09-08T...,endDate=2026-09-19T...]`.

**Stories that appear in several sprints** (carried over) count once, against
the most recent listed sprint, for velocity history.

**Order of work:**
1. `dashboard.py` calls `generate_report()` and caches the result for 15 minutes.
2. It then computes the derived views (narrative, allocation rows, prompts).
3. It passes one context dictionary to `ppt_export.build_deck()`, so the
   PowerPoint always matches the screen.

---

## 8. Every new sprint

1. Add the new sprint name to the end of each squad's `sprints` list in
   `config.py`.
2. When a new quarter starts, check it's in `QUARTERS`.
3. Restart the dashboard.

Team changes: update `members` for the squad.

---

## 9. Troubleshooting

| Symptom | Cause and fix |
|---|---|
| `Jira API Error (HTTP 401)` | Token missing, expired or wrong. Regenerate it and update `JIRA_BEARER_TOKEN` in `.env` |
| `Jira API Error (HTTP 400)` with `errorMessages` | Invalid JQL: usually a misspelled sprint name, a username that doesn't exist, or a bad `backlog_filter`. The printed JQL shows the exact query |
| `SSL: CERTIFICATE_VERIFY_FAILED` | Jira uses an internal certificate. Export your corporate root CA to a `.pem` file and set `JIRA_CA_BUNDLE` |
| `getaddrinfo failed` / connection timed out | This machine can't reach `JIRA_HOST` (VPN, firewall, or a proxy is needed) |
| All story points are 0 | `STORY_POINTS_FIELD` is wrong. Check `/rest/api/2/field` |
| `Jira returned 0 stories for sprint …` | The sprint name doesn't match Jira exactly, or `members` aren't Jira usernames. Run `python -m report.diagnose <SQUAD>` |
| `… none has the sprint field …` | `SPRINT_FIELD` is the wrong custom field id. `python -m report.diagnose <SQUAD>` prints the right one |
| `No start/end dates for sprint …` | The sprint has no dates in Jira. Add them under `sprint_dates` for that squad in `config.py` |
| Velocity looks too low | Your finished status isn't `Done`. Add its name to `DONE_STATUSES` in `config.py` |
| Backlog donut is empty | `backlog_filter` matches nothing. Test it in Jira's issue search first |
| Everything is "Needs refinement" | Add your ready status names to `BACKLOG_READY_STATUSES` |
| `No quarter in config.QUARTERS contains ...` | Add the quarter to `QUARTERS` |
| Old numbers after a Jira change | Results are cached for 15 minutes. Restart the dashboard |

---

## 10. Notes

- The report is for team planning and delivery transparency, not individual
  performance ranking (this line also appears on every slide).
- Assumes Jira Server / Data Center (`/rest/api/2`, bearer PAT, sprint field
  returned as a string). Jira Cloud uses a different auth scheme and sprint
  format and would need changes in `jira_client.py` and `report/issues.py`.
