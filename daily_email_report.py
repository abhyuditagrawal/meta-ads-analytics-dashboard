"""
Daily Meta Ads Email Report
===========================
Runs every night at midnight via GitHub Actions.
Fetches yesterday's data for all active campaigns, generates a PDF,
and emails it using SMTP.

Uses plain HTTP requests to Meta Graph API — no SDK dependencies.
"""

import os
import sys
import json
import smtplib
import logging
import requests
import pandas as pd
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication


# ═══════════════════════════════════════════════════════════
# 1. CONFIG — read from environment variables
# ═══════════════════════════════════════════════════════════
META_ACCESS_TOKEN = os.environ.get('META_ACCESS_TOKEN', '')
META_AD_ACCOUNT_ID = 'act_24472841068985090'  # your hardcoded account
META_API_VERSION = 'v21.0'

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SMTP_USER = os.environ.get('SMTP_USER', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
EMAIL_TO = os.environ.get('EMAIL_TO', '')
EMAIL_FROM = os.environ.get('EMAIL_FROM', '') or SMTP_USER

DEFAULT_AOV = 600

# Same benchmarks as the dashboard
BENCHMARKS = {
    'CTR': {'weak': 1.0, 'acceptable': 1.5, 'good': 3.0, 'excellent': 3.0, 'min': 1.0, 'ideal': 2.0, 'max': 3.0, 'unit': '%', 'higher_better': True},
    'Outbound_CTR': {'weak': 0.5, 'acceptable': 0.8, 'good': 1.5, 'excellent': 2.0, 'min': 0.5, 'ideal': 1.0, 'max': 2.0, 'unit': '%', 'higher_better': True},
    'Hook_Rate': {'weak': 20, 'acceptable': 30, 'good': 45, 'excellent': 50, 'min': 20, 'ideal': 35, 'max': 50, 'unit': '%', 'higher_better': True},
    'ThruPlay_Rate': {'weak': 8, 'acceptable': 15, 'good': 25, 'excellent': 25, 'min': 8, 'ideal': 15, 'max': 25, 'unit': '%', 'higher_better': True},
    'CPM': {'weak': 300, 'acceptable': 200, 'good': 100, 'excellent': 100, 'min': 200, 'ideal': 150, 'max': 100, 'unit': '₹', 'higher_better': False},
    'Frequency': {'weak': 6, 'acceptable': 3.5, 'good': 1.8, 'excellent': 1.8, 'min': 3.5, 'ideal': 2.5, 'max': 1.8, 'unit': 'x', 'higher_better': False},
    'CPC': {'weak': 40, 'acceptable': 20, 'good': 10, 'excellent': 10, 'min': 20, 'ideal': 12, 'max': 10, 'unit': '₹', 'higher_better': False},
    'LP_View_Rate': {'weak': 50, 'acceptable': 65, 'good': 80, 'excellent': 80, 'min': 50, 'ideal': 70, 'max': 80, 'unit': '%', 'higher_better': True},
    'View_Content_Rate': {'weak': 40, 'acceptable': 55, 'good': 70, 'excellent': 70, 'min': 40, 'ideal': 55, 'max': 70, 'unit': '%', 'higher_better': True},
    'ATC_Rate': {'weak': 10, 'acceptable': 20, 'good': 35, 'excellent': 35, 'min': 10, 'ideal': 20, 'max': 35, 'unit': '%', 'higher_better': True},
    'Checkout_Rate': {'weak': 40, 'acceptable': 55, 'good': 70, 'excellent': 70, 'min': 40, 'ideal': 55, 'max': 70, 'unit': '%', 'higher_better': True},
    'Purchase_Rate': {'weak': 40, 'acceptable': 55, 'good': 70, 'excellent': 70, 'min': 40, 'ideal': 55, 'max': 70, 'unit': '%', 'higher_better': True},
    'Overall_CVR': {'weak': 1, 'acceptable': 2, 'good': 4, 'excellent': 4, 'min': 1, 'ideal': 3, 'max': 4, 'unit': '%', 'higher_better': True},
    'CPA': {'weak': 600, 'acceptable': 400, 'good': 200, 'excellent': 200, 'min': 400, 'ideal': 300, 'max': 200, 'unit': '₹', 'higher_better': False},
    'Cost_per_ATC': {'weak': 300, 'acceptable': 150, 'good': 75, 'excellent': 75, 'min': 150, 'ideal': 100, 'max': 75, 'unit': '₹', 'higher_better': False},
    'Cost_per_Checkout': {'weak': 500, 'acceptable': 300, 'good': 150, 'excellent': 150, 'min': 300, 'ideal': 200, 'max': 150, 'unit': '₹', 'higher_better': False},
    'ROAS': {'weak': 2, 'acceptable': 3, 'good': 5, 'excellent': 5, 'min': 2, 'ideal': 4, 'max': 5, 'unit': 'x', 'higher_better': True},
    'ACoS': {'weak': 50, 'acceptable': 33, 'good': 20, 'excellent': 20, 'min': 33, 'ideal': 25, 'max': 20, 'unit': '%', 'higher_better': False},
    'AOV': {'weak': 400, 'acceptable': 600, 'good': 900, 'excellent': 900, 'min': 400, 'ideal': 600, 'max': 900, 'unit': '₹', 'higher_better': True},
    'MER': {'weak': 1.5, 'acceptable': 2.5, 'good': 4, 'excellent': 4, 'min': 1.5, 'ideal': 2.5, 'max': 4, 'unit': 'x', 'higher_better': True},
}

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')
log = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════
# 2. META GRAPH API — simple requests-based client
# ═══════════════════════════════════════════════════════════
def graph_get(endpoint, params=None):
    """GET request to Meta Graph API."""
    p = dict(params or {})
    p['access_token'] = META_ACCESS_TOKEN
    url = f'https://graph.facebook.com/{META_API_VERSION}/{endpoint}'
    r = requests.get(url, params=p, timeout=60)
    if r.status_code != 200:
        log.error(f'API error {r.status_code}: {r.text[:500]}')
        r.raise_for_status()
    return r.json()


def get_active_campaigns():
    """Fetch all campaigns, return only ACTIVE ones."""
    all_campaigns = []
    next_url = f'{META_AD_ACCOUNT_ID}/campaigns'
    params = {'fields': 'name,id,status', 'limit': 200}

    while next_url:
        data = graph_get(next_url, params)
        all_campaigns.extend(data.get('data', []))

        # Handle pagination
        paging = data.get('paging', {})
        next_full_url = paging.get('next')
        if next_full_url:
            # Extract endpoint from full URL for next call
            next_url = next_full_url.replace(f'https://graph.facebook.com/{META_API_VERSION}/', '')
            params = {}  # Already in the URL
        else:
            next_url = None

    return [c for c in all_campaigns if c.get('status') == 'ACTIVE']


def fetch_insights(campaign_ids, start_date, end_date):
    """Fetch performance insights for given campaigns and date range."""
    fields = [
        'campaign_id', 'campaign_name', 'date_start',
        'impressions', 'clicks', 'spend', 'reach', 'frequency',
        'cpc', 'cpm', 'ctr', 'outbound_clicks', 'actions',
        'action_values', 'video_thruplay_watched_actions',
    ]

    data = graph_get(f'{META_AD_ACCOUNT_ID}/insights', {
        'fields': ','.join(fields),
        'level': 'campaign',
        'time_increment': 1,
        'filtering': json.dumps([{
            'field': 'campaign.id', 'operator': 'IN', 'value': campaign_ids
        }]),
        'time_range': json.dumps({
            'since': start_date.strftime('%Y-%m-%d'),
            'until': end_date.strftime('%Y-%m-%d'),
        }),
        'limit': 500,
    })

    rows = []
    for ins in data.get('data', []):
        row = {
            'date': pd.to_datetime(ins.get('date_start')),
            'campaign_name': ins.get('campaign_name', 'Unknown'),
            'impressions': int(ins.get('impressions', 0)),
            'clicks': int(ins.get('clicks', 0)),
            'spend': float(ins.get('spend', 0)),
            'reach': int(ins.get('reach', 0)),
            'frequency': float(ins.get('frequency', 0)),
            'cpc': float(ins.get('cpc') or 0),
            'cpm': float(ins.get('cpm') or 0),
            'ctr': float(ins.get('ctr') or 0),
            'outbound_clicks': 0, 'video_3s_views': 0, 'video_thruplay': 0,
            'lp_views': 0, 'view_content': 0, 'adds_to_cart': 0,
            'checkouts': 0, 'purchases': 0, 'revenue': 0,
            'entity_name': ins.get('campaign_name'),
        }

        # Outbound clicks
        for oc in (ins.get('outbound_clicks') or []):
            if oc.get('action_type') == 'outbound_click':
                row['outbound_clicks'] = int(oc.get('value', 0))
                break

        # ThruPlay
        for vt in (ins.get('video_thruplay_watched_actions') or []):
            row['video_thruplay'] = int(vt.get('value', 0))
            break

        # Actions
        for a in (ins.get('actions') or []):
            at = a.get('action_type', '')
            val = int(a.get('value', 0))
            if not at:
                continue
            if 'landing_page_view' in at:
                row['lp_views'] = val
            elif at in ('view_content', 'offsite_conversion.fb_pixel_view_content'):
                row['view_content'] = val
            elif 'add_to_cart' in at:
                row['adds_to_cart'] = val
            elif 'initiate_checkout' in at:
                row['checkouts'] = val
            elif 'purchase' in at:
                row['purchases'] = val
            elif at == 'video_view':
                row['video_3s_views'] = val

        # Revenue
        rev_found = False
        for av in (ins.get('action_values') or []):
            if 'purchase' in av.get('action_type', ''):
                row['revenue'] = float(av.get('value', 0))
                rev_found = True
                break
        if not rev_found and row['purchases'] > 0:
            row['revenue'] = row['purchases'] * DEFAULT_AOV

        rows.append(row)

    if not rows:
        return None
    df = pd.DataFrame(rows)
    df['product'] = df['entity_name']
    return df


# ═══════════════════════════════════════════════════════════
# 3. METRIC CALCULATIONS — same as dashboard
# ═══════════════════════════════════════════════════════════
def pct(a, b):
    return (a / b * 100) if b > 0 else 0


def sdiv(a, b):
    return (a / b) if b > 0 else 0


def calculate_metrics(df):
    t = df.sum(numeric_only=True)
    return {
        'CTR': pct(t.clicks, t.impressions),
        'Outbound_CTR': pct(t.outbound_clicks, t.impressions),
        'Hook_Rate': pct(t.video_3s_views, t.impressions),
        'ThruPlay_Rate': pct(t.video_thruplay, t.impressions),
        'CPM': sdiv(t.spend, t.impressions) * 1000,
        'Frequency': t.frequency / len(df) if len(df) > 0 else 0,
        'CPC': sdiv(t.spend, t.clicks),
        'LP_View_Rate': pct(t.lp_views, t.clicks),
        'View_Content_Rate': pct(t.view_content, t.lp_views),
        'ATC_Rate': pct(t.adds_to_cart, t.lp_views),
        'Checkout_Rate': pct(t.checkouts, t.adds_to_cart),
        'Purchase_Rate': pct(t.purchases, t.checkouts),
        'Overall_CVR': pct(t.purchases, t.clicks),
        'CPA': sdiv(t.spend, t.purchases),
        'Cost_per_ATC': sdiv(t.spend, t.adds_to_cart),
        'Cost_per_Checkout': sdiv(t.spend, t.checkouts),
        'ROAS': sdiv(t.revenue, t.spend),
        'ACoS': pct(t.spend, t.revenue),
        'AOV': sdiv(t.revenue, t.purchases),
        'MER': sdiv(t.revenue, t.spend),
        'totals': {
            'impressions': t.impressions, 'clicks': t.clicks,
            'outbound_clicks': t.outbound_clicks,
            'video_3s_views': t.video_3s_views, 'video_thruplay': t.video_thruplay,
            'lp_views': t.lp_views, 'view_content': t.view_content,
            'adds_to_cart': t.adds_to_cart, 'checkouts': t.checkouts,
            'purchases': t.purchases, 'spend': t.spend,
            'revenue': t.revenue, 'reach': t.reach,
        }
    }


def calculate_daily_metrics(df):
    d = df.copy()
    sp = lambda a, b: (a / b * 100).fillna(0).replace([float('inf'), float('-inf')], 0)
    sd = lambda a, b: (a / b).fillna(0).replace([float('inf'), float('-inf')], 0)
    d['CTR'] = sp(d.clicks, d.impressions)
    d['Outbound_CTR'] = sp(d.outbound_clicks, d.impressions)
    d['Hook_Rate'] = sp(d.video_3s_views, d.impressions)
    d['ThruPlay_Rate'] = sp(d.video_thruplay, d.impressions)
    d['CPM'] = sd(d.spend, d.impressions) * 1000
    d['CPC'] = sd(d.spend, d.clicks)
    d['LP_View_Rate'] = sp(d.lp_views, d.clicks)
    d['View_Content_Rate'] = sp(d.view_content, d.lp_views)
    d['ATC_Rate'] = sp(d.adds_to_cart, d.lp_views)
    d['Checkout_Rate'] = sp(d.checkouts, d.adds_to_cart)
    d['Purchase_Rate'] = sp(d.purchases, d.checkouts)
    d['Overall_CVR'] = sp(d.purchases, d.clicks)
    d['CPA'] = sd(d.spend, d.purchases)
    d['Cost_per_ATC'] = sd(d.spend, d.adds_to_cart)
    d['Cost_per_Checkout'] = sd(d.spend, d.checkouts)
    d['ROAS'] = sd(d.revenue, d.spend)
    d['ACoS'] = sp(d.spend, d.revenue)
    d['AOV'] = sd(d.revenue, d.purchases)
    d['MER'] = sd(d.revenue, d.spend)
    return d


def get_status_emoji(mn, v):
    if mn not in BENCHMARKS:
        return ''
    b = BENCHMARKS[mn]
    hb = b['higher_better']
    if hb:
        return '✅' if v >= b['good'] else '⚠️' if v >= b['acceptable'] else '🚨'
    return '✅' if v <= b['good'] else '⚠️' if v <= b['acceptable'] else '🚨'


def get_status_label(mn, v):
    if mn not in BENCHMARKS:
        return 'N/A'
    b = BENCHMARKS[mn]
    hb = b['higher_better']
    if hb:
        if v >= b['excellent']: return 'Excellent'
        elif v >= b['good']: return 'Good'
        elif v >= b['acceptable']: return 'Acceptable'
        return 'Weak'
    if v <= b['excellent']: return 'Excellent'
    elif v <= b['good']: return 'Good'
    elif v <= b['acceptable']: return 'Acceptable'
    return 'Weak'


def get_recommendations(metrics):
    issues = []
    checks = [
        ('CTR', True, 'MEDIUM', 'CTR', ['Test different creatives', 'Improve targeting']),
        ('Hook_Rate', True, 'HIGH', 'Hook Rate', ['Redesign first 3 seconds of video', 'Use text overlays']),
        ('ATC_Rate', True, 'HIGH', 'Add to Cart Rate', ['Improve product page', 'Add social proof']),
        ('Checkout_Rate', True, 'CRITICAL', 'Checkout Rate', ['Enable guest checkout', 'Simplify checkout flow']),
        ('ROAS', True, 'CRITICAL', 'ROAS', ['Cut underperforming spend', 'Increase AOV']),
        ('CPM', False, 'MEDIUM', 'CPM', ['Broaden targeting', 'Test placements']),
    ]
    for m, hb, pri, label, recs in checks:
        v = metrics.get(m, 0)
        b = BENCHMARKS.get(m, {})
        th = b.get('min', 0)
        if hb and 0 < v < th:
            issues.append({'priority': pri, 'metric': label, 'current': v, 'target': b.get('ideal', 0), 'recommendations': recs})
        elif not hb and v > th > 0:
            issues.append({'priority': pri, 'metric': label, 'current': v, 'target': b.get('ideal', 0), 'recommendations': recs})
    issues.sort(key=lambda x: {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}.get(x['priority'], 9))
    return issues


# ═══════════════════════════════════════════════════════════
# 4. EMAIL
# ═══════════════════════════════════════════════════════════
def send_simple_email(subject, html_body):
    """Send an email without any attachment."""
    msg = MIMEMultipart('mixed')
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)
    log.info(f'Email sent to {EMAIL_TO}')


