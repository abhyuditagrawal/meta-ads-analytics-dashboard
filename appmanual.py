import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Tuple
from io import BytesIO
from datetime import datetime
import base64

# Page config
st.set_page_config(
    page_title="Meta Ads Analytics Dashboard",
    page_icon="📊",
    layout="wide"
)

# Benchmark standards
BENCHMARKS = {
    'CTR': {'min': 0.9, 'ideal': 1.5, 'max': 3.0, 'unit': '%'},
    'LP_View_Rate': {'min': 80, 'ideal': 90, 'max': 100, 'unit': '%'},
    'ATC_Rate': {'min': 10, 'ideal': 20, 'max': 30, 'unit': '%'},
    'Checkout_Rate': {'min': 60, 'ideal': 75, 'max': 85, 'unit': '%'},
    'Purchase_Rate': {'min': 50, 'ideal': 65, 'max': 80, 'unit': '%'},
    'Overall_CVR': {'min': 2, 'ideal': 5, 'max': 10, 'unit': '%'},
    'CPC': {'min': 5, 'ideal': 10, 'max': 15, 'unit': '₹'},
    'CPA': {'min': 100, 'ideal': 300, 'max': 500, 'unit': '₹'},
    'Frequency': {'min': 1.0, 'ideal': 1.1, 'max': 1.3, 'unit': 'x'}
}

# Column synonyms for flexible matching
COLUMN_SYNONYMS = {
    "date": ["day", "date"],
    "impressions": ["impressions"],
    "clicks": ["clicks (all)", "link clicks", "clicks"],
    "lp_views": ["landing page views", "landing page view"],
    "adds_to_cart": ["adds to cart", "add to cart"],
    "checkouts": ["checkouts initiated", "checkout"],
    "spend": ["amount spent"],
    "purchases": ["results", "website purchase"]
}

def detect_header_row(df):
    """Find the row that contains column headers"""
    for i in range(min(10, len(df))):
        row_str = df.iloc[i].astype(str).str.lower()
        if row_str.str.contains("impression").any() or row_str.str.contains("day").any():
            return i
    return 0

def normalize_columns(df):
    """Map actual column names to standard names using synonyms"""
    mapping = {}
    lower_cols = {c.lower(): c for c in df.columns}

    for key, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            for col in lower_cols:
                if syn in col:
                    mapping[key] = lower_cols[col]
                    break
            if key in mapping:
                break
    
    return mapping

def split_data_and_notes(df, date_col):
    """Separate actual data rows from notes/text rows"""
    data_rows = []
    notes = []

    for _, row in df.iterrows():
        try:
            pd.to_datetime(row[date_col])
            data_rows.append(row)
        except:
            txt = str(row[date_col]).strip()
            if txt and txt.lower() != "nan" and txt.lower() != "none":
                notes.append(txt)

    return pd.DataFrame(data_rows), notes

def clean_sheet(raw_df, sheet_name, uploaded_file):
    """Clean and parse a single Excel sheet"""
    header_row = detect_header_row(raw_df)
    df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=header_row)
    col_map = normalize_columns(df)
    
    if "date" not in col_map:
        return None, []
    
    df_data, notes = split_data_and_notes(df, col_map["date"])
    
    required = ["impressions", "clicks", "lp_views", "adds_to_cart", "checkouts", "spend", "purchases"]
    for r in required:
        if r not in col_map:
            return None, notes
    
    clean = pd.DataFrame()
    clean["date"] = pd.to_datetime(df_data[col_map["date"]], errors='coerce')
    clean["impressions"] = pd.to_numeric(df_data[col_map["impressions"]], errors="coerce").fillna(0)
    clean["clicks"] = pd.to_numeric(df_data[col_map["clicks"]], errors="coerce").fillna(0)
    clean["lp_views"] = pd.to_numeric(df_data[col_map["lp_views"]], errors="coerce").fillna(0)
    clean["adds_to_cart"] = pd.to_numeric(df_data[col_map["adds_to_cart"]], errors="coerce").fillna(0)
    clean["checkouts"] = pd.to_numeric(df_data[col_map["checkouts"]], errors="coerce").fillna(0)
    clean["purchases"] = pd.to_numeric(df_data[col_map["purchases"]], errors="coerce").fillna(0)
    clean["spend"] = pd.to_numeric(df_data[col_map["spend"]], errors="coerce").fillna(0)
    clean["product"] = sheet_name
    
    clean = clean[clean["date"].notna()]
    
    return clean, notes

def calculate_metrics(df: pd.DataFrame) -> Dict:
    """Calculate all marketing metrics"""
    totals = df.sum(numeric_only=True)
    
    def pct(a, b):
        return (a / b * 100) if b > 0 else 0
    
    metrics = {
        'CTR': pct(totals.clicks, totals.impressions),
        'LP_View_Rate': pct(totals.lp_views, totals.clicks),
        'ATC_Rate': pct(totals.adds_to_cart, totals.lp_views),
        'Checkout_Rate': pct(totals.checkouts, totals.adds_to_cart),
        'Purchase_Rate': pct(totals.purchases, totals.checkouts),
        'Overall_CVR': pct(totals.purchases, totals.clicks),
        'CPC': totals.spend / totals.clicks if totals.clicks > 0 else 0,
        'CPA': totals.spend / totals.purchases if totals.purchases > 0 else 0,
        'ROAS': (totals.purchases * 500) / totals.spend if totals.spend > 0 else 0,
        'Frequency': totals.impressions / totals.clicks if totals.clicks > 0 else 0,
        'totals': {
            'impressions': totals.impressions,
            'clicks': totals.clicks,
            'lp_views': totals.lp_views,
            'adds_to_cart': totals.adds_to_cart,
            'checkouts': totals.checkouts,
            'purchases': totals.purchases,
            'spend': totals.spend
        }
    }
    
    return metrics

