"""
Squad Delivery Pulse — Streamlit dashboard.

    streamlit run dashboard.py

Every number comes from report.generate_report(squad, sprint), the same function
that computes the report.
"""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import logging

import config
from log_setup import setup_logging
from ppt_export import build_deck
from report import generate_report

setup_logging()
log = logging.getLogger("dashboard")

ACCENT, BLUE, LIGHT_BLUE = "#E3C84A", "#4472C4", "#A9C4EB"
ORANGE, GREEN, TAN, RED, GREY, INK = "#ED7D31", "#4E8B5F", "#D9925B", "#C0504D", "#A6A6A6", "#2B2B2B"

st.set_page_config(page_title="Squad Delivery Pulse", page_icon="📊", layout="wide")
st.markdown(f"""
<style>
  .block-container {{padding-top: 3.2rem; max-width: 1400px;}}
  .topbar {{height: 6px; background: {ACCENT}; border-radius: 3px; margin-bottom: .6rem;}}
  .eyebrow {{letter-spacing: .18em; font-size: .72rem; font-weight: 600; color: #555;}}
  .kpi {{background: #fff; border: 1px solid #e6e6e6; border-radius: 8px; padding: 14px 18px; height: 128px;}}
  .kpi .lbl {{letter-spacing: .14em; font-size: .7rem; font-weight: 700; color: #555;}}
  .kpi .val {{font-size: 2.1rem; font-weight: 700; color: {INK}; margin: 6px 0 2px;}}
  .kpi .sub {{font-size: .8rem; color: #666;}}
  .panel {{background: #fafafa; border: 1px solid #ececec; border-radius: 8px; padding: 14px 18px;}}
  .panel h4 {{letter-spacing: .14em; font-size: .75rem; font-weight: 700; color: #555; margin: 0 0 10px;}}
  .row {{display: grid; grid-template-columns: 140px 1fr; gap: 10px; padding: 8px 0;
         border-bottom: 1px solid #eee; font-size: .88rem;}}
  .evt {{display: grid; grid-template-columns: 90px 50px 1fr; gap: 8px; padding: 6px 0;
         border-bottom: 1px solid #eee; font-size: .85rem;}}
  .legend {{display: grid; grid-template-columns: 18px 1fr 50px; gap: 8px; padding: 12px 0; font-size: .9rem;
            border-bottom: 1px solid #eee;}}
  .alloc {{width: 100%; border-collapse: collapse; font-size: .86rem;}}
  .alloc th {{background: #1f1f1f; color: #fff; text-align: left; padding: 12px 10px; font-weight: 600;}}
  .alloc td {{padding: 12px 10px; border-bottom: 1px solid #e6e6e6;}}
  .alloc tr:nth-child(even) td {{background: #fafafa;}}
  .alloc td.num {{text-align: center;}}
  .alloc td.bad {{color: {RED}; font-weight: 700; text-align: center;}}
  .alloc td.note {{color: #555;}}
  .prompt {{display: grid; grid-template-columns: 22px 1fr; gap: 8px; padding: 10px 0; font-size: .9rem;}}
  .dot {{width: 14px; height: 14px; border-radius: 50%; margin-top: 3px;}}
  .callout {{background: #F3EAD9; border: 1px solid #E0CFAE; border-radius: 6px; padding: 10px 12px;
             font-size: .78rem; color: #444; margin-top: 12px;}}
  .footer {{font-size: .72rem; color: #888; margin-top: 1.5rem; border-top: 1px solid #eee; padding-top: 6px;}}
  @media (prefers-color-scheme: dark) {{
    .kpi, .panel {{background: #1e1e1e; border-color: #333;}} .kpi .val {{color: #eee;}}
  }}
</style>""", unsafe_allow_html=True)


@st.cache_data(ttl=900, show_spinner="Pulling sprint data from Jira…")
def load(squad: str, sprint: str) -> dict:
    return generate_report(squad, sprint)


def kpi(col, label, value, sub, color):
    col.markdown(f'<div class="kpi" style="border-left:6px solid {color}"><div class="lbl">{label}</div>'
                 f'<div class="val">{value}</div><div class="sub">{sub}</div></div>', unsafe_allow_html=True)


