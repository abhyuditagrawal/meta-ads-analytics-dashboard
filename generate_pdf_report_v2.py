"""
Replacement generate_pdf_report function for Meta Ads Dashboard.
Uses pure ReportLab drawings — NO Kaleido/Chrome dependency.
Drop this into your main app file, replacing the old generate_pdf_report function.
"""

from io import BytesIO
from datetime import datetime
from typing import Dict, List

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, landscape
from reportlab.lib.units import inch, mm
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.platypus import (
    SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer,
    PageBreak, KeepTogether, HRFlowable
)
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.graphics.shapes import Drawing, Rect, String, Line, Circle, Polygon
from reportlab.graphics.charts.barcharts import VerticalBarChart
from reportlab.graphics.charts.lineplots import LinePlot
from reportlab.graphics.widgets.markers import makeMarker
from reportlab.graphics import renderPDF


# ─────────────────────────────────────────────────────────
# COLOR PALETTE
# ─────────────────────────────────────────────────────────
class C:
    """Brand color constants"""
    PRIMARY = colors.HexColor('#1e40af')      # Deep blue
    PRIMARY_LIGHT = colors.HexColor('#3b82f6')
    PRIMARY_BG = colors.HexColor('#eff6ff')
    SUCCESS = colors.HexColor('#059669')
    SUCCESS_BG = colors.HexColor('#ecfdf5')
    WARNING = colors.HexColor('#d97706')
    WARNING_BG = colors.HexColor('#fffbeb')
    DANGER = colors.HexColor('#dc2626')
    DANGER_BG = colors.HexColor('#fef2f2')
    PURPLE = colors.HexColor('#7c3aed')
    PURPLE_BG = colors.HexColor('#f5f3ff')
    PINK = colors.HexColor('#db2777')
    PINK_BG = colors.HexColor('#fdf2f8')
    DARK = colors.HexColor('#111827')
    GRAY = colors.HexColor('#6b7280')
    LIGHT_GRAY = colors.HexColor('#f3f4f6')
    BORDER = colors.HexColor('#e5e7eb')
    WHITE = colors.white


# ─────────────────────────────────────────────────────────
# STYLES
# ─────────────────────────────────────────────────────────
def get_styles():
    styles = getSampleStyleSheet()

    styles.add(ParagraphStyle(
        'ReportTitle', parent=styles['Title'], fontSize=28,
        textColor=C.PRIMARY, spaceAfter=4, fontName='Helvetica-Bold',
        alignment=TA_LEFT, leading=34
    ))
    styles.add(ParagraphStyle(
        'ReportSubtitle', parent=styles['Normal'], fontSize=12,
        textColor=C.GRAY, spaceAfter=20, fontName='Helvetica',
        alignment=TA_LEFT
    ))
    styles.add(ParagraphStyle(
        'SectionHead', parent=styles['Heading2'], fontSize=16,
        textColor=C.PRIMARY, spaceAfter=10, spaceBefore=16,
        fontName='Helvetica-Bold', borderPadding=(0, 0, 4, 0)
    ))
    styles.add(ParagraphStyle(
        'SubSection', parent=styles['Heading3'], fontSize=12,
        textColor=C.DARK, spaceAfter=6, spaceBefore=8,
        fontName='Helvetica-Bold'
    ))
    styles.add(ParagraphStyle(
        'ReportBody', parent=styles['Normal'], fontSize=9,
        textColor=C.DARK, fontName='Helvetica', leading=13
    ))
    styles.add(ParagraphStyle(
        'SmallGray', parent=styles['Normal'], fontSize=8,
        textColor=C.GRAY, fontName='Helvetica'
    ))
    styles.add(ParagraphStyle(
        'KPIValue', parent=styles['Normal'], fontSize=22,
        textColor=C.DARK, fontName='Helvetica-Bold', alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        'KPILabel', parent=styles['Normal'], fontSize=8,
        textColor=C.GRAY, fontName='Helvetica', alignment=TA_CENTER
    ))
    styles.add(ParagraphStyle(
        'FooterStyle', parent=styles['Normal'], fontSize=7,
        textColor=C.GRAY, fontName='Helvetica', alignment=TA_CENTER
    ))
    return styles


# ─────────────────────────────────────────────────────────
# HELPER: Header / Footer
# ─────────────────────────────────────────────────────────
def _header_footer(canvas_obj, doc):
    canvas_obj.saveState()
    w, h = landscape(letter)

    # Top accent bar
    canvas_obj.setFillColor(C.PRIMARY)
    canvas_obj.rect(0, h - 6, w, 6, fill=1, stroke=0)

    # Footer line
    canvas_obj.setStrokeColor(C.BORDER)
    canvas_obj.setLineWidth(0.5)
    canvas_obj.line(40, 28, w - 40, 28)

    # Footer text
    canvas_obj.setFont('Helvetica', 7)
    canvas_obj.setFillColor(C.GRAY)
    canvas_obj.drawString(40, 16, f"Meta Ads Analytics Report  |  Generated {datetime.now().strftime('%B %d, %Y %I:%M %p')}")
    canvas_obj.drawRightString(w - 40, 16, f"Page {doc.page}")

    canvas_obj.restoreState()


# ─────────────────────────────────────────────────────────
# HELPER: KPI Card row (pure table-based, no images)
# ─────────────────────────────────────────────────────────
def make_kpi_row(items, styles):
    """items = list of (label, value, color_hex) tuples. Returns a Table."""
    cells_top = []
    cells_bot = []
    for label, value, col in items:
        cells_top.append(Paragraph(f"<font color='{col}'><b>{value}</b></font>", styles['KPIValue']))
        cells_bot.append(Paragraph(label, styles['KPILabel']))

    n = len(items)
    col_w = 9.5 * inch / n if n else 2.0 * inch
    t = Table([cells_top, cells_bot], colWidths=[col_w]*n, rowHeights=[36, 18])
    t.setStyle(TableStyle([
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('BOX', (0, 0), (-1, -1), 0.5, C.BORDER),
        ('INNERGRID', (0, 0), (-1, -1), 0.25, C.BORDER),
        ('BACKGROUND', (0, 0), (-1, -1), C.LIGHT_GRAY),
        ('TOPPADDING', (0, 0), (-1, 0), 6),
        ('BOTTOMPADDING', (0, 1), (-1, 1), 6),
    ]))
    return t


