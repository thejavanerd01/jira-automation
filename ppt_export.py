"""
PowerPoint export for the Squad Delivery Pulse dashboard.

build_deck(ctx) -> bytes of a .pptx whose 4 slides mirror the dashboard
(and the original deck): one-page squad view, velocity & backlog health,
sprint burndown, quarterly burndown. All charts are native PowerPoint
charts, so they stay editable after export.
"""

from __future__ import annotations

import io

from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.dml.color import RGBColor
from pptx.enum.chart import XL_CHART_TYPE, XL_LABEL_POSITION, XL_LEGEND_POSITION
from pptx.enum.dml import MSO_LINE_DASH_STYLE
from pptx.enum.shapes import MSO_SHAPE
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn
from pptx.util import Inches, Pt, Emu

# Same palette as the Streamlit UI
ACCENT = RGBColor(0xE3, 0xC8, 0x4A)
BLUE = RGBColor(0x44, 0x72, 0xC4)
LIGHT_BLUE = RGBColor(0xA9, 0xC4, 0xEB)
ORANGE = RGBColor(0xED, 0x7D, 0x31)
GREEN = RGBColor(0x4E, 0x8B, 0x5F)
TAN = RGBColor(0xD9, 0x92, 0x5B)
RED = RGBColor(0xC0, 0x50, 0x4D)
GREY = RGBColor(0xA6, 0xA6, 0xA6)
INK = RGBColor(0x2B, 0x2B, 0x2B)
MUTED = RGBColor(0x55, 0x55, 0x55)
SUBTLE = RGBColor(0x88, 0x88, 0x88)
PANEL = RGBColor(0xFA, 0xFA, 0xFA)
BORDER = RGBColor(0xE6, 0xE6, 0xE6)
GRID = RGBColor(0xE5, 0xE5, 0xE5)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
FONT = "Segoe UI"


# ─────────────────────────────────────────────────────────────────────────────
# Primitive helpers
# ─────────────────────────────────────────────────────────────────────────────
def _text(slide, x, y, w, h, text, size=12, bold=False, color=INK, spacing=None,
          align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP, wrap=True):
    tb = slide.shapes.add_textbox(Inches(x), Inches(y), Inches(w), Inches(h))
    tf = tb.text_frame
    tf.word_wrap = wrap
    tf.vertical_anchor = anchor
    for m in ("margin_left", "margin_right", "margin_top", "margin_bottom"):
        setattr(tf, m, 0)
    lines = text if isinstance(text, list) else [text]
    for i, line in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        r = p.add_run()
        r.text = line
        f = r.font
        f.size, f.bold, f.name = Pt(size), bold, FONT
        f.color.rgb = color
        if spacing:
            r._r.get_or_add_rPr().set("spc", str(spacing))
    return tb


def _rect(slide, x, y, w, h, fill, line=None, rounded=False):
    shp = slide.shapes.add_shape(
        MSO_SHAPE.ROUNDED_RECTANGLE if rounded else MSO_SHAPE.RECTANGLE,
        Inches(x), Inches(y), Inches(w), Inches(h))
    if rounded:
        shp.adjustments[0] = 0.06
    shp.fill.solid()
    shp.fill.fore_color.rgb = fill
    if line:
        shp.line.color.rgb = line
        shp.line.width = Pt(0.75)
    else:
        shp.line.fill.background()
    shp.shadow.inherit = False
    return shp