def layout(fig, title, height=360):
    fig.update_layout(height=height, margin=dict(l=10, r=10, t=40, b=10),
                      title=dict(text=title, x=0, font=dict(size=15)),
                      legend=dict(orientation="h", y=-0.15, x=0.5, xanchor="center"),
                      plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)", bargap=0.35)
    fig.update_yaxes(gridcolor="#e5e5e5", zeroline=False)
    return fig


def short(name: str, squad: str) -> str:
    return name.replace(f"{squad} ", "")


# ─────────────────────────────────────────────────────────────────────────────
# Header: squad + sprint selection, exports
# ─────────────────────────────────────────────────────────────────────────────
st.markdown('<div class="topbar"></div>', unsafe_allow_html=True)
h1, h2, h3, h4 = st.columns([3.4, 0.9, 1.1, 0.8])
with h1:
    st.markdown('<div class="eyebrow">SQUAD DELIVERY PULSE</div>', unsafe_allow_html=True)
    st.markdown("<h2 style='margin:0;white-space:nowrap'>Sprint pulse | one-page squad view</h2>",
                unsafe_allow_html=True)
with h2:
    squad = st.selectbox("Squad", list(config.SQUADS))
cfg = config.SQUADS[squad]
with h3:
    sprint = st.selectbox("Sprint", cfg["sprints"], index=len(cfg["sprints"]) - 1)
with h4:
    st.markdown("<div style='height:1.75rem'></div>", unsafe_allow_html=True)
    ppt_slot = st.empty()

try:
    r = load(squad, sprint)
except Exception as exc:
    log.exception("Could not load %s / %s", squad, sprint)
    st.error(f"Could not load {squad} · {sprint} from Jira.\n\n{exc}")
    st.stop()

st.write("")

# ─────────────────────────────────────────────────────────────────────────────
# Metrics
# ─────────────────────────────────────────────────────────────────────────────
committed, delivered = r["committed_sp"], r["delivered_sp"]
spill_sp, spill_n = r["spillover_sp"], r["spillover_count"]
avg_vel = float(r["average_velocity"])
hist_n = len(r["historical_df"])
pct = r["commitment_pct"]
carryover = committed - delivered
not_done = carryover - spill_sp
coverage = r["ready_coverage"]
bl = r["backlog_sp"]

velocity_sub = f"Avg {avg_vel:.0f} SP ({hist_n} prior sprints)" if hist_n else "No prior sprints for an average"
plan_sub = f"{delivered} of {committed} SP delivered"
ready_val = f"{coverage:.1f}" if hist_n else "—"
ready_sub = f"sprints of ready work ({bl['Ready']:.0f} SP)"
carry_sub = f"{spill_sp} SP finished late · {not_done} SP still open"

k1, k2, k3, k4 = st.columns(4)
kpi(k1, "VELOCITY", f"{r['velocity']} SP", velocity_sub, BLUE)
kpi(k2, "PLAN → DONE", f"{pct:.0f}%", plan_sub, GREEN)
kpi(k3, "READY BACKLOG", ready_val, ready_sub, TAN)
kpi(k4, "CARRYOVER", f"{carryover} SP", carry_sub, RED)
st.write("")

# ─────────────────────────────────────────────────────────────────────────────
# Velocity trend + narrative
# ─────────────────────────────────────────────────────────────────────────────
sh = r["sprint_history_df"]
names = [short(s, squad) for s in sh["Sprint"]]
completed_series = [int(v) for v in sh["Completed"]]
committed_series = [int(v) for v in sh["Committed"]]

direction = "above" if r["velocity"] >= avg_vel else "below"
what = (f"Velocity {r['velocity']} SP, {direction} the {avg_vel:.0f} SP average." if hist_n
        else f"Velocity {r['velocity']} SP.")
if carryover:
    what += f" {carryover} SP carried over."
why = f"{pct:.0f}% of committed work was delivered inside the sprint."
if hist_n:
    why += (f" {coverage:.1f} sprints of ready work in the backlog"
            + (" — pipeline is healthy." if coverage >= 1.5 else " — pipeline is thin."))
action_parts = []
if pct < 85:
    action_parts.append("Revisit commitment sizing: plan → done is under 85%.")