# ─────────────────────────────────────────────────────────
# HELPER: Metric table with rating colors
# ─────────────────────────────────────────────────────────
def _rating_color(rating):
    if rating == 'Excellent':
        return C.SUCCESS
    elif rating == 'Good':
        return colors.HexColor('#15803d')
    elif rating == 'Acceptable':
        return C.WARNING
    else:
        return C.DANGER


def _rating_bg(rating):
    if rating in ('Excellent', 'Good'):
        return C.SUCCESS_BG
    elif rating == 'Acceptable':
        return C.WARNING_BG
    else:
        return C.DANGER_BG


# ─────────────────────────────────────────────────────────
# HELPER: Pure ReportLab horizontal bar chart
# ─────────────────────────────────────────────────────────
def make_funnel_drawing(totals, width=680, height=320):
    """Create a horizontal funnel bar chart using pure ReportLab."""
    d = Drawing(width, height)

    stages = [
        ('Impressions', totals.get('impressions', 0)),
        ('Link Clicks', totals.get('clicks', 0)),
        ('Outbound Clicks', totals.get('outbound_clicks', 0)),
        ('LP Views', totals.get('lp_views', 0)),
        ('View Content', totals.get('view_content', 0)),
        ('Add to Cart', totals.get('adds_to_cart', 0)),
        ('Checkouts', totals.get('checkouts', 0)),
        ('Purchases', totals.get('purchases', 0)),
    ]

    bar_colors = [
        colors.HexColor('#1e3a8a'), colors.HexColor('#1d4ed8'),
        colors.HexColor('#2563eb'), colors.HexColor('#3b82f6'),
        colors.HexColor('#60a5fa'), colors.HexColor('#93c5fd'),
        colors.HexColor('#7c3aed'), colors.HexColor('#059669'),
    ]

    max_val = max(s[1] for s in stages) if stages else 1
    if max_val == 0:
        max_val = 1

    bar_h = 28
    gap = 6
    left_margin = 110
    max_bar_w = width - left_margin - 80
    y_start = height - 40

    # Title
    d.add(String(width / 2, height - 15, "Conversion Funnel", fontSize=12,
                 fontName='Helvetica-Bold', fillColor=C.DARK, textAnchor='middle'))

    for i, (label, val) in enumerate(stages):
        y = y_start - i * (bar_h + gap)
        bar_w = max(4, (val / max_val) * max_bar_w)

        # Bar
        d.add(Rect(left_margin, y - bar_h, bar_w, bar_h,
                    fillColor=bar_colors[i % len(bar_colors)], strokeColor=None))

        # Label on left
        d.add(String(left_margin - 6, y - bar_h + 8, label, fontSize=8,
                     fontName='Helvetica', fillColor=C.DARK, textAnchor='end'))

        # Value on bar
        val_str = f"{val:,.0f}"
        if val > 0 and stages[0][1] > 0:
            pct = val / stages[0][1] * 100
            val_str += f" ({pct:.1f}%)"
        text_x = left_margin + bar_w + 4
        d.add(String(text_x, y - bar_h + 8, val_str, fontSize=7,
                     fontName='Helvetica', fillColor=C.GRAY))

    return d