def _chrome(slide, title, subtitle=None, squad=None, sprint=None, title_size=28):
    """Yellow top bar, eyebrow, title, subtitle, squad/sprint pills, footer."""
    _rect(slide, 0, 0, 13.333, 0.12, ACCENT)
    _text(slide, 0.6, 0.4, 6, 0.3, "SQUAD DELIVERY PULSE", 10, True, MUTED, spacing=300)
    _text(slide, 0.6, 0.68, 8.85 if sprint else 10.45, 0.6, title, title_size, True, INK)
    if subtitle:
        _text(slide, 0.6, 1.3, 9, 0.35, subtitle, 13, False, MUTED)
    if squad:
        px = 9.55 if sprint else 11.2
        _rect(slide, px, 0.45, 1.55, 0.42, PANEL, BORDER, rounded=True)
        _text(slide, px, 0.45, 1.55, 0.42, f"SQUAD: {squad}", 10, True, INK,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    if sprint:
        _rect(slide, 11.2, 0.45, 1.55, 0.42, ACCENT, rounded=True)
        _text(slide, 11.2, 0.45, 1.55, 0.42, f"SPRINT: {sprint}", 10, True, INK,
              align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
    _rect(slide, 0.6, 6.95, 12.13, 0.012, BORDER)
    _text(slide, 0.6, 7.0, 8, 0.25,
          "For team planning and delivery transparency, not individual performance ranking",
          9, False, SUBTLE)
    _text(slide, 0.6, 7.2, 8, 0.25, "Fidelity Internal Information", 9, False, SUBTLE)


def _panel(slide, x, y, w, h, heading):
    _rect(slide, x, y, w, h, PANEL, BORDER, rounded=True)
    _text(slide, x + 0.25, y + 0.2, w - 0.5, 0.3, heading, 10, True, MUTED, spacing=250)


def _label_rows(slide, x, y, w, rows, label_w=1.7, row_h=0.62, size=11):
    for i, (label, value) in enumerate(rows):
        yy = y + i * row_h
        _text(slide, x, yy, label_w, row_h, label, size, True, INK)
        _text(slide, x + label_w, yy, w - label_w, row_h, value, size, False, INK)


def _style_chart(chart, title=None, legend=True, gridlines=True):
    chart.font.name = FONT
    chart.font.size = Pt(10)
    chart.font.color.rgb = MUTED
    if title:
        chart.has_title = True
        tf = chart.chart_title.text_frame
        tf.text = title
        r = tf.paragraphs[0].runs[0]
        r.font.size, r.font.bold, r.font.color.rgb = Pt(13), True, INK
    else:
        chart.has_title = False
    chart.has_legend = legend
    if legend:
        chart.legend.position = XL_LEGEND_POSITION.BOTTOM
        chart.legend.include_in_layout = False
        chart.legend.font.size = Pt(10)
    try:
        va = chart.value_axis
        va.has_major_gridlines = gridlines
        if gridlines:
            va.major_gridlines.format.line.color.rgb = GRID
        va.format.line.fill.background()
        va.tick_labels.font.size = Pt(9)
        ca = chart.category_axis
        ca.format.line.color.rgb = GRID
        ca.tick_labels.font.size = Pt(9)
    except (ValueError, AttributeError):
        pass  # doughnut has no axes


def _bar_chart(slide, x, y, w, h, cats, series, title):
    data = CategoryChartData()
    data.categories = cats
    for name, vals, _ in series:
        data.add_series(name, vals)
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(x), Inches(y),
                                   Inches(w), Inches(h), data).chart
    _style_chart(chart, title)
    plot = chart.plots[0]
    plot.gap_width, plot.overlap = 60, 0
    plot.has_data_labels = True
    dl = plot.data_labels
    dl.show_value, dl.position = True, XL_LABEL_POSITION.OUTSIDE_END
    dl.font.size, dl.font.color.rgb = Pt(10), MUTED
    for s, (_, _, color) in zip(plot.series, series):
        s.format.fill.solid()
        s.format.fill.fore_color.rgb = color
    return chart


def _line_chart(slide, x, y, w, h, cats, ideal, actual, title):
    data = CategoryChartData()
    data.categories = cats
    data.add_series("Ideal", ideal)
    data.add_series("Actual", actual)
    chart = slide.shapes.add_chart(XL_CHART_TYPE.LINE_MARKERS, Inches(x), Inches(y),
                                   Inches(w), Inches(h), data).chart
    _style_chart(chart, title)
    for s, color, width, dash in ((chart.plots[0].series[0], GREY, 1.75, True),
                                  (chart.plots[0].series[1], BLUE, 2.75, False)):
        s.smooth = False
        s.format.line.color.rgb = color
        s.format.line.width = Pt(width)
        if dash:
            s.format.line.dash_style = MSO_LINE_DASH_STYLE.DASH
        s.marker.format.fill.solid()
        s.marker.format.fill.fore_color.rgb = color
        s.marker.format.line.color.rgb = color
        s.marker.size = 6
    return chart


# ─────────────────────────────────────────────────────────────────────────────
# Slides
# ─────────────────────────────────────────────────────────────────────────────
def _slide_squad_view(prs, c):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _chrome(s, "Sprint pulse | one-page squad view", squad=c["squad"], sprint=c["sprint"])

    cards = [(lbl, val, sub, {"blue": BLUE, "green": GREEN, "tan": TAN, "red": RED}[col])
             for lbl, val, sub, col in c["cards"]] if c.get("cards") else [
        ("VELOCITY", f"{c['velocity']} SP", c["velocity_sub"], BLUE),
        ("PLAN → DONE", f"{c['plan_done']:.0%}", c["plan_done_sub"], GREEN),
        ("READY BACKLOG", f"{c['coverage']:.1f}", "sprints of ready work", TAN),
        ("CARRYOVER", f"{c['carryover']} SP", c["carryover_sub"], RED),
    ]
    cw, gap, cy = 2.9, 0.18, 1.45
    for i, (lbl, val, sub, color) in enumerate(cards):
        cx = 0.6 + i * (cw + gap)
        _rect(s, cx, cy, cw, 1.35, WHITE, BORDER)
        _rect(s, cx, cy, 0.08, 1.35, color)
        _text(s, cx + 0.3, cy + 0.2, cw - 0.4, 0.25, lbl, 9, True, MUTED, spacing=250)
        _text(s, cx + 0.3, cy + 0.45, cw - 0.4, 0.5, val, 28, True, INK)
        _text(s, cx + 0.3, cy + 0.98, cw - 0.35, 0.3, sub, 9, False, MUTED)

    series = ([(n, v, (BLUE, ORANGE)[i % 2]) for i, (n, v) in enumerate(c["trend_series"])]
              if c.get("trend_series") else
              [("EY Completed SP", c["ey_completed"], BLUE),
               ("Overall Squad SP", c["squad_total"], ORANGE)])
    _bar_chart(s, 0.5, 3.0, 6.7, 3.85, c["sprint_names"], series, "Velocity trend")

    _panel(s, 7.45, 3.05, 5.28, 3.75, "STATUS NARRATIVE")
    rows = [("What changed", c["what"]), ("Why it matters", c["why"]),
            ("Action next sprint", c["action"])]
    if c.get("notes"):
        rows.append(("Notes", c["notes"]))
    _label_rows(s, 7.7, 3.6, 4.85, rows, label_w=1.6,
                row_h=0.78 if len(rows) == 3 else 0.72, size=10.5)


def _slide_velocity_backlog(prs, c):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _chrome(s, "Velocity and backlog health",
            "Use trend plus readiness to separate delivery pace from pipeline quality.")
    _bar_chart(s, 0.5, 1.9, 6.9, 4.9, c["sprint_names"],
               [("Committed", c["committed"], LIGHT_BLUE),
                ("Completed", c["completed"], BLUE)],
               "Completed vs. committed story points")

    _text(s, 7.7, 1.95, 5, 0.3, "Backlog depth by readiness", 13, True, INK)
    labels = ["Ready", "Needs refinement", "Blocked"]
    vals = c["backlog_values"]
    data = CategoryChartData()
    data.categories = labels
    data.add_series("Backlog SP", vals)
    gf = s.shapes.add_chart(XL_CHART_TYPE.DOUGHNUT, Inches(7.55), Inches(2.4),
                            Inches(3.0), Inches(3.0), data)
    ch = gf.chart
    _style_chart(ch, legend=False)
    plot = ch.plots[0]
    hole = plot._element.find(qn("c:holeSize"))
    if hole is None:
        hole = plot._element.makeelement(qn("c:holeSize"), {})
        plot._element.append(hole)
    hole.set("val", "62")
    for pt, color in zip(plot.series[0].points, (GREEN, TAN, RED)):
        pt.format.fill.solid()
        pt.format.fill.fore_color.rgb = color
    _text(s, 7.55, 3.55, 3.0, 0.45, f"{c['coverage']:.1f}", 26, True, INK,
          align=PP_ALIGN.CENTER)
    _text(s, 7.55, 4.0, 3.0, 0.3, "coverage", 11, False, MUTED, align=PP_ALIGN.CENTER)

    total = sum(vals) or 1
    for i, (lbl, v, color) in enumerate(zip(labels, vals, (GREEN, TAN, RED))):
        yy = 2.75 + i * 0.75
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(10.85), Inches(yy + 0.06),
                                 Inches(0.16), Inches(0.16))
        dot.fill.solid(); dot.fill.fore_color.rgb = color; dot.line.fill.background()
        _text(s, 11.1, yy, 1.2, 0.3, lbl, 11, False, INK)
        _text(s, 12.2, yy, 0.55, 0.3, f"{v / total:.0%}", 11, True, INK, align=PP_ALIGN.RIGHT)


