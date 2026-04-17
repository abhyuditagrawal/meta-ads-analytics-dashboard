#!/usr/bin/env python3
"""
Daily Meta Ads Email Report
============================
Standalone script — runs independently of Streamlit.

What it does:
  1. Connects to Meta API using your System User token
  2. Fetches yesterday's data for ALL active campaigns
  3. Generates the PDF report
  4. Emails it to you as an attachment

Schedule to run at midnight (or any time) via:
  - cron:             0 0 * * * /usr/bin/python3 /path/to/daily_email_report.py
  - GitHub Actions:   see sample workflow at bottom of this file
  - PythonAnywhere:   Tasks → add daily task

Configuration:
  Set these as environment variables (or edit the CONFIG section below).
"""

import os
import sys
import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
from datetime import datetime, timedelta
from typing import Dict, List

import pandas as pd
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount

# ─────────────────────────────────────────────────────────
# CONFIG — set via environment variables or edit directly
# ─────────────────────────────────────────────────────────
CONFIG = {
    # Meta API
    'META_APP_ID': os.environ.get('META_APP_ID', '1196805395915193'),
    'META_APP_SECRET': os.environ.get('META_APP_SECRET', '7aa8c5a3254f8abcdb657e54642dd92b'),
    'META_ACCESS_TOKEN': os.environ.get('META_ACCESS_TOKEN', ''),  # System User token — required
    'META_AD_ACCOUNT_ID': os.environ.get('META_AD_ACCOUNT_ID', 'act_24472841068985090'),

    # Email — use Gmail App Password (not your regular password)
    # To get a Gmail App Password: Google Account → Security → 2-Step Verification → App Passwords
    'SMTP_HOST': os.environ.get('SMTP_HOST', 'smtp.gmail.com'),
    'SMTP_PORT': int(os.environ.get('SMTP_PORT', '587')),
    'SMTP_USER': os.environ.get('SMTP_USER', ''),          # your email, e.g. you@gmail.com
    'SMTP_PASSWORD': os.environ.get('SMTP_PASSWORD', ''),   # Gmail App Password (16 chars)
    'EMAIL_TO': os.environ.get('EMAIL_TO', ''),              # recipient email (can be same)
    'EMAIL_FROM': os.environ.get('EMAIL_FROM', ''),          # sender display, e.g. you@gmail.com
}

# Default AOV for fallback revenue calculation
DEFAULT_AOV = 600

# ─────────────────────────────────────────────────────────
# BENCHMARKS (same as dashboard)
# ─────────────────────────────────────────────────────────
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


# ─────────────────────────────────────────────────────────
# HELPER FUNCTIONS (same logic as dashboard — no Streamlit)
# ─────────────────────────────────────────────────────────
def get_status_emoji(metric_name, value):
    if metric_name not in BENCHMARKS:
        return ''
    bench = BENCHMARKS[metric_name]
    hb = bench.get('higher_better', True)
    if hb:
        return '✅' if value >= bench['good'] else '⚠️' if value >= bench['acceptable'] else '🚨'
    else:
        return '✅' if value <= bench['good'] else '⚠️' if value <= bench['acceptable'] else '🚨'


def get_status_label(metric_name, value):
    if metric_name not in BENCHMARKS:
        return 'N/A'
    bench = BENCHMARKS[metric_name]
    hb = bench.get('higher_better', True)
    if hb:
        if value >= bench['excellent']: return 'Excellent'
        elif value >= bench['good']: return 'Good'
        elif value >= bench['acceptable']: return 'Acceptable'
        else: return 'Weak'
    else:
        if value <= bench['excellent']: return 'Excellent'
        elif value <= bench['good']: return 'Good'
        elif value <= bench['acceptable']: return 'Acceptable'
        else: return 'Weak'