if hist_n and coverage < 1.5:
    action_parts.append(f"Refine backlog items to lift readiness beyond {coverage:.1f} sprints.")
if bl["Blocked"]:
    action_parts.append(f"Unblock {bl['Blocked']:.0f} SP of backlog work.")
if carryover:
    action_parts.append("Split or pair on stories at risk of carrying over.")
action = " ".join(action_parts) or "Keep commitment and refinement cadence as they are."

c1, c2 = st.columns([1.15, 1])
with c1:
    fig = go.Figure()
    fig.add_bar(x=names, y=completed_series, name="Completed SP", text=completed_series, textposition="outside",
                marker_color=[BLUE] * (len(names) - 1) + [ORANGE])
    if hist_n:
        fig.add_scatter(x=names, y=[avg_vel] * len(names), name=f"Avg ({avg_vel:.0f} SP)",
                        mode="lines", line=dict(color=GREY, dash="dot"))
    st.plotly_chart(layout(fig, "Velocity trend (selected sprint in orange)"), width="stretch")
with c2:
    st.markdown('<div class="panel"><h4>STATUS NARRATIVE</h4>'
                f'<div class="row"><b>What changed</b><span>{what}</span></div>'
                f'<div class="row"><b>Why it matters</b><span>{why}</span></div>'
                f'<div class="row"><b>Action next sprint</b><span>{action}</span></div></div>',
                unsafe_allow_html=True)
    with st.expander("Add notes"):
        st.text_area("Notes for this sprint", key=f"notes_{squad}_{sprint}",
                     placeholder="Context the numbers don't show…")

# ─────────────────────────────────────────────────────────────────────────────
# Velocity and backlog health
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### Velocity and backlog health")
st.caption("Use trend plus readiness to separate delivery pace from pipeline quality.")
c3, c4, c5 = st.columns([1.3, 0.8, 0.7])
with c3:
    fig = go.Figure()
    fig.add_bar(x=names, y=committed_series, name="Committed", marker_color=LIGHT_BLUE,
                text=committed_series, textposition="outside")
    fig.add_bar(x=names, y=completed_series, name="Completed", marker_color=BLUE,
                text=completed_series, textposition="outside")
    st.plotly_chart(layout(fig, "Completed vs. committed story points"), width="stretch")

bl_labels = ["Ready", "Needs refinement", "Blocked"]
bl_values = [bl[k] for k in bl_labels]
bl_total = sum(bl_values) or 1
with c4:
    fig = go.Figure(go.Pie(labels=bl_labels, values=bl_values, hole=0.62, sort=False,
                           marker=dict(colors=[GREEN, TAN, RED]), textinfo="text",
                           text=[f"{v / (sum(bl_values) or 1):.0%}" if v else "" for v in bl_values],
                           hovertemplate="%{label}: %{value} SP<extra></extra>"))
    fig.add_annotation(text=f"<b>{ready_val}</b><br>coverage", showarrow=False, font=dict(size=20))
    fig.update_layout(showlegend=False)
    st.plotly_chart(layout(fig, "Backlog depth by readiness"), width="stretch")