def _slide_sprint_burndown(prs, c):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _chrome(s, "Sprint burndown and scope movement",
            "A burndown is most useful when scope changes and blockers are shown alongside remaining work.",
            squad=c["squad"], sprint=c["sprint"])
    _line_chart(s, 0.5, 1.9, 7.9, 4.9, c["days"], c["ideal"], c["remaining"],
                "Remaining story points by sprint day")

    _panel(s, 8.7, 1.95, 4.03, 4.85, c.get("events_title", "SPRINT EVENTS"))
    y = 2.5
    if c.get("event_rows"):                        # generic (label, value, note) rows
        for label, value, note in c["event_rows"][:6]:
            _text(s, 8.95, y, 0.95, 0.45, label, 10.5, True, INK)
            _text(s, 9.9, y, 0.55, 0.45, value, 10.5, True, INK)
            _text(s, 10.45, y, 2.15, 0.5, note, 10, False, INK)
            y += 0.55
    elif c["events"]:
        for d, delta, note in c["events"]:
            _text(s, 8.95, y, 0.5, 0.45, f"D{d}", 11, True, INK)
            _text(s, 9.45, y, 0.8, 0.45, f"{delta:+d} SP", 11, True, INK)
            _text(s, 10.3, y, 2.3, 0.45, note, 10.5, False, INK)
            y += 0.55
    else:
        _text(s, 8.95, y, 3.5, 0.3, "No scope changes recorded.", 10.5, False, SUBTLE)
        y += 0.45
    y += 0.3
    _text(s, 8.95, y, 3.5, 0.3, "END-OF-SPRINT READOUT", 10, True, MUTED, spacing=250)
    _text(s, 8.95, y + 0.4, 3.55, 0.8, c["sprint_readout"], 11, False, INK)