def calculate_metrics(df):
    totals = df.sum(numeric_only=True)
    pct = lambda a, b: (a / b * 100) if b > 0 else 0
    sdiv = lambda a, b: (a / b) if b > 0 else 0

    return {
        'CTR': pct(totals.clicks, totals.impressions),
        'Outbound_CTR': pct(totals.outbound_clicks, totals.impressions),
        'Hook_Rate': pct(totals.video_3s_views, totals.impressions),
        'ThruPlay_Rate': pct(totals.video_thruplay, totals.impressions),
        'CPM': sdiv(totals.spend, totals.impressions) * 1000,
        'Frequency': totals.frequency / len(df) if len(df) > 0 else 0,
        'CPC': sdiv(totals.spend, totals.clicks),
        'LP_View_Rate': pct(totals.lp_views, totals.clicks),
        'View_Content_Rate': pct(totals.view_content, totals.lp_views),
        'ATC_Rate': pct(totals.adds_to_cart, totals.lp_views),
        'Checkout_Rate': pct(totals.checkouts, totals.adds_to_cart),
        'Purchase_Rate': pct(totals.purchases, totals.checkouts),
        'Overall_CVR': pct(totals.purchases, totals.clicks),
        'CPA': sdiv(totals.spend, totals.purchases),
        'Cost_per_ATC': sdiv(totals.spend, totals.adds_to_cart),
        'Cost_per_Checkout': sdiv(totals.spend, totals.checkouts),
        'ROAS': sdiv(totals.revenue, totals.spend),
        'ACoS': pct(totals.spend, totals.revenue),
        'AOV': sdiv(totals.revenue, totals.purchases),
        'MER': sdiv(totals.revenue, totals.spend),
        'totals': {
            'impressions': totals.impressions, 'clicks': totals.clicks,
            'outbound_clicks': totals.outbound_clicks,
            'video_3s_views': totals.video_3s_views, 'video_thruplay': totals.video_thruplay,
            'lp_views': totals.lp_views, 'view_content': totals.view_content,
            'adds_to_cart': totals.adds_to_cart, 'checkouts': totals.checkouts,
            'purchases': totals.purchases, 'spend': totals.spend,
            'revenue': totals.revenue, 'reach': totals.reach,
        }
    }


def calculate_daily_metrics(df):
    daily = df.copy()
    sp = lambda a, b: (a / b * 100).fillna(0).replace([float('inf'), float('-inf')], 0)
    sd = lambda a, b: (a / b).fillna(0).replace([float('inf'), float('-inf')], 0)

    daily['CTR'] = sp(daily['clicks'], daily['impressions'])
    daily['Outbound_CTR'] = sp(daily['outbound_clicks'], daily['impressions'])
    daily['Hook_Rate'] = sp(daily['video_3s_views'], daily['impressions'])
    daily['ThruPlay_Rate'] = sp(daily['video_thruplay'], daily['impressions'])
    daily['CPM'] = sd(daily['spend'], daily['impressions']) * 1000
    daily['CPC'] = sd(daily['spend'], daily['clicks'])
    daily['LP_View_Rate'] = sp(daily['lp_views'], daily['clicks'])
    daily['View_Content_Rate'] = sp(daily['view_content'], daily['lp_views'])
    daily['ATC_Rate'] = sp(daily['adds_to_cart'], daily['lp_views'])
    daily['Checkout_Rate'] = sp(daily['checkouts'], daily['adds_to_cart'])
    daily['Purchase_Rate'] = sp(daily['purchases'], daily['checkouts'])
    daily['Overall_CVR'] = sp(daily['purchases'], daily['clicks'])
    daily['CPA'] = sd(daily['spend'], daily['purchases'])
    daily['Cost_per_ATC'] = sd(daily['spend'], daily['adds_to_cart'])
    daily['Cost_per_Checkout'] = sd(daily['spend'], daily['checkouts'])
    daily['ROAS'] = sd(daily['revenue'], daily['spend'])
    daily['ACoS'] = sp(daily['spend'], daily['revenue'])
    daily['AOV'] = sd(daily['revenue'], daily['purchases'])
    daily['MER'] = sd(daily['revenue'], daily['spend'])
    return daily