with c5:
    st.write("")
    st.write("")
    st.markdown("".join(
        f"<div class='legend'><div class='dot' style='background:{c}'></div><span>{l}<br>"
        f"<small style='color:#888'>{v:.0f} SP</small></span><b>{v / bl_total:.0%}</b></div>"
        for l, v, c in zip(bl_labels, bl_values, (GREEN, TAN, RED))), unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Burndown + spillover
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### Sprint burndown and scope movement")
bd = r["burndown_df"]
days = [pd.to_datetime(d).strftime("%m/%d") for d in bd["Date"]]
ideal = [round(float(v), 1) for v in (bd["Ideal Remaining"] if "Ideal Remaining" in bd else bd["Remaining SP"])]
remaining = [float(v) for v in bd["Remaining SP"]]
sprint_readout = (f"{remaining[-1]:.0f} SP remaining of {committed} SP · {delivered} SP delivered"
                  + (f" · {spill_sp} SP finished after sprint end." if spill_sp else "."))
sp_df = r["spillover_df"]

c6, c7 = st.columns([1.6, 1])
with c6:
    fig = go.Figure()
    fig.add_scatter(x=days, y=ideal, name="Ideal", mode="lines+markers", line=dict(color=GREY, dash="dot"))
    fig.add_scatter(x=days, y=remaining, name="Actual", mode="lines+markers", line=dict(color=BLUE, width=3))
    st.plotly_chart(layout(fig, "Remaining story points by sprint day"), width="stretch")
with c7:
    rows = "".join(f'<div class="evt"><b>{x["Key"]}</b><span>{x["Story Points"]} SP</span>'
                   f'<span>{x["Summary"]}</span></div>' for _, x in sp_df.iterrows()) \
        or '<div style="font-size:.85rem;color:#888">No spillover this sprint.</div>'
    st.markdown(f'<div class="panel"><h4>SPILLOVER</h4>{rows}'
                f'<h4 style="margin-top:18px">END-OF-SPRINT READOUT</h4>'
                f'<div style="font-size:.88rem">{sprint_readout}</div></div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Quarterly burndown
# ─────────────────────────────────────────────────────────────────────────────
qs, qdf = r["quarter_summary"], r["quarter_df"]
st.markdown("#### Quarterly burndown and scope movement")
st.caption("A burndown is most useful when scope changes and blockers are shown alongside remaining work.")
q_weeks = [pd.to_datetime(w).strftime("%m/%d/%Y") for w in qdf["Week"]]
q_ideal = [float(v) for v in qdf["Ideal Remaining"]]
q_actual = [float(v) for v in qdf["Remaining SP"].dropna()]
q_start_txt = f"{pd.to_datetime(qs['start']):%b} {pd.to_datetime(qs['start']).day}, {pd.to_datetime(qs['start']).year}"
q_end_txt = f"{pd.to_datetime(qs['end']):%b} {pd.to_datetime(qs['end']).day}, {pd.to_datetime(qs['end']).year}"
on_track = bool(q_actual) and q_actual[-1] <= q_ideal[len(q_actual) - 1]
q_rows = [
    ("Quarter period", f"{q_start_txt} to {q_end_txt}"),
    ("Total completed stories", str(qs["completed_stories"])),
    ("Total SP delivered", f"{qs['delivered_sp']:.0f}"),
    ("Quarter scope", f"{qs['scope_sp']:.0f} SP across {len(qs['sprints'])} sprints"),
    ("Status", "On or ahead of ideal" if on_track else "Behind ideal"),
]

c11, c12 = st.columns([1.6, 1])
with c11:
    fig = go.Figure()
    fig.add_scatter(x=q_weeks, y=q_ideal, name="Ideal", mode="lines+markers", line=dict(color=GREY))
    fig.add_scatter(x=q_weeks[:len(q_actual)], y=q_actual, name="Actual", mode="lines+markers",
                    line=dict(color=BLUE, width=3))
    fig.update_xaxes(tickangle=0, tickvals=q_weeks[::2], ticktext=[w[:5] for w in q_weeks[::2]])
    st.plotly_chart(layout(fig, f"Quarterly Burndown {qs['label']}"), width="stretch")
with c12:
    st.markdown('<div class="panel"><h4>END-OF-QUARTER READOUT</h4>'
                + "".join(f'<div class="row"><b>{k}</b><span>{v}</span></div>' for k, v in q_rows)
                + '</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Team allocation
# ─────────────────────────────────────────────────────────────────────────────
st.markdown("#### Team allocation and story-point distribution")
st.caption("Use this view for workload balance and support conversations, not productivity comparisons.")
iss = r["issues_df"]
done_by = dict(zip(r["assignee_df"]["Assignee"], r["assignee_df"]["Velocity"]))
spill_keys = sp_df.groupby("Assignee")["Key"].apply(", ".join).to_dict() if not sp_df.empty else {}
open_keys = (iss[iss["Status"] != "Done"].groupby("Assignee")["Key"].apply(", ".join).to_dict()
             if not iss.empty else {})
alloc_rows = []
if not iss.empty:
    for member, planned in iss.groupby("Assignee")["Story Points"].sum().items():
        done = int(done_by.get(member, 0))
        notes = ([f"Open: {open_keys[member]}"] if member in open_keys else []) + \
                ([f"Late: {spill_keys[member]}"] if member in spill_keys else [])
        alloc_rows.append([member, "Engineer", "100%", int(planned), done, int(planned) - done, "; ".join(notes)])
ALLOC_COLS = ["Team member", "Role", "Capacity", "Planned SP", "Done SP", "Carryover", "Support / note"]
ALLOC_NOTE = ("Interpret story points as a planning abstraction. Do not compare people "
              "across roles, story types or squads.")

plans = [row[3] for row in alloc_rows]
avg_plan = sum(plans) / len(plans) if plans else 0
heavy = [row[0] for row in alloc_rows if avg_plan and row[3] > 1.6 * avg_plan]
prompts = [("Team allocation is broadly balanced", "info") if not heavy
           else (f"Load concentrated on {', '.join(heavy)} — rebalance or pair", "warn")]
if any(row[5] for row in alloc_rows):
    prompts.append(("Pair on carried-over stories to improve predictability", "info"))
if hist_n and coverage < 1.5:
    prompts.append(("Backlog grooming needed to build next-sprint readiness", "warn"))

c9, c10 = st.columns([2.2, 1])
with c9:
    body = "".join(
        f"<tr><td>{a}</td><td>{b}</td><td class='num'>{c}</td><td class='num'>{d}</td><td class='num'>{e}</td>"
        f"<td class='{'bad' if f else 'num'}'>{f}</td><td class='note'>{g}</td></tr>"
        for a, b, c, d, e, f, g in alloc_rows)
    st.markdown("<table class='alloc'><thead><tr>" + "".join(f"<th>{h}</th>" for h in ALLOC_COLS)
                + f"</tr></thead><tbody>{body}</tbody></table>", unsafe_allow_html=True)
with c10:
    dots = {"info": BLUE, "warn": ACCENT}
    items = "".join(f"<div class='prompt'><div class='dot' style='background:{dots[k]}'></div><div>{t}</div></div>"
                    for t, k in prompts)
    st.markdown(f"<div class='panel'><h4>FACILITATION PROMPTS</h4>{items}"
                f"<div class='callout'>{ALLOC_NOTE}</div></div>", unsafe_allow_html=True)

st.markdown('<div class="footer">For team planning and delivery transparency, not individual performance '
            'ranking · Fidelity Internal Information</div>', unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
# Exports
# ─────────────────────────────────────────────────────────────────────────────
file_stub = f"{squad}_{short(sprint, squad)}".replace(" ", "_")

ppt_ctx = {
    "squad": squad, "sprint": short(sprint, squad),
    "cards": [("VELOCITY", f"{r['velocity']} SP", velocity_sub, "blue"),
              ("PLAN → DONE", f"{pct:.0f}%", plan_sub, "green"),
              ("READY BACKLOG", ready_val, ready_sub, "tan"),
              ("CARRYOVER", f"{carryover} SP", carry_sub, "red")],
    "sprint_names": names,
    "trend_series": [("Completed SP", completed_series)],
    "committed": committed_series, "completed": completed_series,
    "backlog_values": bl_values, "coverage": coverage,
    "what": what, "why": why, "action": action,
    "notes": st.session_state.get(f"notes_{squad}_{sprint}", "").strip(),
    "days": days, "ideal": ideal, "remaining": remaining,
    "events": [], "sprint_readout": sprint_readout, "events_title": "SPILLOVER",
    "event_rows": [(x["Key"], f"{x['Story Points']} SP", x["Summary"]) for _, x in sp_df.iterrows()],
    "q_label": qs["label"], "q_weeks": [w[:5] for w in q_weeks], "q_ideal": q_ideal,
    "q_actual": q_actual, "q_rows": q_rows,
    "alloc_cols": ALLOC_COLS, "alloc_rows": alloc_rows, "prompts": prompts, "alloc_note": ALLOC_NOTE,
}
ppt_slot.download_button("⬇ PPT", data=build_deck(ppt_ctx), file_name=f"{file_stub}_Pulse.pptx",
                         mime="application/vnd.openxmlformats-officedocument.presentationml.presentation",
                         width="stretch")