def calculate_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate metrics for each day"""
    daily = df.copy()
    
    daily['CTR'] = (daily['clicks'] / daily['impressions'] * 100).fillna(0)
    daily['LP_View_Rate'] = (daily['lp_views'] / daily['clicks'] * 100).fillna(0)
    daily['ATC_Rate'] = (daily['adds_to_cart'] / daily['lp_views'] * 100).fillna(0)
    daily['Checkout_Rate'] = (daily['checkouts'] / daily['adds_to_cart'] * 100).fillna(0)
    daily['Purchase_Rate'] = (daily['purchases'] / daily['checkouts'] * 100).fillna(0)
    daily['Overall_CVR'] = (daily['purchases'] / daily['clicks'] * 100).fillna(0)
    daily['CPC'] = (daily['spend'] / daily['clicks']).fillna(0)
    daily['CPA'] = (daily['spend'] / daily['purchases']).fillna(0).replace([float('inf')], 0)
    daily['Frequency'] = (daily['impressions'] / daily['clicks']).fillna(0)
    
    return daily

def create_actual_vs_ideal_chart(df: pd.DataFrame, metric: str) -> go.Figure:
    """Create chart showing actual vs ideal performance over time"""
    daily = calculate_daily_metrics(df)
    
    bench = BENCHMARKS.get(metric)
    if not bench:
        return None
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=daily['date'],
        y=daily[metric],
        mode='lines+markers',
        name='Actual',
        line=dict(color='#3b82f6', width=3),
        marker=dict(size=8)
    ))
    
    fig.add_trace(go.Scatter(
        x=daily['date'],
        y=[bench['ideal']] * len(daily),
        mode='lines',
        name='Ideal Target',
        line=dict(color='#10b981', width=2, dash='dash')
    ))
    
    fig.add_trace(go.Scatter(
        x=daily['date'],
        y=[bench['min']] * len(daily),
        mode='lines',
        name='Minimum Acceptable',
        line=dict(color='#f59e0b', width=2, dash='dot')
    ))
    
    fig.update_layout(
        title=f"{metric.replace('_', ' ')} - Actual vs Benchmarks",
        xaxis_title="Date",
        yaxis_title=f"Value ({bench['unit']})",
        hovermode='x unified',
        showlegend=True,
        height=400
    )
    
    return fig

def create_performance_gauge(actual: float, metric: str) -> go.Figure:
    """Create a gauge chart for a metric"""
    bench = BENCHMARKS.get(metric)
    if not bench:
        return None
    
    if actual >= bench['ideal']:
        color = '#10b981'
    elif actual >= bench['min']:
        color = '#f59e0b'
    else:
        color = '#ef4444'
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=actual,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': metric.replace('_', ' ')},
        delta={'reference': bench['ideal'], 'increasing': {'color': "green"}},
        gauge={
            'axis': {'range': [None, bench['max']]},
            'bar': {'color': color},
            'steps': [
                {'range': [0, bench['min']], 'color': '#fee2e2'},
                {'range': [bench['min'], bench['ideal']], 'color': '#fef3c7'},
                {'range': [bench['ideal'], bench['max']], 'color': '#dcfce7'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': bench['ideal']
            }
        }
    ))
    
    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
    
    return fig

def get_status(metric_name: str, value: float) -> str:
    """Get status based on benchmark"""
    if metric_name not in BENCHMARKS:
        return 'neutral'
    
    bench = BENCHMARKS[metric_name]
    if value >= bench['ideal']:
        return 'excellent'
    elif value >= bench['min']:
        return 'good'
    else:
        return 'critical'

def get_status_emoji(metric_name: str, value: float) -> str:
    """Get emoji for status"""
    status = get_status(metric_name, value)
    if status == 'excellent':
        return '✅'
    elif status == 'good':
        return '⚠️'
    else:
        return '🚨'

def create_funnel_chart(metrics: Dict) -> go.Figure:
    """Create funnel visualization"""
    totals = metrics['totals']
    
    stages = [
        ('Impressions', totals['impressions']),
        ('Link Clicks', totals['clicks']),
        ('LP Views', totals['lp_views']),
        ('Add to Cart', totals['adds_to_cart']),
        ('Checkouts', totals['checkouts']),
        ('Purchases', totals['purchases'])
    ]
    
    fig = go.Figure(go.Funnel(
        y=[s[0] for s in stages],
        x=[s[1] for s in stages],
        textposition="inside",
        textinfo="value+percent initial",
        marker=dict(
            color=['#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe', '#eff6ff']
        )
    ))
    
    fig.update_layout(
        height=500,
        margin=dict(l=20, r=20, t=40, b=20),
        title="Conversion Funnel"
    )
    
    return fig

def create_comparison_chart(all_data: pd.DataFrame, selected_products: List[str], metric: str) -> go.Figure:
    """Create comparison bar chart"""
    products = []
    values = []
    colors = []
    
    for product in selected_products:
        df = all_data[all_data["product"] == product]
        metrics = calculate_metrics(df)
        products.append(product)
        values.append(metrics[metric])
        
        status = get_status(metric, metrics[metric])
        color = '#10b981' if status == 'excellent' else '#f59e0b' if status == 'good' else '#ef4444'
        colors.append(color)
    
    fig = go.Figure(data=[
        go.Bar(
            x=products,
            y=values,
            marker_color=colors,
            text=[f"{v:.2f}%" for v in values],
            textposition='outside'
        )
    ])
    
    if metric in BENCHMARKS:
        fig.add_hline(
            y=BENCHMARKS[metric]['ideal'],
            line_dash="dash",
            line_color="green",
            annotation_text=f"Target: {BENCHMARKS[metric]['ideal']}%"
        )
    
    fig.update_layout(
        title=f"{metric.replace('_', ' ')} Comparison",
        height=400,
        showlegend=False,
        yaxis_title="Percentage (%)"
    )
    
    return fig

def get_recommendations(metrics: Dict) -> List[Dict]:
    """Generate recommendations based on metrics"""
    issues = []
    
    if metrics['Checkout_Rate'] < BENCHMARKS['Checkout_Rate']['min']:
        issues.append({
            'priority': 'CRITICAL',
            'metric': 'Checkout Rate',
            'current': metrics['Checkout_Rate'],
            'target': BENCHMARKS['Checkout_Rate']['ideal'],
            'recommendations': [
                'Enable guest checkout to reduce friction',
                'Add multiple payment options (UPI, COD, Cards)',
                'Display shipping costs earlier in the funnel',
                'Simplify checkout to 1-2 steps maximum',
                'Add trust badges and security indicators',
                'Optimize mobile checkout experience'
            ]
        })
    
    if metrics['LP_View_Rate'] < BENCHMARKS['LP_View_Rate']['min']:
        issues.append({
            'priority': 'HIGH',
            'metric': 'Landing Page View Rate',
            'current': metrics['LP_View_Rate'],
            'target': BENCHMARKS['LP_View_Rate']['ideal'],
            'recommendations': [
                'Improve page load speed (compress images, use CDN)',
                'Optimize for mobile devices',
                'Check for broken links or redirects',
                'Ensure landing page matches ad promise'
            ]
        })
    
    if metrics['Purchase_Rate'] < BENCHMARKS['Purchase_Rate']['min']:
        issues.append({
            'priority': 'MEDIUM',
            'metric': 'Purchase Completion Rate',
            'current': metrics['Purchase_Rate'],
            'target': BENCHMARKS['Purchase_Rate']['ideal'],
            'recommendations': [
                'Add exit-intent popups with discount offers',
                'Implement cart abandonment email sequence',
                'Show limited stock/urgency indicators',
                'Offer free shipping threshold',
                'Add live chat support during checkout'
            ]
        })
    
    if metrics['CTR'] < BENCHMARKS['CTR']['min']:
        issues.append({
            'priority': 'MEDIUM',
            'metric': 'Click-Through Rate',
            'current': metrics['CTR'],
            'target': BENCHMARKS['CTR']['ideal'],
            'recommendations': [
                'Test different ad creatives and copy',
                'Improve ad targeting to reach more relevant audience',
                'Use more compelling calls-to-action',
                'A/B test different images and videos',
                'Ensure ad relevance matches landing page'
            ]
        })
    
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
    issues.sort(key=lambda x: priority_order[x['priority']])
    
    return issues

def generate_pdf_report(product_name: str, df: pd.DataFrame, metrics: Dict, notes: List[str], mode: str = "single") -> bytes:
    """Generate a comprehensive PDF report with ALL dashboard content"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, A4
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
        from reportlab.pdfgen import canvas
        import plotly.io as pio
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        subheading_style = ParagraphStyle(
            'CustomSubHeading',
            parent=styles['Heading3'],
            fontSize=12,
            textColor=colors.HexColor('#6b7280'),
            spaceAfter=8,
            fontName='Helvetica-Bold'
        )
        
        story.append(Paragraph("Meta Ads Analytics Report", title_style))
        story.append(Paragraph(f"Product: {product_name}", heading_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Executive Summary", heading_style))
        summary_data = [
            ['Metric', 'Value'],
            ['Total Spend', f"₹{metrics['totals']['spend']:,.0f}"],
            ['Total Purchases', f"{int(metrics['totals']['purchases'])}"],
            ['Cost Per Acquisition', f"₹{metrics['CPA']:.2f}"],
            ['Overall Conversion Rate', f"{metrics['Overall_CVR']:.2f}%"],
            ['Days Analyzed', f"{len(df)}"]
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Performance Metrics", heading_style))
        
        metrics_data = [
            ['Metric', 'Value', 'Target', 'Status'],
            ['CTR', f"{metrics['CTR']:.2f}%", f"{BENCHMARKS['CTR']['ideal']}%", get_status_emoji('CTR', metrics['CTR'])],
            ['LP View Rate', f"{metrics['LP_View_Rate']:.2f}%", f"{BENCHMARKS['LP_View_Rate']['ideal']}%", get_status_emoji('LP_View_Rate', metrics['LP_View_Rate'])],
            ['Add to Cart Rate', f"{metrics['ATC_Rate']:.2f}%", f"{BENCHMARKS['ATC_Rate']['ideal']}%", get_status_emoji('ATC_Rate', metrics['ATC_Rate'])],
            ['Checkout Rate', f"{metrics['Checkout_Rate']:.2f}%", f"{BENCHMARKS['Checkout_Rate']['ideal']}%", get_status_emoji('Checkout_Rate', metrics['Checkout_Rate'])],
            ['Purchase Rate', f"{metrics['Purchase_Rate']:.2f}%", f"{BENCHMARKS['Purchase_Rate']['ideal']}%", get_status_emoji('Purchase_Rate', metrics['Purchase_Rate'])],
        ]
        
        metrics_table = Table(metrics_data, colWidths=[2*inch, 1.5*inch, 1.5*inch, 1*inch])
        metrics_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(metrics_table)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Performance vs Benchmarks - Detailed Analysis", heading_style))
        
        comparison_data = [['Metric', 'Your Avg', 'Ideal', 'Min', 'Gap', 'Status']]
        
        for metric_name in ['CTR', 'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR', 'CPC', 'CPA', 'Frequency']:
            actual_val = metrics[metric_name]
            bench = BENCHMARKS[metric_name]
            gap = actual_val - bench['ideal']
            status = get_status_emoji(metric_name, actual_val)
            
            comparison_data.append([
                metric_name.replace('_', ' '),
                f"{actual_val:.2f}{bench['unit']}",
                f"{bench['ideal']:.2f}{bench['unit']}",
                f"{bench['min']:.2f}{bench['unit']}",
                f"{gap:+.2f}{bench['unit']}",
                status
            ])
        
        comparison_table = Table(comparison_data, colWidths=[1.5*inch, 1*inch, 1*inch, 1*inch, 1*inch, 0.8*inch])
        comparison_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3e8ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        
        story.append(comparison_table)
        story.append(PageBreak())
        
        story.append(Paragraph("Conversion Funnel Visualization", heading_style))
        
        funnel_fig = create_funnel_chart(metrics)
        img_bytes = pio.to_image(funnel_fig, format='png', width=700, height=500)
        img_buffer = BytesIO(img_bytes)
        img = Image(img_buffer, width=6*inch, height=4*inch)
        story.append(img)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Cost Breakdown", heading_style))
        
        cost_data = [
            ['Metric', 'Value', 'Benchmark'],
            ['Cost Per Click (CPC)', f"₹{metrics['CPC']:.2f}", f"₹{BENCHMARKS['CPC']['ideal']:.0f}"],
            ['Cost Per Acquisition (CPA)', f"₹{metrics['CPA']:.2f}", f"₹{BENCHMARKS['CPA']['ideal']:.0f}"],
            ['Total Ad Spend', f"₹{metrics['totals']['spend']:,.0f}", '-'],
            ['Frequency', f"{metrics['Frequency']:.2f}x", f"{BENCHMARKS['Frequency']['ideal']:.1f}x"],
        ]
        
        cost_table = Table(cost_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        cost_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#f59e0b')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fef3c7')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(cost_table)
        story.append(PageBreak())
        
        story.append(Paragraph("Daily Performance Trends", heading_style))
        
        fig_conversions = px.line(
            df, 
            x="date", 
            y=["clicks", "adds_to_cart", "purchases"],
            title="Daily Conversions Trend",
            labels={"value": "Count", "variable": "Metric", "date": "Date"}
        )
        fig_conversions.update_layout(width=700, height=400, showlegend=True)
        
        conv_img_bytes = pio.to_image(fig_conversions, format='png', width=700, height=400)
        conv_img_buffer = BytesIO(conv_img_bytes)
        conv_img = Image(conv_img_buffer, width=6*inch, height=3*inch)
        story.append(conv_img)
        story.append(Spacer(1, 0.2*inch))
        
        fig_spend = px.line(df, x="date", y="spend", title="Daily Ad Spend")
        fig_spend.update_layout(width=700, height=400)
        
        spend_img_bytes = pio.to_image(fig_spend, format='png', width=700, height=400)
        spend_img_buffer = BytesIO(spend_img_bytes)
        spend_img = Image(spend_img_buffer, width=6*inch, height=3*inch)
        story.append(spend_img)
        story.append(PageBreak())
        
        story.append(Paragraph("Daily Performance vs Benchmarks", heading_style))
        
        ctr_fig = create_actual_vs_ideal_chart(df, 'CTR')
        if ctr_fig:
            ctr_img = pio.to_image(ctr_fig, format='png', width=700, height=400)
            ctr_buffer = BytesIO(ctr_img)
            story.append(Image(ctr_buffer, width=6*inch, height=3*inch))
            story.append(Spacer(1, 0.2*inch))
        
        checkout_fig = create_actual_vs_ideal_chart(df, 'Checkout_Rate')
        if checkout_fig:
            checkout_img = pio.to_image(checkout_fig, format='png', width=700, height=400)
            checkout_buffer = BytesIO(checkout_img)
            story.append(Image(checkout_buffer, width=6*inch, height=3*inch))
            story.append(Spacer(1, 0.2*inch))
        
        atc_fig = create_actual_vs_ideal_chart(df, 'ATC_Rate')
        if atc_fig:
            atc_img = pio.to_image(atc_fig, format='png', width=700, height=400)
            atc_buffer = BytesIO(atc_img)
            story.append(Image(atc_buffer, width=6*inch, height=3*inch))
            story.append(Spacer(1, 0.2*inch))
        
        cvr_fig = create_actual_vs_ideal_chart(df, 'Overall_CVR')
        if cvr_fig:
            cvr_img = pio.to_image(cvr_fig, format='png', width=700, height=400)
            cvr_buffer = BytesIO(cvr_img)
            story.append(Image(cvr_buffer, width=6*inch, height=3*inch))
        
        story.append(PageBreak())
        
        story.append(Paragraph("Conversion Funnel Breakdown", heading_style))
        
        funnel_data = [
            ['Stage', 'Count', 'Conversion %'],
            ['Impressions', f"{int(metrics['totals']['impressions']):,}", '100%'],
            ['Link Clicks', f"{int(metrics['totals']['clicks']):,}", f"{metrics['CTR']:.2f}%"],
            ['Landing Page Views', f"{int(metrics['totals']['lp_views']):,}", f"{metrics['LP_View_Rate']:.2f}%"],
            ['Add to Cart', f"{int(metrics['totals']['adds_to_cart']):,}", f"{metrics['ATC_Rate']:.2f}%"],
            ['Checkouts', f"{int(metrics['totals']['checkouts']):,}", f"{metrics['Checkout_Rate']:.2f}%"],
            ['Purchases', f"{int(metrics['totals']['purchases']):,}", f"{metrics['Purchase_Rate']:.2f}%"],
        ]
        
        funnel_table = Table(funnel_data, colWidths=[2.5*inch, 1.5*inch, 1.5*inch])
        funnel_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#f3e8ff')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(funnel_table)
        story.append(PageBreak())
        
        recommendations = get_recommendations(metrics)
        if recommendations:
            story.append(Paragraph("Issues Detected & Recommendations", heading_style))
            
            for issue in recommendations:
                priority_color = '#ef4444' if issue['priority'] == 'CRITICAL' else '#f97316' if issue['priority'] == 'HIGH' else '#f59e0b'
                
                story.append(Paragraph(f"<font color='{priority_color}'><b>{issue['priority']}: {issue['metric']}</b></font>", subheading_style))
                story.append(Paragraph(f"Current: {issue['current']:.2f}% | Target: {issue['target']:.2f}%", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                
                for rec in issue['recommendations']:
                    story.append(Paragraph(f"• {rec}", styles['Normal']))
                
                story.append(Spacer(1, 0.2*inch))
        
        story.append(PageBreak())
        
        if notes:
            story.append(Paragraph("Analyst Notes & Observations", heading_style))
            for note in notes:
                story.append(Paragraph(f"• {note}", styles['Normal']))
            story.append(Spacer(1, 0.3*inch))
            story.append(PageBreak())
        
        story.append(Paragraph("Day-wise Performance Breakdown", heading_style))
        
        daily_metrics = calculate_daily_metrics(df)
        
        daily_data = [['Date', 'CTR%', 'LP%', 'ATC%', 'Chk%', 'Pur%', 'CVR%', 'CPC', 'CPA', 'Freq']]
        
        for _, row in daily_metrics.iterrows():
            daily_data.append([
                row['date'].strftime('%m/%d'),
                f"{row['CTR']:.1f}",
                f"{row['LP_View_Rate']:.1f}",
                f"{row['ATC_Rate']:.1f}",
                f"{row['Checkout_Rate']:.1f}",
                f"{row['Purchase_Rate']:.1f}",
                f"{row['Overall_CVR']:.1f}",
                f"{row['CPC']:.1f}",
                f"{row['CPA']:.0f}",
                f"{row['Frequency']:.2f}"
            ])
        
        daily_table = Table(daily_data, colWidths=[0.7*inch] * 10)
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        
        story.append(daily_table)
        story.append(PageBreak())
        
        story.append(Paragraph("Raw Data - Complete Daily Breakdown", heading_style))
        
        raw_data = [['Date', 'Impr', 'Clicks', 'LP Views', 'ATC', 'Chk', 'Purch', 'Spend']]
        
        for _, row in df.iterrows():
            raw_data.append([
                row['date'].strftime('%m/%d/%y'),
                f"{int(row['impressions']):,}",
                f"{int(row['clicks'])}",
                f"{int(row['lp_views'])}",
                f"{int(row['adds_to_cart'])}",
                f"{int(row['checkouts'])}",
                f"{int(row['purchases'])}",
                f"₹{row['spend']:.0f}"
            ])
        
        raw_table = Table(raw_data, colWidths=[0.8*inch, 0.8*inch, 0.7*inch, 0.8*inch, 0.7*inch, 0.7*inch, 0.7*inch, 0.9*inch])
        raw_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#059669')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 8),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#d1fae5')),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 7),
            ('TOPPADDING', (0, 1), (-1, -1), 5),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 5),
        ]))
        
        story.append(raw_table)
        
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    except ImportError:
        st.error("PDF generation requires reportlab and kaleido. Install with: pip install reportlab kaleido")
        return None
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None

def generate_comparison_pdf(selected_products: List[str], all_data: pd.DataFrame) -> bytes:
    """Generate PDF for product comparison"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        import plotly.io as pio
        
        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1f2937'),
            spaceAfter=30,
            alignment=TA_CENTER,
            fontName='Helvetica-Bold'
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#3b82f6'),
            spaceAfter=12,
            spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        
        story.append(Paragraph("Meta Ads Product Comparison Report", title_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Performance Comparison", heading_style))
        
        comparison_data = [['Metric'] + selected_products]
        
        metrics_to_show = [
            ('CTR (%)', 'CTR'),
            ('LP View Rate (%)', 'LP_View_Rate'),
            ('ATC Rate (%)', 'ATC_Rate'),
            ('Checkout Rate (%)', 'Checkout_Rate'),
            ('Purchase Rate (%)', 'Purchase_Rate'),
            ('Overall CVR (%)', 'Overall_CVR'),
            ('Total Spend (₹)', 'spend'),
            ('Total Purchases', 'purchases'),
            ('CPC (₹)', 'CPC'),
            ('CPA (₹)', 'CPA'),
        ]
        
        for label, metric_key in metrics_to_show:
            row = [label]
            for product in selected_products:
                df = all_data[all_data["product"] == product]
                metrics = calculate_metrics(df)
                
                if metric_key == 'spend':
                    value = f"₹{metrics['totals']['spend']:,.0f}"
                elif metric_key == 'purchases':
                    value = f"{int(metrics['totals']['purchases'])}"
                elif metric_key in ['CPC', 'CPA']:
                    value = f"₹{metrics[metric_key]:.2f}"
                else:
                    value = f"{metrics[metric_key]:.2f}%"
                
                row.append(value)
            
            comparison_data.append(row)
        
        col_width = 1.8*inch
        table = Table(comparison_data, colWidths=[2*inch] + [col_width] * len(selected_products))
        
        table_style = [
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 9),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]
        
        table.setStyle(TableStyle(table_style))
        story.append(table)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(PageBreak())
        story.append(Paragraph("Visual Performance Comparison", heading_style))
        
        metrics_to_chart = [
            ('CTR', 'Click-Through Rate Comparison'),
            ('Checkout_Rate', 'Checkout Rate Comparison'),
            ('Overall_CVR', 'Overall Conversion Rate Comparison')
        ]
        
        for metric, title in metrics_to_chart:
            fig = create_comparison_chart(all_data, selected_products, metric)
            fig.update_layout(title=title, width=900, height=400)
            
            img_bytes = pio.to_image(fig, format='png', width=900, height=400)
            img_buffer = BytesIO(img_bytes)
            img = Image(img_buffer, width=9*inch, height=4*inch)
            story.append(img)
            story.append(Spacer(1, 0.2*inch))
        
        story.append(PageBreak())
        
        story.append(Paragraph("Best Performers", heading_style))
        
        best_performers_data = [['Metric', 'Product', 'Value']]
        
        for metric_name, metric_label in [('Checkout_Rate', 'Checkout Rate'), ('Purchase_Rate', 'Purchase Rate'), ('Overall_CVR', 'Overall CVR')]:
            best_product = max(selected_products, 
                             key=lambda p: calculate_metrics(all_data[all_data["product"] == p])[metric_name])
            best_value = calculate_metrics(all_data[all_data["product"] == best_product])[metric_name]
            best_performers_data.append([metric_label, best_product, f"{best_value:.2f}%"])
        
        best_table = Table(best_performers_data, colWidths=[2.5*inch, 3*inch, 1.5*inch])
        best_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#dcfce7')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(best_table)
        story.append(Spacer(1, 0.3*inch))
        
        story.append(Paragraph("Needs Improvement", heading_style))
        
        worst_performers_data = [['Metric', 'Product', 'Value']]
        
        for metric_name, metric_label in [('Checkout_Rate', 'Checkout Rate'), ('Purchase_Rate', 'Purchase Rate'), ('Overall_CVR', 'Overall CVR')]:
            worst_product = min(selected_products, 
                              key=lambda p: calculate_metrics(all_data[all_data["product"] == p])[metric_name])
            worst_value = calculate_metrics(all_data[all_data["product"] == worst_product])[metric_name]
            worst_performers_data.append([metric_label, worst_product, f"{worst_value:.2f}%"])
        
        worst_table = Table(worst_performers_data, colWidths=[2.5*inch, 3*inch, 1.5*inch])
        worst_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ef4444')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, 1), (-1, -1), colors.HexColor('#fee2e2')),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('TOPPADDING', (0, 1), (-1, -1), 8),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 8),
        ]))
        
        story.append(worst_table)
        
        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()
    
    except ImportError:
        st.error("PDF generation requires reportlab and kaleido. Install with: pip install reportlab kaleido")
        return None
    except Exception as e:
        st.error(f"Error generating comparison PDF: {str(e)}")
        return None

def main():
    st.title("📊 Meta Ads Analytics Dashboard")
    st.markdown("Upload your Excel file with multiple product sheets to analyze campaign performance")
    
    uploaded_file = st.file_uploader("Upload Excel File (.xlsx)", type=['xlsx', 'xls'])
    
    if uploaded_file is not None:
        try:
            excel_file = pd.ExcelFile(uploaded_file)
            
            all_data = []
            product_notes = {}
            
            for sheet_name in excel_file.sheet_names:
                raw_df = pd.read_excel(uploaded_file, sheet_name=sheet_name, header=None)
                cleaned_df, notes = clean_sheet(raw_df, sheet_name, uploaded_file)
                
                if cleaned_df is not None and len(cleaned_df) > 0:
                    all_data.append(cleaned_df)
                    product_notes[sheet_name] = notes
            
            if not all_data:
                st.error("No valid data found in Excel file. Please check your file format.")
                st.info("Make sure your sheets have columns: Day/Date, Impressions, Link clicks, Landing page views, Adds to cart, Checkouts initiated, Amount spent, Results/Purchases")
                return
            
            data = pd.concat(all_data, ignore_index=True)
            products = sorted(data["product"].unique())
            
            st.sidebar.header("📋 Product Selection")
            mode = st.sidebar.radio("Mode", ["Single Product Analysis", "Compare Products"])
            
            if mode == "Single Product Analysis":
                selected_product = st.sidebar.selectbox("Select Product", products)
                df = data[data["product"] == selected_product]
                metrics = calculate_metrics(df)
                
                col1, col2, col3 = st.columns([2, 1, 1])
                with col1:
                    st.header(f"📦 {selected_product}")
                with col2:
                    st.metric("Days of Data", len(df))
                with col3:
                    pdf_bytes = generate_pdf_report(selected_product, df, metrics, product_notes.get(selected_product, []))
                    if pdf_bytes:
                        st.download_button(
                            label="📥 Download PDF Report",
                            data=pdf_bytes,
                            file_name=f"{selected_product}_Report_{datetime.now().strftime('%Y%m%d')}.pdf",
                            mime="application/pdf",
                            use_container_width=True
                        )
                
                st.divider()
                
                st.subheader("🎯 Performance Overview")
                
                metric_cols = st.columns(6)
                metric_names = ['CTR', 'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR']
                metric_labels = ['CTR', 'LP View Rate', 'ATC Rate', 'Checkout Rate', 'Purchase Rate', 'Overall CVR']
                
                for idx, (metric_name, label) in enumerate(zip(metric_names, metric_labels)):
                    with metric_cols[idx]:
                        value = metrics[metric_name]
                        emoji = get_status_emoji(metric_name, value)
                        ideal = BENCHMARKS[metric_name]['ideal']
                        delta_val = value - ideal
                        
                        st.metric(
                            label=f"{emoji} {label}",
                            value=f"{value:.2f}%",
                            delta=f"{delta_val:+.2f}% vs target",
                            delta_color="normal"
                        )
                
                st.divider()
                
                st.subheader("📊 Performance vs Benchmarks")
                
                comparison_data = []
                for metric_name in ['CTR', 'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR', 'CPC', 'CPA', 'Frequency']:
                    actual_val = metrics[metric_name]
                    bench = BENCHMARKS[metric_name]
                    
                    gap = actual_val - bench['ideal']
                    gap_pct = (gap / bench['ideal'] * 100) if bench['ideal'] > 0 else 0
                    
                    status = get_status_emoji(metric_name, actual_val)
                    
                    comparison_data.append({
                        'Metric': metric_name.replace('_', ' '),
                        'Your Average': f"{actual_val:.2f}{bench['unit']}",
                        'Ideal Target': f"{bench['ideal']:.2f}{bench['unit']}",
                        'Min Acceptable': f"{bench['min']:.2f}{bench['unit']}",
                        'Gap': f"{gap:+.2f}{bench['unit']}",
                        'Gap %': f"{gap_pct:+.1f}%",
                        'Status': status
                    })
                
                comparison_df = pd.DataFrame(comparison_data)
                st.dataframe(comparison_df, use_container_width=True, hide_index=True)
                
                st.divider()
                
                st.subheader("🎯 Performance Gauges")
                
                gauge_cols = st.columns(3)
                key_metrics_for_gauge = ['CTR', 'Checkout_Rate', 'Overall_CVR']
                
                for idx, metric_name in enumerate(key_metrics_for_gauge):
                    with gauge_cols[idx]:
                        gauge_fig = create_performance_gauge(metrics[metric_name], metric_name)
                        if gauge_fig:
                            st.plotly_chart(gauge_fig, use_container_width=True)
                
                st.divider()
                
                st.subheader("📈 Daily Performance vs Benchmarks")
                
                chart_col1, chart_col2 = st.columns(2)
                
                with chart_col1:
                    ctr_chart = create_actual_vs_ideal_chart(df, 'CTR')
                    if ctr_chart:
                        st.plotly_chart(ctr_chart, use_container_width=True)
                    
                    atc_chart = create_actual_vs_ideal_chart(df, 'ATC_Rate')
                    if atc_chart:
                        st.plotly_chart(atc_chart, use_container_width=True)
                
                with chart_col2:
                    checkout_chart = create_actual_vs_ideal_chart(df, 'Checkout_Rate')
                    if checkout_chart:
                        st.plotly_chart(checkout_chart, use_container_width=True)
                    
                    cvr_chart = create_actual_vs_ideal_chart(df, 'Overall_CVR')
                    if cvr_chart:
                        st.plotly_chart(cvr_chart, use_container_width=True)
                
                st.divider()
                
                st.subheader("📅 Day-wise Performance Breakdown")
                
                daily_metrics = calculate_daily_metrics(df)
                display_cols = ['date', 'CTR', 'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR', 'CPC', 'CPA', 'Frequency']
                daily_display = daily_metrics[display_cols].copy()
                daily_display['date'] = pd.to_datetime(daily_display['date']).dt.strftime('%Y-%m-%d')
                
                for col in display_cols[1:]:
                    daily_display[col] = daily_display[col].round(2)
                
                st.dataframe(daily_display, use_container_width=True, hide_index=True)
                st.info("💡 **Color Guide:** ✅ Excellent (above ideal) | ⚠️ Average (above minimum) | 🚨 Poor (below minimum)")
                
                st.divider()
                
                col1, col2 = st.columns(2)
                
                with col1:
                    st.subheader("📊 Conversion Funnel")
                    fig_funnel = create_funnel_chart(metrics)
                    st.plotly_chart(fig_funnel, use_container_width=True)
                
                with col2:
                    st.subheader("💰 Cost Metrics")
                    
                    st.markdown(f"""
                    <div style='padding: 15px; background-color: #eff6ff; border-left: 4px solid #3b82f6; margin-bottom: 15px;'>
                        <div style='color: #1f2937; font-size: 14px;'>Total Spent</div>
                        <div style='font-size: 28px; font-weight: bold; color: #000000;'>₹{metrics['totals']['spend']:,.0f}</div>
                    </div>
                    
                    <div style='padding: 15px; background-color: #f3e8ff; border-left: 4px solid #a855f7; margin-bottom: 15px;'>
                        <div style='color: #1f2937; font-size: 14px;'>Cost Per Click (CPC)</div>
                        <div style='font-size: 28px; font-weight: bold; color: #000000;'>₹{metrics['CPC']:.2f}</div>
                        <div style='color: #1f2937; font-size: 12px;'>Benchmark: ₹5-15</div>
                    </div>
                    
                    <div style='padding: 15px; background-color: #dcfce7; border-left: 4px solid #22c55e; margin-bottom: 15px;'>
                        <div style='color: #1f2937; font-size: 14px;'>Cost Per Acquisition (CPA)</div>
                        <div style='font-size: 28px; font-weight: bold; color: #000000;'>₹{metrics['CPA']:.2f}</div>
                        <div style='color: #1f2937; font-size: 12px;'>Benchmark: ₹100-500</div>
                    </div>
                    
                    <div style='padding: 15px; background-color: #fef3c7; border-left: 4px solid #f59e0b; margin-bottom: 15px;'>
                        <div style='color: #1f2937; font-size: 14px;'>Total Purchases</div>
                        <div style='font-size: 28px; font-weight: bold; color: #000000;'>{int(metrics['totals']['purchases'])}</div>
                    </div>
                    """, unsafe_allow_html=True)
                
                st.divider()
                
                st.subheader("📈 Daily Trends")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    fig_conversions = px.line(
                        df, 
                        x="date", 
                        y=["clicks", "adds_to_cart", "purchases"],
                        title="Daily Conversions",
                        labels={"value": "Count", "variable": "Metric"}
                    )
                    st.plotly_chart(fig_conversions, use_container_width=True)
                
                with col2:
                    fig_spend = px.line(
                        df,
                        x="date",
                        y="spend",
                        title="Daily Spend"
                    )
                    st.plotly_chart(fig_spend, use_container_width=True)
                
                st.divider()
                
                recommendations = get_recommendations(metrics)
                
                if recommendations:
                    st.subheader("🚨 Issues Detected & Recommendations")
                    
                    for issue in recommendations:
                        priority_colors = {
                            'CRITICAL': '#ef4444',
                            'HIGH': '#f97316',
                            'MEDIUM': '#f59e0b'
                        }
                        
                        with st.expander(f"{issue['priority']}: {issue['metric']} - Current: {issue['current']:.1f}% → Target: {issue['target']}%", expanded=True):
                            st.markdown(f"**Current Performance:** {issue['current']:.2f}%")
                            st.markdown(f"**Target Performance:** {issue['target']:.2f}%")
                            st.markdown("**Action Items:**")
                            
                            for rec in issue['recommendations']:
                                st.markdown(f"• {rec}")
                else:
                    st.success("🎉 All metrics are performing well! Keep up the good work.")
                
                if selected_product in product_notes and product_notes[selected_product]:
                    st.divider()
                    st.subheader("📝 Analyst Notes & Observations")
                    for note in product_notes[selected_product]:
                        st.markdown(f"• {note}")
                
                with st.expander("📄 View Raw Data"):
                    st.dataframe(df, use_container_width=True)
            
            else:
                st.subheader("📊 Product Comparison")
                
                col1, col2 = st.columns([3, 1])
                
                with col1:
                    selected_products = st.sidebar.multiselect(
                        "Select Products to Compare (max 4)",
                        products,
                        default=products[:min(3, len(products))]
                    )
                
                with col2:
                    if len(selected_products) >= 2 and len(selected_products) <= 4:
                        pdf_bytes = generate_comparison_pdf(selected_products, data)
                        if pdf_bytes:
                            st.download_button(
                                label="📥 Download Comparison PDF",
                                data=pdf_bytes,
                                file_name=f"Product_Comparison_{datetime.now().strftime('%Y%m%d')}.pdf",
                                mime="application/pdf",
                                use_container_width=True
                            )
                
                if len(selected_products) < 2:
                    st.warning("Please select at least 2 products to compare")
                elif len(selected_products) > 4:
                    st.warning("Please select maximum 4 products to compare")
                else:
                    st.subheader("📋 Metrics Comparison Table")
                    
                    comparison_data = []
                    for product in selected_products:
                        df = data[data["product"] == product]
                        metrics = calculate_metrics(df)
                        comparison_data.append({
                            'Product': product,
                            'CTR (%)': f"{metrics['CTR']:.2f}",
                            'LP View (%)': f"{metrics['LP_View_Rate']:.2f}",
                            'ATC (%)': f"{metrics['ATC_Rate']:.2f}",
                            'Checkout (%)': f"{metrics['Checkout_Rate']:.2f}",
                            'Purchase (%)': f"{metrics['Purchase_Rate']:.2f}",
                            'Overall CVR (%)': f"{metrics['Overall_CVR']:.2f}",
                            'Total Spent': f"₹{metrics['totals']['spend']:,.0f}",
                            'Purchases': int(metrics['totals']['purchases']),
                            'CPA': f"₹{metrics['CPA']:.2f}"
                        })
                    
                    comparison_df = pd.DataFrame(comparison_data)
                    st.dataframe(comparison_df, use_container_width=True)
                    
                    st.divider()
                    
                    st.subheader("📊 Visual Comparison")
                    
                    chart_cols = st.columns(2)
                    
                    metrics_to_compare = ['CTR', 'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR']
                    
                    for idx, metric in enumerate(metrics_to_compare):
                        with chart_cols[idx % 2]:
                            fig = create_comparison_chart(data, selected_products, metric)
                            st.plotly_chart(fig, use_container_width=True)
                    
                    st.divider()
                    
                    st.subheader("🏆 Best & Worst Performers")
                    
                    col1, col2 = st.columns(2)
                    
                    with col1:
                        st.markdown("### ✅ Best Performers")
                        for metric in ['Checkout_Rate', 'Purchase_Rate', 'Overall_CVR']:
                            best_product = max(selected_products, 
                                             key=lambda p: calculate_metrics(data[data["product"] == p])[metric])
                            best_value = calculate_metrics(data[data["product"] == best_product])[metric]
                            st.markdown(f"**{metric.replace('_', ' ')}:** {best_product} ({best_value:.2f}%)")
                    
                    with col2:
                        st.markdown("### ⚠️ Needs Improvement")
                        for metric in ['Checkout_Rate', 'Purchase_Rate', 'Overall_CVR']:
                            worst_product = min(selected_products, 
                                              key=lambda p: calculate_metrics(data[data["product"] == p])[metric])
                            worst_value = calculate_metrics(data[data["product"] == worst_product])[metric]
                            st.markdown(f"**{metric.replace('_', ' ')}:** {worst_product} ({worst_value:.2f}%)")
        
        except Exception as e:
            st.error(f"Error reading Excel file: {str(e)}")
            st.info("Please ensure your Excel file has the correct format with columns: Day/Date, Impressions, Link clicks, Landing page views, Adds to cart, Checkouts initiated, Amount spent, Results/Purchases")
    
    else:
        st.info("👆 Upload your Excel file to get started")
        
        st.markdown("""
        ### 📋 Required Excel Format
        
        Your Excel file should have:
        - **Multiple sheets** (one per product/campaign)
        - **Columns** (flexible naming):
          - Day/Date
          - Impressions
          - Link clicks / Clicks (all)
          - Landing page views
          - Adds to cart
          - Checkouts initiated
          - Amount spent (INR)
          - Results / Website purchases
          
        ### ✨ Features
        
        - 📊 **Single Product Analysis**: Deep dive into one product's performance
        - 🔄 **Compare Products**: Side-by-side comparison of up to 4 products
        - 📈 **Funnel Visualization**: See where users drop off
        - 🎯 **Benchmark Comparison**: Compare against industry standards
        - 💡 **Smart Recommendations**: Get actionable improvement suggestions
        - 🚨 **Issue Detection**: Automatically identify performance problems
        - 📝 **Notes Extraction**: Captures analyst notes from your sheets
        """)

if __name__ == "__main__":
    main()