def get_recommendations(metrics):
    issues = []
    checks = [
        ('CTR', True, 'MEDIUM', 'Click-Through Rate', ['Test different ad creatives', 'Improve targeting', 'Use compelling CTAs']),
        ('Hook_Rate', True, 'HIGH', 'Hook Rate', ['Redesign first 3 seconds', 'Use text overlays', 'Front-load compelling visuals']),
        ('LP_View_Rate', True, 'HIGH', 'LP View Rate', ['Improve page load speed', 'Optimize for mobile', 'Check for broken links']),
        ('ATC_Rate', True, 'HIGH', 'Add to Cart Rate', ['Improve product page', 'Add social proof', 'Simplify ATC experience']),
        ('Checkout_Rate', True, 'CRITICAL', 'Checkout Rate', ['Enable guest checkout', 'Add UPI/COD/Cards', 'Simplify checkout flow']),
        ('ROAS', True, 'CRITICAL', 'ROAS', ['Increase AOV', 'Improve CVR', 'Cut underperforming spend']),
        ('CPM', False, 'MEDIUM', 'CPM', ['Broaden targeting', 'Test different placements', 'Improve ad quality score']),
    ]

    for metric, higher_better, priority, label, recs in checks:
        val = metrics.get(metric, 0)
        bench = BENCHMARKS.get(metric, {})
        threshold = bench.get('min', 0)

        if higher_better and val < threshold and val > 0:
            issues.append({'priority': priority, 'metric': label, 'current': val, 'target': bench.get('ideal', 0), 'recommendations': recs})
        elif not higher_better and val > threshold and val > 0:
            issues.append({'priority': priority, 'metric': label, 'current': val, 'target': bench.get('ideal', 0), 'recommendations': recs})

    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
    issues.sort(key=lambda x: priority_order.get(x['priority'], 99))
    return issues


# ─────────────────────────────────────────────────────────
# META API — fetch data (no Streamlit dependency)
# ─────────────────────────────────────────────────────────
def fetch_campaign_data(ad_account_id, campaign_ids, report_date):
    """Fetch one day of data for given campaigns."""

    def parse_insight(insight):
        """Parse a single insight row (works for both SDK objects and dicts)."""
        get = insight.get if isinstance(insight, dict) else lambda k, d=None: insight.get(k, d)

        row = {
            'date': pd.to_datetime(get('date_start')),
            'campaign_name': get('campaign_name', 'Unknown'),
            'impressions': int(get('impressions', 0)),
            'clicks': int(get('clicks', 0)),
            'spend': float(get('spend', 0)),
            'reach': int(get('reach', 0)),
            'frequency': float(get('frequency', 0)),
            'cpc': float(get('cpc', 0) or 0),
            'cpm': float(get('cpm', 0) or 0),
            'ctr': float(get('ctr', 0) or 0),
            'lp_views': 0, 'view_content': 0, 'adds_to_cart': 0,
            'checkouts': 0, 'purchases': 0, 'revenue': 0,
            'outbound_clicks': 0, 'video_3s_views': 0, 'video_thruplay': 0,
            'entity_name': get('campaign_name'),
        }

        for oc in (get('outbound_clicks') or []):
            if oc.get('action_type') == 'outbound_click':
                row['outbound_clicks'] = int(oc.get('value', 0))
                break

        for vt in (get('video_thruplay_watched_actions') or []):
            row['video_thruplay'] = int(vt.get('value', 0))
            break

        for action in (get('actions') or []):
            at = action.get('action_type', '')
            if not at:
                continue
            val = int(action.get('value', 0))
            if 'landing_page_view' in at:
                row['lp_views'] = val
            elif at in ('view_content', 'offsite_conversion.fb_pixel_view_content'):
                row['view_content'] = val
            elif 'add_to_cart' in at or at == 'offsite_conversion.fb_pixel_add_to_cart':
                row['adds_to_cart'] = val
            elif 'initiate_checkout' in at or at == 'offsite_conversion.fb_pixel_initiate_checkout':
                row['checkouts'] = val
            elif 'purchase' in at or at == 'offsite_conversion.fb_pixel_purchase':
                row['purchases'] = val
            elif at == 'video_view':
                row['video_3s_views'] = val

        revenue_found = False
        for av in (get('action_values') or []):
            at = av.get('action_type', '')
            if not at:
                continue
            if 'purchase' in at or at == 'offsite_conversion.fb_pixel_purchase':
                row['revenue'] = float(av.get('value', 0))
                revenue_found = True
                break
        if not revenue_found and row['purchases'] > 0:
            row['revenue'] = row['purchases'] * DEFAULT_AOV

        return row

    # Try SDK first
    try:
        ad_account = AdAccount(ad_account_id)

        fields = [
            'campaign_id', 'campaign_name', 'date_start',
            'impressions', 'clicks', 'spend', 'reach', 'frequency',
            'cpc', 'cpm', 'ctr', 'outbound_clicks', 'actions',
            'action_values', 'video_thruplay_watched_actions',
        ]

        params = {
            'level': 'campaign',
            'time_increment': 1,
            'filtering': [{'field': 'campaign.id', 'operator': 'IN', 'value': campaign_ids}],
            'time_range': {
                'since': report_date.strftime('%Y-%m-%d'),
                'until': report_date.strftime('%Y-%m-%d'),
            }
        }

        insights = ad_account.get_insights(fields=fields, params=params)
        data_list = [parse_insight(i) for i in insights]

    except Exception as sdk_err:
        log.warning(f"SDK insights call failed: {sdk_err}")
        log.info("Trying direct API call as fallback...")

        import requests
        import json

        url = f"https://graph.facebook.com/v21.0/{ad_account_id}/insights"
        params = {
            'fields': ','.join([
                'campaign_id', 'campaign_name', 'date_start',
                'impressions', 'clicks', 'spend', 'reach', 'frequency',
                'cpc', 'cpm', 'ctr', 'outbound_clicks', 'actions',
                'action_values', 'video_thruplay_watched_actions',
            ]),
            'level': 'campaign',
            'time_increment': 1,
            'filtering': json.dumps([{'field': 'campaign.id', 'operator': 'IN', 'value': campaign_ids}]),
            'time_range': json.dumps({
                'since': report_date.strftime('%Y-%m-%d'),
                'until': report_date.strftime('%Y-%m-%d'),
            }),
            'access_token': CONFIG['META_ACCESS_TOKEN'],
            'limit': 500,
        }

        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()
        data_list = [parse_insight(i) for i in data.get('data', [])]

    if data_list:
        df = pd.DataFrame(data_list)
        df['product'] = df['entity_name']
        return df
    return None