def send_no_activity_email(report_date, reason, campaign_names=None):
    """Short email when there's no data to report — just so you know the system is alive."""
    subject = f'📊 Meta Ads — {report_date.strftime("%b %d")} | No activity'

    campaigns_html = ''
    if campaign_names:
        clist = ', '.join(campaign_names[:5])
        if len(campaign_names) > 5:
            clist += f' +{len(campaign_names) - 5} more'
        campaigns_html = f'<p style="color:#64748b;font-size:13px;margin:10px 0 0 0">Active campaigns: {clist}</p>'

    html = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #6b7280; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0;">📊 Daily Meta Ads Report</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">{report_date.strftime('%A, %B %d, %Y')}</p>
      </div>
      <div style="background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0; border-radius: 0 0 8px 8px;">
        <p style="margin: 0; font-size: 14px; color: #374151;">
          <strong>No report generated for yesterday.</strong>
        </p>
        <p style="margin: 10px 0 0 0; font-size: 13px; color: #64748b;">
          Reason: {reason}
        </p>
        {campaigns_html}
        <p style="margin: 20px 0 0 0; font-size: 12px; color: #94a3b8;">
          This is an automated heads-up so you know the daily report script ran successfully. No PDF attached since there's nothing to report on.
        </p>
      </div>
    </div>
    """
    send_simple_email(subject, html)


def send_email(subject, html_body, pdf_bytes, pdf_filename):
    msg = MIMEMultipart('mixed')
    msg['From'] = EMAIL_FROM
    msg['To'] = EMAIL_TO
    msg['Subject'] = subject
    msg.attach(MIMEText(html_body, 'html'))

    pdf = MIMEApplication(pdf_bytes, _subtype='pdf')
    pdf.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
    msg.attach(pdf)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as s:
        s.starttls()
        s.login(SMTP_USER, SMTP_PASSWORD)
        s.send_message(msg)
    log.info(f'Email sent to {EMAIL_TO}')


def build_email_body(report_date, metrics, campaign_names):
    t = metrics['totals']
    roas = metrics['ROAS']
    roas_color = '#059669' if roas >= 3 else '#d97706' if roas >= 2 else '#dc2626'
    clist = ', '.join(campaign_names[:5])
    if len(campaign_names) > 5:
        clist += f' +{len(campaign_names) - 5} more'

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
      <div style="background: #1e40af; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
        <h2 style="margin: 0;">📊 Daily Meta Ads Report</h2>
        <p style="margin: 5px 0 0 0; opacity: 0.9;">{report_date.strftime('%A, %B %d, %Y')}</p>
      </div>
      <div style="background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0;">
        <p style="color: #64748b; font-size: 13px; margin-top: 0;">Active campaigns: {clist}</p>
        <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
          <tr>
            <td style="padding: 12px; background: #eff6ff; border-radius: 6px; text-align: center; width: 33%;">
              <div style="font-size: 11px; color: #64748b;">Spend</div>
              <div style="font-size: 22px; font-weight: bold; color: #1e40af;">₹{t['spend']:,.0f}</div>
            </td>
            <td style="width: 8px;"></td>
            <td style="padding: 12px; background: #ecfdf5; border-radius: 6px; text-align: center; width: 33%;">
              <div style="font-size: 11px; color: #64748b;">Revenue</div>
              <div style="font-size: 22px; font-weight: bold; color: #059669;">₹{t['revenue']:,.0f}</div>
            </td>
            <td style="width: 8px;"></td>
            <td style="padding: 12px; background: #fefce8; border-radius: 6px; text-align: center; width: 33%;">
              <div style="font-size: 11px; color: #64748b;">ROAS</div>
              <div style="font-size: 22px; font-weight: bold; color: {roas_color};">{roas:.2f}x</div>
            </td>
          </tr>
        </table>
        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
          <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px 0; color: #64748b;">Purchases</td><td style="padding: 8px 0; text-align: right; font-weight: 600;">{int(t['purchases'])}</td></tr>
          <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px 0; color: #64748b;">CPA</td><td style="padding: 8px 0; text-align: right; font-weight: 600;">₹{metrics['CPA']:,.0f}</td></tr>
          <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px 0; color: #64748b;">CTR</td><td style="padding: 8px 0; text-align: right; font-weight: 600;">{metrics['CTR']:.2f}%</td></tr>
          <tr style="border-bottom: 1px solid #e2e8f0;"><td style="padding: 8px 0; color: #64748b;">CPM</td><td style="padding: 8px 0; text-align: right; font-weight: 600;">₹{metrics['CPM']:,.0f}</td></tr>
          <tr><td style="padding: 8px 0; color: #64748b;">Overall CVR</td><td style="padding: 8px 0; text-align: right; font-weight: 600;">{metrics['Overall_CVR']:.2f}%</td></tr>
        </table>
      </div>
      <div style="background: #f1f5f9; padding: 15px; border-radius: 0 0 8px 8px; border: 1px solid #e2e8f0; border-top: 0;">
        <p style="margin: 0; font-size: 12px; color: #94a3b8; text-align: center;">📎 Full PDF report attached</p>
      </div>
    </div>
    """