def _slide_quarter_burndown(prs, c):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _chrome(s, "Quarterly burndown and scope movement",
            "A burndown is most useful when scope changes and blockers are shown alongside remaining work.",
            squad=c["squad"], sprint=c["sprint"], title_size=24)
    actual = c["q_actual"] + [None] * (len(c["q_weeks"]) - len(c["q_actual"]))
    _line_chart(s, 0.5, 1.9, 7.9, 4.9, c["q_weeks"], c["q_ideal"], actual,
                f"Quarterly Burndown {c['q_label']}")

    _panel(s, 8.7, 1.95, 4.03, 4.85, "END-OF-QUARTER READOUT")
    _label_rows(s, 8.95, 2.5, 3.6, c["q_rows"], label_w=1.5, row_h=0.5, size=11)


def _slide_team_allocation(prs, c):
    s = prs.slides.add_slide(prs.slide_layouts[6])
    _chrome(s, "Team allocation and story-point distribution",
            "Use this view for workload balance and support conversations, not productivity comparisons.",
            squad=c["squad"], sprint=c["sprint"], title_size=24)
    cols, rows = c["alloc_cols"], c["alloc_rows"]
    widths = [1.5, 1.15, 0.85, 0.95, 0.8, 1.0, 2.15]          # inches, sums to 8.4
    row_h = min(0.62, 4.3 / (len(rows) + 1))
    tbl = s.shapes.add_table(len(rows) + 1, len(cols), Inches(0.6), Inches(1.95),
                             Inches(sum(widths)), Inches(row_h * (len(rows) + 1))).table
    for i, w in enumerate(widths):
        tbl.columns[i].width = Inches(w)
    centered = {2, 3, 4, 5}

    def fill(cell, text, bg, color=INK, bold=False, size=10.5, center=False):
        cell.fill.solid()
        cell.fill.fore_color.rgb = bg
        cell.vertical_anchor = MSO_ANCHOR.MIDDLE
        cell.margin_left = cell.margin_right = Inches(0.08)
        tf = cell.text_frame
        tf.word_wrap = True
        p = tf.paragraphs[0]
        p.alignment = PP_ALIGN.CENTER if center else PP_ALIGN.LEFT
        r = p.add_run()
        r.text = str(text)
        r.font.size, r.font.bold, r.font.name = Pt(size), bold, FONT
        r.font.color.rgb = color

    for j, h in enumerate(cols):
        fill(tbl.cell(0, j), h, RGBColor(0x1F, 0x1F, 0x1F), WHITE, True, 9.5, j in centered)
    for i, r in enumerate(rows, start=1):
        bg = PANEL if i % 2 == 0 else WHITE
        for j, v in enumerate(r):
            bad = j == 5 and v
            fill(tbl.cell(i, j), v, bg, RED if bad else (MUTED if j == 6 else INK),
                 bool(bad), 10 if j == 6 else 10.5, j in centered)
    for i in range(len(rows) + 1):
        tbl.rows[i].height = Inches(row_h)
    # plain table look (turn off banding from the default style)
    tbl.first_row = True
    tbl.horz_banding = False

    _panel(s, 9.3, 1.95, 3.43, 4.85, "FACILITATION PROMPTS")
    y = 2.55
    for text, kind in c["prompts"]:
        dot = s.shapes.add_shape(MSO_SHAPE.OVAL, Inches(9.55), Inches(y + 0.05),
                                 Inches(0.18), Inches(0.18))
        dot.fill.solid()
        dot.fill.fore_color.rgb = ACCENT if kind == "warn" else BLUE
        dot.line.fill.background()
        _text(s, 9.9, y, 2.65, 0.6, text, 11, False, INK)
        y += 0.72
    _rect(s, 9.55, 5.85, 2.95, 0.7, RGBColor(0xF3, 0xEA, 0xD9), RGBColor(0xE0, 0xCF, 0xAE), rounded=True)
    _text(s, 9.7, 5.93, 2.65, 0.55, c["alloc_note"], 9, False, MUTED)


def build_deck(ctx: dict) -> bytes:
    prs = Presentation()
    prs.slide_width, prs.slide_height = Inches(13.333), Inches(7.5)
    _slide_squad_view(prs, ctx)
    if "backlog_values" in ctx:          # slides are included only when their data exists
        _slide_velocity_backlog(prs, ctx)
    _slide_sprint_burndown(prs, ctx)
    if "q_weeks" in ctx:
        _slide_quarter_burndown(prs, ctx)
    if ctx.get("alloc_rows"):
        _slide_team_allocation(prs, ctx)
    buf = io.BytesIO()
    prs.save(buf)
    return buf.getvalue()