def get_active_campaigns(ad_account_id):
    """Get all ACTIVE campaign IDs."""
    # Try SDK first, fall back to direct API call if SDK has JSON parsing issues
    try:
        ad_account = AdAccount(ad_account_id)
        campaigns = ad_account.get_campaigns(
            fields=['name', 'id', 'status', 'objective']
        )
        return [{'id': c['id'], 'name': c['name']} for c in campaigns if c.get('status') == 'ACTIVE']
    except Exception as sdk_err:
        log.warning(f"SDK call failed: {sdk_err}")
        log.info("Trying direct API call as fallback...")

        # Direct API call using requests
        import requests
        url = f"https://graph.facebook.com/v21.0/{ad_account_id}/campaigns"
        params = {
            'fields': 'name,id,status,objective',
            'access_token': CONFIG['META_ACCESS_TOKEN'],
            'limit': 500,
        }
        resp = requests.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

        campaigns = data.get('data', [])
        return [{'id': c['id'], 'name': c['name']} for c in campaigns if c.get('status') == 'ACTIVE']


# ─────────────────────────────────────────────────────────
# EMAIL
# ─────────────────────────────────────────────────────────
def send_email(subject, body_html, pdf_bytes, pdf_filename):
    """Send email with PDF attachment via SMTP."""

    msg = MIMEMultipart('mixed')
    msg['From'] = CONFIG['EMAIL_FROM']
    msg['To'] = CONFIG['EMAIL_TO']
    msg['Subject'] = subject

    # HTML body
    html_part = MIMEText(body_html, 'html')
    msg.attach(html_part)

    # PDF attachment
    pdf_part = MIMEApplication(pdf_bytes, _subtype='pdf')
    pdf_part.add_header('Content-Disposition', 'attachment', filename=pdf_filename)
    msg.attach(pdf_part)

    with smtplib.SMTP(CONFIG['SMTP_HOST'], CONFIG['SMTP_PORT']) as server:
        server.starttls()
        server.login(CONFIG['SMTP_USER'], CONFIG['SMTP_PASSWORD'])
        server.send_message(msg)

    log.info(f"Email sent to {CONFIG['EMAIL_TO']}")