# ═══════════════════════════════════════════════════════════
# 5. MAIN
# ═══════════════════════════════════════════════════════════
def main():
    log.info('=' * 50)
    log.info('Daily Meta Ads Email Report')
    log.info('=' * 50)

    # Validate config
    missing = []
    if not META_ACCESS_TOKEN: missing.append('META_ACCESS_TOKEN')
    if not SMTP_USER: missing.append('SMTP_USER')
    if not SMTP_PASSWORD: missing.append('SMTP_PASSWORD')
    if not EMAIL_TO: missing.append('EMAIL_TO')
    if missing:
        log.error(f'Missing required env vars: {", ".join(missing)}')
        sys.exit(1)

    # Report for yesterday
    report_date = (datetime.now() - timedelta(days=1)).date()
    log.info(f'Report date: {report_date}')

    # Get active campaigns
    log.info('Fetching active campaigns...')
    campaigns = get_active_campaigns()
    if not campaigns:
        log.warning('No active campaigns. Sending heads-up email.')
        send_no_activity_email(report_date, reason='No active campaigns were running.')
        return
    campaign_ids = [c['id'] for c in campaigns]
    campaign_names = [c['name'] for c in campaigns]
    log.info(f'Found {len(campaigns)} active: {", ".join(campaign_names[:3])}{"..." if len(campaign_names) > 3 else ""}')

    # Fetch performance data for yesterday
    log.info(f'Fetching insights for {report_date}...')
    df = fetch_insights(campaign_ids, report_date, report_date)
    if df is None or len(df) == 0:
        log.warning('No spend data for yesterday. Sending heads-up email.')
        send_no_activity_email(
            report_date,
            reason='Active campaigns exist, but none spent yesterday.',
            campaign_names=campaign_names,
        )
        return
    log.info(f'Got {len(df)} row(s) of data')

    # Aggregate if multiple campaigns
    if len(df['product'].unique()) > 1:
        df_combined = df.groupby('date', as_index=False).agg({
            'impressions': 'sum', 'clicks': 'sum', 'spend': 'sum',
            'reach': 'sum', 'frequency': 'mean', 'cpm': 'mean',
            'lp_views': 'sum', 'view_content': 'sum', 'adds_to_cart': 'sum',
            'checkouts': 'sum', 'purchases': 'sum', 'revenue': 'sum',
            'outbound_clicks': 'sum', 'video_3s_views': 'sum', 'video_thruplay': 'sum',
        })
        df_combined['product'] = 'All Active Campaigns'
    else:
        df_combined = df

    metrics = calculate_metrics(df_combined)
    log.info(f'Spend: ₹{metrics["totals"]["spend"]:,.0f} | Revenue: ₹{metrics["totals"]["revenue"]:,.0f} | ROAS: {metrics["ROAS"]:.2f}x')

    # Generate PDF using the same module as the dashboard
    log.info('Generating PDF...')
    from generate_pdf_report_v2 import generate_pdf_report
    pdf_bytes = generate_pdf_report(
        product_name='All Active Campaigns',
        df=df_combined,
        metrics=metrics,
        mode='Campaign Mode',
        BENCHMARKS=BENCHMARKS,
        calculate_metrics=calculate_metrics,
        calculate_daily_metrics=calculate_daily_metrics,
        get_status_emoji=get_status_emoji,
        get_status_label=get_status_label,
        get_recommendations=get_recommendations,
    )
    if not pdf_bytes:
        log.error('PDF generation returned empty!')
        sys.exit(1)
    log.info(f'PDF: {len(pdf_bytes):,} bytes')

    # Send email
    subject = f'📊 Meta Ads — {report_date.strftime("%b %d")} | ₹{metrics["totals"]["spend"]:,.0f} spent, {metrics["ROAS"]:.1f}x ROAS'
    filename = f'Meta_Ads_{report_date.strftime("%Y_%m_%d")}.pdf'
    log.info('Sending email...')
    send_email(
        subject=subject,
        html_body=build_email_body(report_date, metrics, campaign_names),
        pdf_bytes=pdf_bytes,
        pdf_filename=filename,
    )
    log.info('✅ Done!')


if __name__ == '__main__':
    main()