# ─────────────────────────────────────────────────────────
# HELPER: Pure ReportLab line trend chart
# ─────────────────────────────────────────────────────────
def make_daily_trend_drawing(daily_df, y_cols, title, width=680, height=240):
    """Create a simple multi-line trend chart."""
    d = Drawing(width, height)

    if daily_df is None or len(daily_df) == 0:
        d.add(String(width / 2, height / 2, "No data", fontSize=10,
                     fontName='Helvetica', fillColor=C.GRAY, textAnchor='middle'))
        return d

    line_colors = [
        colors.HexColor('#2563eb'), colors.HexColor('#059669'),
        colors.HexColor('#d97706'), colors.HexColor('#dc2626'),
        colors.HexColor('#7c3aed'), colors.HexColor('#db2777'),
        colors.HexColor('#0891b2'),
    ]

    d.add(String(width / 2, height - 10, title, fontSize=11,
                 fontName='Helvetica-Bold', fillColor=C.DARK, textAnchor='middle'))

    chart = LinePlot()
    chart.x = 50
    chart.y = 35
    chart.width = width - 80
    chart.height = height - 65

    all_data = []
    legend_items = []
    for ci, col in enumerate(y_cols):
        if col not in daily_df.columns:
            continue
        vals = daily_df[col].tolist()
        line_data = [(i, float(v)) for i, v in enumerate(vals)]
        all_data.append(line_data)
        legend_items.append((col, line_colors[ci % len(line_colors)]))

    if not all_data:
        return d

    chart.data = all_data

    for ci, (col_name, col_color) in enumerate(legend_items):
        chart.lines[ci].strokeColor = col_color
        chart.lines[ci].strokeWidth = 1.5
        chart.lines[ci].symbol = makeMarker('FilledCircle', size=2)

    chart.xValueAxis.labels.fontSize = 6
    chart.xValueAxis.labels.fontName = 'Helvetica'
    chart.xValueAxis.visibleGrid = True
    chart.xValueAxis.gridStrokeColor = C.BORDER
    chart.xValueAxis.gridStrokeWidth = 0.25

    chart.yValueAxis.labels.fontSize = 7
    chart.yValueAxis.labels.fontName = 'Helvetica'
    chart.yValueAxis.visibleGrid = True
    chart.yValueAxis.gridStrokeColor = C.BORDER
    chart.yValueAxis.gridStrokeWidth = 0.25

    # Show date labels for x axis (sample a few)
    n = len(daily_df)
    if n > 0:
        dates = daily_df['date'].tolist()
        step = max(1, n // 8)
        label_map = {}
        for i in range(0, n, step):
            try:
                label_map[i] = dates[i].strftime('%m/%d')
            except Exception:
                label_map[i] = str(i)
        chart.xValueAxis.labelTextFormat = lambda val, label_map=label_map: label_map.get(int(round(val)), '')

    d.add(chart)

    # Mini legend
    lx = 60
    for ci, (col_name, col_color) in enumerate(legend_items):
        ly = 10
        d.add(Rect(lx, ly, 8, 8, fillColor=col_color, strokeColor=None))
        d.add(String(lx + 11, ly + 1, col_name.replace('_', ' '), fontSize=6,
                     fontName='Helvetica', fillColor=C.GRAY))
        lx += len(col_name) * 4.5 + 22

    return d


# ─────────────────────────────────────────────────────────
# HELPER: Trend chart WITH benchmark lines (ideal + min)
# ─────────────────────────────────────────────────────────
def make_daily_trend_with_benchmark(daily_df, metric_col, ideal_val, min_val, title, width=680, height=180):
    """Create a line chart for a single metric with ideal and min benchmark lines."""
    d = Drawing(width, height)

    if daily_df is None or len(daily_df) == 0 or metric_col not in daily_df.columns:
        d.add(String(width / 2, height / 2, "No data", fontSize=10,
                     fontName='Helvetica', fillColor=C.GRAY, textAnchor='middle'))
        return d

    d.add(String(width / 2, height - 10, title, fontSize=9,
                 fontName='Helvetica-Bold', fillColor=C.DARK, textAnchor='middle'))

    chart = LinePlot()
    chart.x = 50
    chart.y = 30
    chart.width = width - 80
    chart.height = height - 55

    vals = daily_df[metric_col].tolist()
    n = len(vals)
    actual_data = [(i, float(v)) for i, v in enumerate(vals)]
    ideal_data = [(i, float(ideal_val)) for i in range(n)]
    min_data = [(i, float(min_val)) for i in range(n)]

    chart.data = [actual_data, ideal_data, min_data]

    # Actual line
    chart.lines[0].strokeColor = colors.HexColor('#2563eb')
    chart.lines[0].strokeWidth = 2
    chart.lines[0].symbol = makeMarker('FilledCircle', size=2)

    # Ideal line (green dashed)
    chart.lines[1].strokeColor = colors.HexColor('#059669')
    chart.lines[1].strokeWidth = 1.5
    chart.lines[1].strokeDashArray = [4, 2]

    # Min line (orange dotted)
    chart.lines[2].strokeColor = colors.HexColor('#d97706')
    chart.lines[2].strokeWidth = 1
    chart.lines[2].strokeDashArray = [2, 2]

    chart.xValueAxis.labels.fontSize = 5
    chart.xValueAxis.labels.fontName = 'Helvetica'
    chart.xValueAxis.visibleGrid = True
    chart.xValueAxis.gridStrokeColor = C.BORDER
    chart.xValueAxis.gridStrokeWidth = 0.2

    chart.yValueAxis.labels.fontSize = 6
    chart.yValueAxis.labels.fontName = 'Helvetica'
    chart.yValueAxis.visibleGrid = True
    chart.yValueAxis.gridStrokeColor = C.BORDER
    chart.yValueAxis.gridStrokeWidth = 0.2

    # Date labels
    if n > 0:
        dates = daily_df['date'].tolist()
        step = max(1, n // 8)
        label_map = {}
        for i in range(0, n, step):
            try:
                label_map[i] = dates[i].strftime('%m/%d')
            except Exception:
                label_map[i] = str(i)
        chart.xValueAxis.labelTextFormat = lambda val, label_map=label_map: label_map.get(int(round(val)), '')

    d.add(chart)

    # Legend
    lx = 60
    for label, col in [('Actual', '#2563eb'), ('Ideal', '#059669'), ('Min', '#d97706')]:
        d.add(Rect(lx, 8, 8, 8, fillColor=colors.HexColor(col), strokeColor=None))
        d.add(String(lx + 11, 9, label, fontSize=6, fontName='Helvetica', fillColor=C.GRAY))
        lx += 50

    return d


# ─────────────────────────────────────────────────────────
# MAIN FUNCTION — drop-in replacement
# ─────────────────────────────────────────────────────────
def generate_pdf_report(product_name, df, metrics, mode,
                        ad_account_id=None, selected_campaign_ids=None,
                        date_preset=None, start_date=None, end_date=None,
                        # These must be importable from the main app:
                        BENCHMARKS=None, calculate_metrics=None,
                        calculate_daily_metrics=None,
                        get_status_emoji=None, get_status_label=None,
                        get_recommendations=None,
                        fetch_all_child_data=None):
    """Generate a professional PDF report with NO Kaleido/Chrome dependency."""
    import pandas as pd

    try:
        buffer = BytesIO()
        doc = SimpleDocTemplate(
            buffer, pagesize=landscape(letter),
            topMargin=0.45 * inch, bottomMargin=0.45 * inch,
            leftMargin=0.5 * inch, rightMargin=0.5 * inch
        )
        styles = get_styles()
        story = []

        page_w = landscape(letter)[0] - 1.0 * inch  # usable width
        totals = metrics.get('totals', {})

        # ═══════════════════════════════════════════
        #  PAGE 1 — COVER / EXECUTIVE SUMMARY
        # ═══════════════════════════════════════════
        mode_label = {'Campaign Mode': 'Campaign', 'Ad Set Mode': 'Ad Set', 'Ad Mode': 'Ad'}.get(mode, 'Campaign')

        story.append(Spacer(1, 0.3 * inch))
        story.append(Paragraph("Meta Ads Analytics Report", styles['ReportTitle']))
        story.append(Paragraph(
            f"{mode_label} Analysis  &bull;  {product_name}  &bull;  "
            f"Generated {datetime.now().strftime('%B %d, %Y')}",
            styles['ReportSubtitle']))

        story.append(HRFlowable(width="100%", thickness=1, color=C.PRIMARY, spaceAfter=16))

        # Top-line KPIs
        num_days = len(df['date'].unique()) if 'date' in df.columns else 0
        kpi_items = [
            ('Total Spend', f"₹{totals.get('spend', 0):,.0f}", '#1e40af'),
            ('Revenue', f"₹{totals.get('revenue', 0):,.0f}", '#059669'),
            ('Purchases', f"{int(totals.get('purchases', 0)):,}", '#7c3aed'),
            ('ROAS', f"{metrics.get('ROAS', 0):.2f}x", '#d97706'),
            ('CPA', f"₹{metrics.get('CPA', 0):,.0f}", '#dc2626'),
            ('Days', str(num_days), '#6b7280'),
        ]
        story.append(make_kpi_row(kpi_items, styles))
        story.append(Spacer(1, 0.2 * inch))

        # Executive summary table
        story.append(Paragraph("Executive Summary", styles['SectionHead']))

        exec_data = [
            ['Metric', 'Value', 'Metric', 'Value'],
            ['Total Spend', f"₹{totals.get('spend', 0):,.0f}", 'Total Revenue', f"₹{totals.get('revenue', 0):,.0f}"],
            ['Purchases', f"{int(totals.get('purchases', 0))}", 'ROAS', f"{metrics.get('ROAS', 0):.2f}x"],
            ['ACoS', f"{metrics.get('ACoS', 0):.1f}%", 'AOV', f"₹{metrics.get('AOV', 0):,.0f}"],
            ['MER', f"{metrics.get('MER', 0):.2f}x", 'CPM', f"₹{metrics.get('CPM', 0):,.0f}"],
            ['CPA', f"₹{metrics.get('CPA', 0):,.0f}", 'Overall CVR', f"{metrics.get('Overall_CVR', 0):.2f}%"],
            ['CTR', f"{metrics.get('CTR', 0):.2f}%", 'Hook Rate', f"{metrics.get('Hook_Rate', 0):.1f}%"],
            ['Impressions', f"{int(totals.get('impressions', 0)):,}", 'Reach', f"{int(totals.get('reach', 0)):,}"],
        ]

        cw = page_w / 4
        exec_table = Table(exec_data, colWidths=[cw * 1.1, cw * 0.9, cw * 1.1, cw * 0.9])
        exec_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 10),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('BACKGROUND', (0, 1), (-1, -1), C.PRIMARY_BG),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.PRIMARY_BG, C.WHITE]),
            ('GRID', (0, 0), (-1, -1), 0.5, C.BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 7),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 7),
            ('LEFTPADDING', (0, 0), (-1, -1), 8),
            ('ALIGN', (1, 1), (1, -1), 'RIGHT'),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (2, 1), (2, -1), 'Helvetica-Bold'),
        ]))
        story.append(exec_table)
        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 2 — FULL PERFORMANCE vs BENCHMARKS
        # ═══════════════════════════════════════════
        story.append(Paragraph("Performance vs Benchmarks", styles['SectionHead']))

        all_metric_names = [
            'CTR', 'Outbound_CTR', 'Hook_Rate', 'ThruPlay_Rate',
            'CPM', 'Frequency', 'CPC',
            'LP_View_Rate', 'View_Content_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR',
            'CPA', 'Cost_per_ATC', 'Cost_per_Checkout',
            'ROAS', 'ACoS', 'AOV', 'MER'
        ]

        # Category headers
        category_map = {
            'CTR': 'CREATIVE PERFORMANCE',
            'CPM': 'REACH & DISTRIBUTION',
            'LP_View_Rate': 'FUNNEL CONVERSION',
            'CPA': 'COST METRICS',
            'ROAS': 'REVENUE & EFFICIENCY',
        }

        bench_header = ['Category', 'Metric', 'Value', 'Ideal', 'Min', 'Gap', 'Rating']
        bench_rows = [bench_header]

        current_cat = ''
        for mn in all_metric_names:
            if mn not in metrics or BENCHMARKS is None or mn not in BENCHMARKS:
                continue
            cat = category_map.get(mn, '')
            if cat:
                current_cat = cat

            actual_val = metrics[mn]
            bench = BENCHMARKS[mn]
            gap = actual_val - bench['ideal']
            rating = get_status_label(mn, actual_val) if get_status_label else 'N/A'
            emoji = get_status_emoji(mn, actual_val) if get_status_emoji else ''

            bench_rows.append([
                current_cat if cat else '',
                mn.replace('_', ' '),
                f"{actual_val:.2f}{bench['unit']}",
                f"{bench['ideal']}{bench['unit']}",
                f"{bench['min']}{bench['unit']}",
                f"{gap:+.2f}{bench['unit']}",
                f"{emoji} {rating}",
            ])
            if cat:
                current_cat = ''  # only show once

        cws = [1.5 * inch, 1.3 * inch, 1.0 * inch, 0.9 * inch, 0.9 * inch, 0.9 * inch, 1.0 * inch]
        bench_table = Table(bench_rows, colWidths=cws)

        bench_style = [
            ('BACKGROUND', (0, 0), (-1, 0), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7.5),
            ('GRID', (0, 0), (-1, -1), 0.4, C.BORDER),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
            ('LEFTPADDING', (0, 0), (-1, -1), 4),
            ('ALIGN', (2, 1), (-2, -1), 'CENTER'),
            ('FONTNAME', (0, 1), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 1), (0, -1), 7),
            ('TEXTCOLOR', (0, 1), (0, -1), C.PRIMARY),
        ]

        # Color-code rating column
        for ri in range(1, len(bench_rows)):
            rating_text = bench_rows[ri][-1]
            if 'Excellent' in rating_text or 'Good' in rating_text:
                bench_style.append(('BACKGROUND', (-1, ri), (-1, ri), C.SUCCESS_BG))
            elif 'Acceptable' in rating_text:
                bench_style.append(('BACKGROUND', (-1, ri), (-1, ri), C.WARNING_BG))
            elif 'Weak' in rating_text:
                bench_style.append(('BACKGROUND', (-1, ri), (-1, ri), C.DANGER_BG))
            # Alternate row bg
            if ri % 2 == 0:
                bench_style.append(('BACKGROUND', (0, ri), (-2, ri), C.LIGHT_GRAY))

        bench_table.setStyle(TableStyle(bench_style))
        story.append(bench_table)
        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 3 — CONVERSION FUNNEL (pure drawing)
        # ═══════════════════════════════════════════
        story.append(Paragraph("Conversion Funnel", styles['SectionHead']))
        funnel_d = make_funnel_drawing(totals, width=680, height=300)
        story.append(funnel_d)

        # Funnel drop-off table
        story.append(Spacer(1, 0.15 * inch))
        story.append(Paragraph("Stage-to-Stage Drop-off", styles['SubSection']))

        stages_vals = [
            ('Impressions', totals.get('impressions', 0)),
            ('Clicks', totals.get('clicks', 0)),
            ('Outbound Clicks', totals.get('outbound_clicks', 0)),
            ('LP Views', totals.get('lp_views', 0)),
            ('View Content', totals.get('view_content', 0)),
            ('Add to Cart', totals.get('adds_to_cart', 0)),
            ('Checkouts', totals.get('checkouts', 0)),
            ('Purchases', totals.get('purchases', 0)),
        ]
        drop_data = [['From', 'To', 'From Count', 'To Count', 'Conversion %', 'Drop-off %']]
        for i in range(len(stages_vals) - 1):
            f_name, f_val = stages_vals[i]
            t_name, t_val = stages_vals[i + 1]
            conv_pct = (t_val / f_val * 100) if f_val > 0 else 0
            drop_pct = 100 - conv_pct
            drop_data.append([
                f_name, t_name,
                f"{f_val:,.0f}", f"{t_val:,.0f}",
                f"{conv_pct:.1f}%", f"{drop_pct:.1f}%"
            ])

        drop_table = Table(drop_data, colWidths=[1.3*inch, 1.3*inch, 1.0*inch, 1.0*inch, 1.0*inch, 1.0*inch])
        drop_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C.PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 0.4, C.BORDER),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.PURPLE_BG]),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ]))
        story.append(drop_table)
        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 4 — DAILY TREND CHARTS (pure ReportLab)
        # ═══════════════════════════════════════════
        story.append(Paragraph("Daily Performance Trends", styles['SectionHead']))

        if calculate_daily_metrics is not None:
            daily_m = calculate_daily_metrics(df)
        else:
            daily_m = df

        # Trend 1: Funnel volumes
        trend1 = make_daily_trend_drawing(
            df, ['clicks', 'lp_views', 'adds_to_cart', 'checkouts', 'purchases'],
            "Daily Funnel Volume", width=680, height=200
        )
        story.append(trend1)
        story.append(Spacer(1, 0.15 * inch))

        # Trend 2: Key rates
        trend2 = make_daily_trend_drawing(
            daily_m, ['CTR', 'Hook_Rate', 'ATC_Rate', 'Overall_CVR'],
            "Daily Rates (%)", width=680, height=200
        )
        story.append(trend2)
        story.append(PageBreak())

        # Trend 3: Cost & revenue
        trend3 = make_daily_trend_drawing(
            daily_m, ['ROAS', 'CPA', 'CPM'],
            "ROAS / CPA / CPM Trend", width=680, height=200
        )
        story.append(trend3)
        story.append(Spacer(1, 0.15 * inch))

        trend4 = make_daily_trend_drawing(
            df, ['spend', 'revenue'],
            "Daily Spend vs Revenue (₹)", width=680, height=200
        )
        story.append(trend4)
        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 5 — DAY-WISE TABLE
        # ═══════════════════════════════════════════
        story.append(Paragraph("Day-wise Performance Breakdown", styles['SectionHead']))

        display_cols = [
            'date', 'CTR', 'Outbound_CTR', 'Hook_Rate', 'ThruPlay_Rate',
            'CPM', 'CPC',
            'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR',
            'CPA', 'ROAS', 'ACoS', 'AOV'
        ]
        headers = ['Date', 'CTR%', 'OutCTR%', 'Hook%', 'Thru%', 'CPM', 'CPC',
                    'LP%', 'ATC%', 'Chk%', 'Pur%', 'CVR%', 'CPA', 'ROAS', 'ACoS%', 'AOV']

        daily_rows = [headers]
        for _, row in daily_m.iterrows():
            r = []
            for col in display_cols:
                if col == 'date':
                    try:
                        r.append(row[col].strftime('%m/%d'))
                    except Exception:
                        r.append(str(row.get(col, ''))[:5])
                elif col in ('CPM', 'CPC', 'CPA', 'AOV'):
                    r.append(f"{float(row.get(col, 0)):.0f}")
                elif col == 'ROAS':
                    r.append(f"{float(row.get(col, 0)):.2f}")
                else:
                    r.append(f"{float(row.get(col, 0)):.1f}")
            daily_rows.append(r)

        # Limit to 45 rows per page chunk for readability
        cw_day = 0.58 * inch
        day_table = Table(daily_rows[:46], colWidths=[0.5 * inch] + [cw_day] * 15)
        day_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C.PRIMARY),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6.5),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.LIGHT_GRAY]),
            ('GRID', (0, 0), (-1, -1), 0.3, C.BORDER),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(day_table)
        if len(daily_rows) > 46:
            story.append(Paragraph(
                f"Showing first 45 of {len(daily_rows) - 1} days. Full data available in raw export.",
                styles['SmallGray']))
        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 5b — METRIC vs BENCHMARK CHARTS
        # ═══════════════════════════════════════════
        story.append(Paragraph("Performance vs Benchmarks — Individual Metrics", styles['SectionHead']))

        chart_metrics = ['CTR', 'Hook_Rate', 'ATC_Rate', 'Checkout_Rate', 'Overall_CVR', 'ROAS', 'CPM', 'CPC']
        for cm in chart_metrics:
            if BENCHMARKS and cm in BENCHMARKS:
                bench = BENCHMARKS[cm]
                chart_d = make_daily_trend_with_benchmark(
                    daily_m, cm, bench['ideal'], bench['min'],
                    f"{cm.replace('_', ' ')} — Actual vs Ideal ({bench['ideal']}{bench['unit']}) / Min ({bench['min']}{bench['unit']})",
                    width=680, height=180
                )
                story.append(chart_d)
                story.append(Spacer(1, 0.08 * inch))

        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 6 — RAW DATA
        # ═══════════════════════════════════════════
        story.append(Paragraph("Raw Data Export", styles['SectionHead']))

        raw_cols = ['date', 'product', 'impressions', 'clicks', 'outbound_clicks', 'spend', 'cpm',
                    'video_3s_views', 'video_thruplay', 'lp_views', 'view_content',
                    'adds_to_cart', 'checkouts', 'purchases', 'revenue']
        raw_headers = ['Date', 'Entity', 'Impr', 'Clk', 'OutClk', 'Spend', 'CPM',
                       '3sV', 'Thru', 'LP', 'VC', 'ATC', 'Chk', 'Pur', 'Rev']

        available_cols = [c for c in raw_cols if c in df.columns]
        raw_rows = [raw_headers[:len(available_cols)]]

        for _, row in df.head(60).iterrows():
            r = []
            for col in available_cols:
                if col == 'date':
                    try:
                        r.append(row[col].strftime('%m/%d'))
                    except Exception:
                        r.append(str(row.get(col, ''))[:5])
                elif col == 'product':
                    name = str(row.get(col, ''))
                    r.append(name[:18] + '..' if len(name) > 18 else name)
                elif col in ('spend', 'revenue'):
                    r.append(f"{float(row.get(col, 0)):,.0f}")
                else:
                    r.append(f"{int(row.get(col, 0)):,}")
            raw_rows.append(r)

        n_cols = len(available_cols)
        raw_cw = page_w / n_cols
        raw_table = Table(raw_rows, colWidths=[raw_cw] * n_cols)
        raw_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), C.PURPLE),
            ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 7),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 6),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.PURPLE_BG]),
            ('GRID', (0, 0), (-1, -1), 0.3, C.BORDER),
            ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
            ('TOPPADDING', (0, 0), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
        ]))
        story.append(raw_table)
        story.append(Paragraph(f"Total rows in dataset: {len(df)}", styles['SmallGray']))
        story.append(PageBreak())

        # ═══════════════════════════════════════════
        #  PAGE 7 — CHILD ENTITIES (Campaign Mode)
        # ═══════════════════════════════════════════
        if mode == 'Campaign Mode' and ad_account_id and selected_campaign_ids and fetch_all_child_data:
            try:
                adset_data, ad_data = fetch_all_child_data(
                    ad_account_id, selected_campaign_ids,
                    date_preset, start_date, end_date
                )

                if adset_data is not None and len(adset_data) > 0 and calculate_metrics:
                    story.append(Paragraph("All Ad Sets Performance Summary", styles['SectionHead']))
                    unique_adsets = adset_data['product'].unique()

                    # Count active vs paused
                    has_status = 'entity_status' in adset_data.columns
                    if has_status:
                        status_counts = adset_data.groupby('product')['entity_status'].first()
                        n_active = (status_counts == 'ACTIVE').sum()
                        n_paused = (status_counts == 'PAUSED').sum()
                        n_other = len(status_counts) - n_active - n_paused
                        status_note = f"{len(unique_adsets)} ad set(s) with data"
                        if n_active > 0:
                            status_note += f" — {n_active} active"
                        if n_paused > 0:
                            status_note += f", {n_paused} paused"
                        if n_other > 0:
                            status_note += f", {n_other} other"
                    else:
                        status_note = f"{len(unique_adsets)} ad set(s) with data"

                    story.append(Paragraph(status_note, styles['SmallGray']))
                    story.append(Spacer(1, 0.1 * inch))

                    # Summary table for all ad sets — with Status column
                    adset_summary = [['Status', 'Ad Set', 'Spend', 'Revenue', 'ROAS', 'ACoS', 'AOV', 'CPA', 'CPM', 'CTR%', 'Hook%', 'CVR%', 'Cost/ATC', 'Rating']]
                    for aname in unique_adsets[:15]:
                        adf = adset_data[adset_data['product'] == aname]
                        am = calculate_metrics(adf)
                        roas_val = am.get('ROAS', 0)
                        rating = 'Strong' if roas_val >= 3 else 'OK' if roas_val >= 2 else 'Weak'

                        # Get status for this entity
                        if has_status:
                            entity_st = adf['entity_status'].iloc[0] if len(adf) > 0 else 'UNKNOWN'
                        else:
                            entity_st = 'UNKNOWN'
                        status_label = 'ACTIVE' if entity_st == 'ACTIVE' else 'PAUSED' if entity_st == 'PAUSED' else entity_st

                        adset_summary.append([
                            status_label,
                            str(aname)[:20],
                            f"₹{am['totals']['spend']:,.0f}",
                            f"₹{am['totals']['revenue']:,.0f}",
                            f"{roas_val:.2f}x",
                            f"{am.get('ACoS', 0):.1f}%",
                            f"₹{am.get('AOV', 0):,.0f}",
                            f"₹{am.get('CPA', 0):,.0f}",
                            f"₹{am.get('CPM', 0):,.0f}",
                            f"{am.get('CTR', 0):.2f}",
                            f"{am.get('Hook_Rate', 0):.1f}",
                            f"{am.get('Overall_CVR', 0):.2f}",
                            f"₹{am.get('Cost_per_ATC', 0):,.0f}",
                            rating,
                        ])

                    as_table = Table(adset_summary, colWidths=[
                        0.55*inch, 1.3*inch, 0.6*inch, 0.6*inch, 0.5*inch, 0.5*inch, 0.5*inch,
                        0.5*inch, 0.5*inch, 0.45*inch, 0.45*inch, 0.45*inch, 0.55*inch, 0.5*inch
                    ])
                    as_style = [
                        ('BACKGROUND', (0, 0), (-1, 0), C.PURPLE),
                        ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 7),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('GRID', (0, 0), (-1, -1), 0.4, C.BORDER),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.PURPLE_BG]),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]
                    # Color-code status and rating columns
                    for ri in range(1, len(adset_summary)):
                        # Status column color
                        st_val = adset_summary[ri][0]
                        if st_val == 'ACTIVE':
                            as_style.append(('BACKGROUND', (0, ri), (0, ri), C.SUCCESS_BG))
                            as_style.append(('TEXTCOLOR', (0, ri), (0, ri), C.SUCCESS))
                        elif st_val == 'PAUSED':
                            as_style.append(('BACKGROUND', (0, ri), (0, ri), C.WARNING_BG))
                            as_style.append(('TEXTCOLOR', (0, ri), (0, ri), C.WARNING))
                        # Rating column color
                        r = adset_summary[ri][-1]
                        if r == 'Strong':
                            as_style.append(('BACKGROUND', (-1, ri), (-1, ri), C.SUCCESS_BG))
                        elif r == 'OK':
                            as_style.append(('BACKGROUND', (-1, ri), (-1, ri), C.WARNING_BG))
                        else:
                            as_style.append(('BACKGROUND', (-1, ri), (-1, ri), C.DANGER_BG))

                    as_table.setStyle(TableStyle(as_style))
                    story.append(as_table)
                    story.append(Spacer(1, 0.15 * inch))

                    # Ad Set Raw Data table
                    story.append(Paragraph("Raw Data — All Ad Sets", styles['SubSection']))
                    child_raw_cols = ['date', 'product', 'impressions', 'clicks', 'outbound_clicks', 'spend', 'cpm',
                                     'video_3s_views', 'video_thruplay', 'lp_views', 'view_content',
                                     'adds_to_cart', 'checkouts', 'purchases', 'revenue']
                    child_raw_headers = ['Date', 'Ad Set', 'Impr', 'Clk', 'OutClk', 'Spend', 'CPM',
                                         '3sV', 'Thru', 'LP', 'VC', 'ATC', 'Chk', 'Pur', 'Rev']
                    avail_child_cols = [c for c in child_raw_cols if c in adset_data.columns]
                    adset_raw_rows = [child_raw_headers[:len(avail_child_cols)]]
                    for _, row in adset_data.iterrows():
                        r = []
                        for col in avail_child_cols:
                            if col == 'date':
                                try: r.append(row[col].strftime('%m/%d'))
                                except: r.append(str(row.get(col, ''))[:5])
                            elif col == 'product':
                                name = str(row.get(col, ''))
                                r.append(name[:15] + '..' if len(name) > 15 else name)
                            elif col in ('spend', 'revenue'):
                                r.append(f"{float(row.get(col, 0)):,.0f}")
                            elif col == 'cpm':
                                r.append(f"{float(row.get(col, 0)):.0f}")
                            else:
                                r.append(f"{int(row.get(col, 0)):,}")
                        adset_raw_rows.append(r)

                    n_c = len(avail_child_cols)
                    child_cw = page_w / n_c
                    adset_raw_tbl = Table(adset_raw_rows, colWidths=[child_cw] * n_c)
                    adset_raw_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), C.PURPLE),
                        ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 6),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 5.5),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, colors.HexColor('#f5f3ff')]),
                        ('GRID', (0, 0), (-1, -1), 0.3, C.BORDER),
                        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ]))
                    story.append(adset_raw_tbl)
                    story.append(Paragraph(f"Total rows: {len(adset_data)}", styles['SmallGray']))
                    story.append(PageBreak())

                # Ads summary
                if ad_data is not None and len(ad_data) > 0 and calculate_metrics:
                    story.append(Paragraph("All Ads Performance Summary", styles['SectionHead']))
                    unique_ads = ad_data['product'].unique()

                    # Count active vs paused
                    ad_has_status = 'entity_status' in ad_data.columns
                    if ad_has_status:
                        ad_status_counts = ad_data.groupby('product')['entity_status'].first()
                        ad_n_active = (ad_status_counts == 'ACTIVE').sum()
                        ad_n_paused = (ad_status_counts == 'PAUSED').sum()
                        ad_status_note = f"{len(unique_ads)} ad(s) with data"
                        if ad_n_active > 0:
                            ad_status_note += f" — {ad_n_active} active"
                        if ad_n_paused > 0:
                            ad_status_note += f", {ad_n_paused} paused"
                    else:
                        ad_status_note = f"{len(unique_ads)} ad(s) with data"

                    story.append(Paragraph(ad_status_note, styles['SmallGray']))
                    story.append(Spacer(1, 0.1 * inch))

                    ad_summary = [['Status', 'Ad Name', 'Spend', 'Revenue', 'ROAS', 'ACoS', 'AOV', 'CPA', 'CTR%', 'Hook%', 'CVR%', 'Cost/ATC', 'Rating']]
                    for adname in unique_ads[:20]:
                        addf = ad_data[ad_data['product'] == adname]
                        adm = calculate_metrics(addf)
                        roas_val = adm.get('ROAS', 0)
                        rating = 'Strong' if roas_val >= 3 else 'OK' if roas_val >= 2 else 'Weak'

                        # Get status for this ad
                        if ad_has_status:
                            ad_st = addf['entity_status'].iloc[0] if len(addf) > 0 else 'UNKNOWN'
                        else:
                            ad_st = 'UNKNOWN'
                        ad_status_label = 'ACTIVE' if ad_st == 'ACTIVE' else 'PAUSED' if ad_st == 'PAUSED' else ad_st

                        ad_summary.append([
                            ad_status_label,
                            str(adname)[:20],
                            f"₹{adm['totals']['spend']:,.0f}",
                            f"₹{adm['totals']['revenue']:,.0f}",
                            f"{roas_val:.2f}x",
                            f"{adm.get('ACoS', 0):.1f}%",
                            f"₹{adm.get('AOV', 0):,.0f}",
                            f"₹{adm.get('CPA', 0):,.0f}",
                            f"{adm.get('CTR', 0):.2f}",
                            f"{adm.get('Hook_Rate', 0):.1f}",
                            f"{adm.get('Overall_CVR', 0):.2f}",
                            f"₹{adm.get('Cost_per_ATC', 0):,.0f}",
                            rating,
                        ])

                    ad_tbl = Table(ad_summary, colWidths=[
                        0.55*inch, 1.3*inch, 0.6*inch, 0.6*inch, 0.5*inch, 0.5*inch, 0.5*inch,
                        0.55*inch, 0.45*inch, 0.45*inch, 0.45*inch, 0.55*inch, 0.5*inch
                    ])
                    ad_s = [
                        ('BACKGROUND', (0, 0), (-1, 0), C.PINK),
                        ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 7),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 7),
                        ('GRID', (0, 0), (-1, -1), 0.4, C.BORDER),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.PINK_BG]),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('ALIGN', (1, 1), (1, -1), 'LEFT'),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                    ]
                    for ri in range(1, len(ad_summary)):
                        # Status column color
                        st_val = ad_summary[ri][0]
                        if st_val == 'ACTIVE':
                            ad_s.append(('BACKGROUND', (0, ri), (0, ri), C.SUCCESS_BG))
                            ad_s.append(('TEXTCOLOR', (0, ri), (0, ri), C.SUCCESS))
                        elif st_val == 'PAUSED':
                            ad_s.append(('BACKGROUND', (0, ri), (0, ri), C.WARNING_BG))
                            ad_s.append(('TEXTCOLOR', (0, ri), (0, ri), C.WARNING))
                        # Rating column color
                        r = ad_summary[ri][-1]
                        if r == 'Strong':
                            ad_s.append(('BACKGROUND', (-1, ri), (-1, ri), C.SUCCESS_BG))
                        elif r == 'OK':
                            ad_s.append(('BACKGROUND', (-1, ri), (-1, ri), C.WARNING_BG))
                        else:
                            ad_s.append(('BACKGROUND', (-1, ri), (-1, ri), C.DANGER_BG))
                    ad_tbl.setStyle(TableStyle(ad_s))
                    story.append(ad_tbl)
                    story.append(Spacer(1, 0.15 * inch))

                    # Ad Raw Data table
                    story.append(Paragraph("Raw Data — All Ads", styles['SubSection']))
                    ad_raw_cols = ['date', 'product', 'impressions', 'clicks', 'outbound_clicks', 'spend', 'cpm',
                                  'video_3s_views', 'video_thruplay', 'lp_views', 'view_content',
                                  'adds_to_cart', 'checkouts', 'purchases', 'revenue']
                    ad_raw_headers = ['Date', 'Ad Name', 'Impr', 'Clk', 'OutClk', 'Spend', 'CPM',
                                      '3sV', 'Thru', 'LP', 'VC', 'ATC', 'Chk', 'Pur', 'Rev']
                    avail_ad_cols = [c for c in ad_raw_cols if c in ad_data.columns]
                    ad_raw_rows = [ad_raw_headers[:len(avail_ad_cols)]]
                    for _, row in ad_data.iterrows():
                        r = []
                        for col in avail_ad_cols:
                            if col == 'date':
                                try: r.append(row[col].strftime('%m/%d'))
                                except: r.append(str(row.get(col, ''))[:5])
                            elif col == 'product':
                                name = str(row.get(col, ''))
                                r.append(name[:15] + '..' if len(name) > 15 else name)
                            elif col in ('spend', 'revenue'):
                                r.append(f"{float(row.get(col, 0)):,.0f}")
                            elif col == 'cpm':
                                r.append(f"{float(row.get(col, 0)):.0f}")
                            else:
                                r.append(f"{int(row.get(col, 0)):,}")
                        ad_raw_rows.append(r)

                    n_ac = len(avail_ad_cols)
                    ad_raw_cw = page_w / n_ac
                    ad_raw_tbl = Table(ad_raw_rows, colWidths=[ad_raw_cw] * n_ac)
                    ad_raw_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), C.PINK),
                        ('TEXTCOLOR', (0, 0), (-1, 0), C.WHITE),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 6),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 5.5),
                        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [C.WHITE, C.PINK_BG]),
                        ('GRID', (0, 0), (-1, -1), 0.3, C.BORDER),
                        ('ALIGN', (2, 0), (-1, -1), 'CENTER'),
                        ('TOPPADDING', (0, 0), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 3),
                    ]))
                    story.append(ad_raw_tbl)
                    story.append(Paragraph(f"Total rows: {len(ad_data)}", styles['SmallGray']))
                    story.append(PageBreak())

            except Exception as child_err:
                story.append(Paragraph(f"Could not load child entity data: {str(child_err)}", styles['SmallGray']))

        # ═══════════════════════════════════════════
        #  LAST PAGE — RECOMMENDATIONS
        # ═══════════════════════════════════════════
        if get_recommendations:
            recommendations = get_recommendations(metrics)
            if recommendations:
                story.append(Paragraph("Issues & Recommendations", styles['SectionHead']))

                for issue in recommendations:
                    pri = issue.get('priority', 'MEDIUM')
                    pri_color = {
                        'CRITICAL': C.DANGER,
                        'HIGH': colors.HexColor('#ea580c'),
                        'MEDIUM': C.WARNING
                    }.get(pri, C.GRAY)
                    pri_bg = {
                        'CRITICAL': C.DANGER_BG,
                        'HIGH': colors.HexColor('#fff7ed'),
                        'MEDIUM': C.WARNING_BG
                    }.get(pri, C.LIGHT_GRAY)

                    # Issue header
                    issue_data = [
                        [Paragraph(
                            f"<font color='#{pri_color.hexval()[2:]}'><b>{pri}</b></font> &mdash; "
                            f"<b>{issue['metric']}</b> &nbsp; "
                            f"Current: {issue['current']:.2f} &rarr; Target: {issue['target']:.2f}",
                            styles['ReportBody']
                        )]
                    ]
                    for rec in issue.get('recommendations', []):
                        issue_data.append([Paragraph(f"&bull; {rec}", styles['ReportBody'])])

                    issue_tbl = Table(issue_data, colWidths=[page_w])
                    issue_tbl.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (0, 0), pri_bg),
                        ('LEFTPADDING', (0, 0), (-1, -1), 10),
                        ('TOPPADDING', (0, 0), (-1, -1), 4),
                        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                        ('LINEBELOW', (0, -1), (-1, -1), 0.5, C.BORDER),
                    ]))
                    story.append(issue_tbl)
                    story.append(Spacer(1, 0.08 * inch))

        # Build
        doc.build(story, onFirstPage=_header_footer, onLaterPages=_header_footer)
        buffer.seek(0)
        return buffer.getvalue()

    except Exception as e:
        # Return None so the caller can handle the error
        import traceback
        traceback.print_exc()
        return None