def build_email_body(report_date, metrics, campaign_names):
    """Build a clean HTML email body with key metrics."""

    totals = metrics.get('totals', {})
    roas = metrics.get('ROAS', 0)
    roas_color = '#059669' if roas >= 3 else '#d97706' if roas >= 2 else '#dc2626'

    campaigns_list = ', '.join(campaign_names[:5])
    if len(campaign_names) > 5:
        campaigns_list += f' +{len(campaign_names) - 5} more'

    return f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 600px; margin: 0 auto;">
        <div style="background: #1e40af; color: white; padding: 20px; border-radius: 8px 8px 0 0;">
            <h2 style="margin: 0;">📊 Daily Meta Ads Report</h2>
            <p style="margin: 5px 0 0 0; opacity: 0.9;">{report_date.strftime('%A, %B %d, %Y')}</p>
        </div>

        <div style="background: #f8fafc; padding: 20px; border: 1px solid #e2e8f0;">
            <p style="color: #64748b; font-size: 13px; margin-top: 0;">
                Active campaigns: {campaigns_list}
            </p>

            <table style="width: 100%; border-collapse: collapse; margin: 15px 0;">
                <tr>
                    <td style="padding: 12px; background: #eff6ff; border-radius: 6px; text-align: center; width: 33%;">
                        <div style="font-size: 11px; color: #64748b;">Spend</div>
                        <div style="font-size: 22px; font-weight: bold; color: #1e40af;">₹{totals.get('spend', 0):,.0f}</div>
                    </td>
                    <td style="width: 8px;"></td>
                    <td style="padding: 12px; background: #ecfdf5; border-radius: 6px; text-align: center; width: 33%;">
                        <div style="font-size: 11px; color: #64748b;">Revenue</div>
                        <div style="font-size: 22px; font-weight: bold; color: #059669;">₹{totals.get('revenue', 0):,.0f}</div>
                    </td>
                    <td style="width: 8px;"></td>
                    <td style="padding: 12px; background: #fefce8; border-radius: 6px; text-align: center; width: 33%;">
                        <div style="font-size: 11px; color: #64748b;">ROAS</div>
                        <div style="font-size: 22px; font-weight: bold; color: {roas_color};">{roas:.2f}x</div>
                    </td>
                </tr>
            </table>

            <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px 0; color: #64748b;">Purchases</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">{int(totals.get('purchases', 0))}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px 0; color: #64748b;">CPA</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">₹{metrics.get('CPA', 0):,.0f}</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px 0; color: #64748b;">CTR</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">{metrics.get('CTR', 0):.2f}%</td>
                </tr>
                <tr style="border-bottom: 1px solid #e2e8f0;">
                    <td style="padding: 8px 0; color: #64748b;">CPM</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">₹{metrics.get('CPM', 0):,.0f}</td>
                </tr>
                <tr>
                    <td style="padding: 8px 0; color: #64748b;">Overall CVR</td>
                    <td style="padding: 8px 0; text-align: right; font-weight: 600;">{metrics.get('Overall_CVR', 0):.2f}%</td>
                </tr>
            </table>
        </div>

        <div style="background: #f1f5f9; padding: 15px; border-radius: 0 0 8px 8px; border: 1px solid #e2e8f0; border-top: 0;">
            <p style="margin: 0; font-size: 12px; color: #94a3b8; text-align: center;">
                📎 Full PDF report attached • Auto-generated at {datetime.now().strftime('%I:%M %p')}
            </p>
        </div>
    </div>
    """


# ─────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────
def main():
    log.info("=" * 50)
    log.info("Daily Meta Ads Email Report — Starting")
    log.info("=" * 50)

    # Validate config
    required = ['META_ACCESS_TOKEN', 'SMTP_USER', 'SMTP_PASSWORD', 'EMAIL_TO']
    missing = [k for k in required if not CONFIG.get(k)]
    if missing:
        log.error(f"Missing required config: {', '.join(missing)}")
        log.error("Set them as environment variables or edit the CONFIG section in this script.")
        sys.exit(1)

    # Date to report on (yesterday)
    report_date = (datetime.now() - timedelta(days=1)).date()
    log.info(f"Report date: {report_date}")

    # Initialize API
    log.info("Connecting to Meta API...")
    FacebookAdsApi.init(
        app_id=CONFIG['META_APP_ID'],
        app_secret=CONFIG['META_APP_SECRET'],
        access_token=CONFIG['META_ACCESS_TOKEN']
    )

    # Get active campaigns
    log.info("Fetching active campaigns...")
    campaigns = get_active_campaigns(CONFIG['META_AD_ACCOUNT_ID'])
    if not campaigns:
        log.warning("No active campaigns found. Skipping report.")
        sys.exit(0)

    campaign_ids = [c['id'] for c in campaigns]
    campaign_names = [c['name'] for c in campaigns]
    log.info(f"Found {len(campaigns)} active campaign(s): {', '.join(campaign_names)}")

    # Fetch data
    log.info(f"Fetching performance data for {report_date}...")
    df = fetch_campaign_data(CONFIG['META_AD_ACCOUNT_ID'], campaign_ids, report_date)

    if df is None or len(df) == 0:
        log.warning("No data returned for yesterday. Campaigns may not have spent. Skipping report.")
        sys.exit(0)

    log.info(f"Got {len(df)} row(s) of data")

    # Aggregate if multiple campaigns
    if len(df['product'].unique()) > 1:
        df_combined = df.groupby('date', as_index=False).agg({
            'impressions': 'sum', 'clicks': 'sum', 'spend': 'sum',
            'reach': 'sum', 'frequency': 'mean', 'lp_views': 'sum',
            'view_content': 'sum', 'adds_to_cart': 'sum', 'checkouts': 'sum',
            'purchases': 'sum', 'revenue': 'sum', 'outbound_clicks': 'sum',
            'video_3s_views': 'sum', 'video_thruplay': 'sum', 'cpm': 'mean',
        })
        df_combined['product'] = 'All Active Campaigns'
    else:
        df_combined = df

    # Calculate metrics
    metrics = calculate_metrics(df_combined)
    log.info(f"Spend: ₹{metrics['totals']['spend']:,.0f} | Revenue: ₹{metrics['totals']['revenue']:,.0f} | ROAS: {metrics['ROAS']:.2f}x")

    # Generate PDF
    log.info("Generating PDF report...")
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
        log.error("PDF generation failed!")
        sys.exit(1)

    log.info(f"PDF generated: {len(pdf_bytes):,} bytes")

    # Build email
    email_body = build_email_body(report_date, metrics, campaign_names)
    date_str = report_date.strftime('%B_%d_%Y')
    pdf_filename = f"Meta_Ads_Report_{date_str}.pdf"
    subject = f"📊 Meta Ads Daily Report — {report_date.strftime('%b %d, %Y')} | ₹{metrics['totals']['spend']:,.0f} spent, {metrics['ROAS']:.1f}x ROAS"

    # Send email
    log.info("Sending email...")
    try:
        send_email(subject, email_body, pdf_bytes, pdf_filename)
        log.info("✅ Done! Report sent successfully.")
    except Exception as e:
        log.error(f"Failed to send email: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()


# ─────────────────────────────────────────────────────────
# GITHUB ACTIONS WORKFLOW (save as .github/workflows/daily-report.yml)
# ─────────────────────────────────────────────────────────
#
# name: Daily Meta Ads Report
#
# on:
#   schedule:
#     # Run at 12:00 AM IST (6:30 PM UTC previous day)
#     - cron: '30 18 * * *'
#   workflow_dispatch:  # Allow manual trigger
#
# jobs:
#   send-report:
#     runs-on: ubuntu-latest
#     steps:
#       - uses: actions/checkout@v4
#
#       - name: Set up Python
#         uses: actions/setup-python@v5
#         with:
#           python-version: '3.11'
#
#       - name: Install dependencies
#         run: pip install pandas facebook-business reportlab
#
#       - name: Send daily report
#         env:
#           META_ACCESS_TOKEN: ${{ secrets.META_ACCESS_TOKEN }}
#           SMTP_USER: ${{ secrets.SMTP_USER }}
#           SMTP_PASSWORD: ${{ secrets.SMTP_PASSWORD }}
#           EMAIL_TO: ${{ secrets.EMAIL_TO }}
#           EMAIL_FROM: ${{ secrets.EMAIL_FROM }}
#         run: python daily_email_report.py