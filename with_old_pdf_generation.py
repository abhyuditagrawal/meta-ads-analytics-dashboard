import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List, Tuple
from io import BytesIO
from datetime import datetime, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
from facebook_business.adobjects.adset import AdSet
from facebook_business.adobjects.ad import Ad

# Page config
st.set_page_config(
    page_title="Meta Ads Live Dashboard",
    page_icon="📊",
    layout="wide"
)

# ==================== UPDATED BENCHMARKS ====================
# Based on D2C India / children's products benchmarks
BENCHMARKS = {
    # CREATIVE PERFORMANCE
    'CTR': {'weak': 1.0, 'acceptable': 1.5, 'good': 3.0, 'excellent': 3.0, 'min': 1.0, 'ideal': 2.0, 'max': 3.0, 'unit': '%', 'higher_better': True},
    'Outbound_CTR': {'weak': 0.5, 'acceptable': 0.8, 'good': 1.5, 'excellent': 2.0, 'min': 0.5, 'ideal': 1.0, 'max': 2.0, 'unit': '%', 'higher_better': True},
    'Hook_Rate': {'weak': 20, 'acceptable': 30, 'good': 45, 'excellent': 50, 'min': 20, 'ideal': 35, 'max': 50, 'unit': '%', 'higher_better': True},
    'ThruPlay_Rate': {'weak': 8, 'acceptable': 15, 'good': 25, 'excellent': 25, 'min': 8, 'ideal': 15, 'max': 25, 'unit': '%', 'higher_better': True},

    # REACH & DISTRIBUTION
    'CPM': {'weak': 300, 'acceptable': 200, 'good': 100, 'excellent': 100, 'min': 200, 'ideal': 150, 'max': 100, 'unit': '₹', 'higher_better': False},
    'Frequency': {'weak': 6, 'acceptable': 3.5, 'good': 1.8, 'excellent': 1.8, 'min': 3.5, 'ideal': 2.5, 'max': 1.8, 'unit': 'x', 'higher_better': False},
    'CPC': {'weak': 40, 'acceptable': 20, 'good': 10, 'excellent': 10, 'min': 20, 'ideal': 12, 'max': 10, 'unit': '₹', 'higher_better': False},

    # FUNNEL CONVERSION
    'LP_View_Rate': {'weak': 50, 'acceptable': 65, 'good': 80, 'excellent': 80, 'min': 50, 'ideal': 70, 'max': 80, 'unit': '%', 'higher_better': True},
    'View_Content_Rate': {'weak': 40, 'acceptable': 55, 'good': 70, 'excellent': 70, 'min': 40, 'ideal': 55, 'max': 70, 'unit': '%', 'higher_better': True},
    'ATC_Rate': {'weak': 10, 'acceptable': 20, 'good': 35, 'excellent': 35, 'min': 10, 'ideal': 20, 'max': 35, 'unit': '%', 'higher_better': True},
    'Checkout_Rate': {'weak': 40, 'acceptable': 55, 'good': 70, 'excellent': 70, 'min': 40, 'ideal': 55, 'max': 70, 'unit': '%', 'higher_better': True},
    'Purchase_Rate': {'weak': 40, 'acceptable': 55, 'good': 70, 'excellent': 70, 'min': 40, 'ideal': 55, 'max': 70, 'unit': '%', 'higher_better': True},
    'Overall_CVR': {'weak': 1, 'acceptable': 2, 'good': 4, 'excellent': 4, 'min': 1, 'ideal': 3, 'max': 4, 'unit': '%', 'higher_better': True},

    # COST METRICS
    'CPA': {'weak': 600, 'acceptable': 400, 'good': 200, 'excellent': 200, 'min': 400, 'ideal': 300, 'max': 200, 'unit': '₹', 'higher_better': False},
    'Cost_per_ATC': {'weak': 300, 'acceptable': 150, 'good': 75, 'excellent': 75, 'min': 150, 'ideal': 100, 'max': 75, 'unit': '₹', 'higher_better': False},
    'Cost_per_Checkout': {'weak': 500, 'acceptable': 300, 'good': 150, 'excellent': 150, 'min': 300, 'ideal': 200, 'max': 150, 'unit': '₹', 'higher_better': False},

    # REVENUE & EFFICIENCY
    'ROAS': {'weak': 2, 'acceptable': 3, 'good': 5, 'excellent': 5, 'min': 2, 'ideal': 4, 'max': 5, 'unit': 'x', 'higher_better': True},
    'ACoS': {'weak': 50, 'acceptable': 33, 'good': 20, 'excellent': 20, 'min': 33, 'ideal': 25, 'max': 20, 'unit': '%', 'higher_better': False},
    'AOV': {'weak': 400, 'acceptable': 600, 'good': 900, 'excellent': 900, 'min': 400, 'ideal': 600, 'max': 900, 'unit': '₹', 'higher_better': True},
    'MER': {'weak': 1.5, 'acceptable': 2.5, 'good': 4, 'excellent': 4, 'min': 1.5, 'ideal': 2.5, 'max': 4, 'unit': 'x', 'higher_better': True},
}

# Default AOV for fallback revenue calculation
DEFAULT_AOV = 600  # ₹600 per order

# Initialize session state
if 'api_initialized' not in st.session_state:
    st.session_state.api_initialized = False
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False
if 'analysis_mode' not in st.session_state:
    st.session_state.analysis_mode = 'Campaign Mode'


def initialize_api(app_id, app_secret, access_token):
    """Initialize Facebook Ads API"""
    try:
        FacebookAdsApi.init(
            app_id=app_id,
            app_secret=app_secret,
            access_token=access_token
        )
        return True, "API Initialized Successfully!"
    except Exception as e:
        return False, f"Error: {str(e)}"


def get_campaigns(ad_account_id):
    """Fetch all campaigns from ad account"""
    try:
        ad_account = AdAccount(ad_account_id)
        campaigns = ad_account.get_campaigns(
            fields=['name', 'id', 'status', 'objective']
        )

        campaign_list = []
        for campaign in campaigns:
            campaign_list.append({
                'id': campaign.get('id'),
                'name': campaign.get('name'),
                'status': campaign.get('status'),
                'objective': campaign.get('objective')
            })

        return campaign_list, None
    except Exception as e:
        return None, str(e)


def get_adsets(ad_account_id, campaign_ids=None):
    """Fetch ad sets from ad account, optionally filtered by campaign IDs"""
    try:
        ad_account = AdAccount(ad_account_id)

        params = {}
        if campaign_ids:
            params['filtering'] = [{'field': 'campaign.id', 'operator': 'IN', 'value': campaign_ids}]

        adsets = ad_account.get_ad_sets(
            fields=['name', 'id', 'status', 'campaign_id'],
            params=params
        )

        adset_list = []
        for adset in adsets:
            adset_list.append({
                'id': adset.get('id'),
                'name': adset.get('name'),
                'status': adset.get('status'),
                'campaign_id': adset.get('campaign_id'),
                'campaign_name': adset.get('campaign_name', 'Unknown')
            })

        return adset_list, None
    except Exception as e:
        return None, str(e)


def get_ads(ad_account_id, adset_ids=None):
    """Fetch ads from ad account, optionally filtered by ad set IDs"""
    try:
        ad_account = AdAccount(ad_account_id)

        params = {}
        if adset_ids:
            params['filtering'] = [{'field': 'adset.id', 'operator': 'IN', 'value': adset_ids}]

        ads = ad_account.get_ads(
            fields=['name', 'id', 'status', 'adset_id', 'adset_name', 'campaign_id'],
            params=params
        )

        ad_list = []
        for ad in ads:
            ad_list.append({
                'id': ad.get('id'),
                'name': ad.get('name'),
                'status': ad.get('status'),
                'adset_id': ad.get('adset_id'),
                'adset_name': ad.get('adset_name', 'Unknown'),
                'campaign_id': ad.get('campaign_id'),
                'campaign_name': 'Unknown'
            })

        return ad_list, None
    except Exception as e:
        return None, str(e)


def fetch_data(ad_account_id, entity_ids, level='campaign', date_preset='last_30d', start_date=None, end_date=None):
    """Fetch performance data for selected entities at specified level (campaign/adset/ad)"""
    try:
        ad_account = AdAccount(ad_account_id)

        fields = [
            'campaign_id',
            'campaign_name',
            'date_start',
            'impressions',
            'clicks',
            'spend',
            'reach',
            'frequency',
            'cpc',
            'cpm',
            'ctr',
            'outbound_clicks',
            'actions',
            'action_values',
            'cost_per_action_type',
            'video_thruplay_watched_actions',
        ]

        # Add level-specific fields
        if level == 'adset':
            fields.extend(['adset_id', 'adset_name'])
        elif level == 'ad':
            fields.extend(['adset_id', 'adset_name', 'ad_id', 'ad_name'])

        # Build filtering based on level
        filter_field = {
            'campaign': 'campaign.id',
            'adset': 'adset.id',
            'ad': 'ad.id'
        }

        params = {
            'level': level,
            'time_increment': 1,
            'filtering': [{'field': filter_field[level], 'operator': 'IN', 'value': entity_ids}],
        }

        if start_date and end_date:
            params['time_range'] = {
                'since': start_date.strftime('%Y-%m-%d'),
                'until': end_date.strftime('%Y-%m-%d')
            }
        else:
            params['date_preset'] = date_preset

        insights = ad_account.get_insights(fields=fields, params=params)

        data_list = []
        for insight in insights:
            row = {
                'date': pd.to_datetime(insight.get('date_start')),
                'campaign_name': insight.get('campaign_name', 'Unknown'),
                'impressions': int(insight.get('impressions', 0)),
                'clicks': int(insight.get('clicks', 0)),
                'spend': float(insight.get('spend', 0)),
                'reach': int(insight.get('reach', 0)),
                'frequency': float(insight.get('frequency', 0)),
                'cpc': float(insight.get('cpc', 0)),
                'cpm': float(insight.get('cpm', 0)),
                'ctr': float(insight.get('ctr', 0)),
                'lp_views': 0,
                'view_content': 0,
                'adds_to_cart': 0,
                'checkouts': 0,
                'purchases': 0,
                'revenue': 0,
                'outbound_clicks': 0,
                'video_3s_views': 0,
                'video_thruplay': 0,
            }

            # Extract outbound clicks
            outbound_clicks = insight.get('outbound_clicks') or []
            if outbound_clicks:
                for oc in outbound_clicks:
                    if oc.get('action_type') == 'outbound_click':
                        row['outbound_clicks'] = int(oc.get('value', 0))
                        break

            # Extract video metrics
            video_thruplay = insight.get('video_thruplay_watched_actions') or []
            if video_thruplay:
                for vt in video_thruplay:
                    row['video_thruplay'] = int(vt.get('value', 0))
                    break

            # Add entity name based on level
            if level == 'campaign':
                row['entity_name'] = insight.get('campaign_name')
            elif level == 'adset':
                row['entity_name'] = insight.get('adset_name', 'Unknown')
                row['adset_name'] = insight.get('adset_name', 'Unknown')
            elif level == 'ad':
                row['entity_name'] = insight.get('ad_name', 'Unknown')
                row['ad_name'] = insight.get('ad_name', 'Unknown')
                row['adset_name'] = insight.get('adset_name', 'Unknown')

            # Extract actions
            actions = insight.get('actions', []) or []
            for action in actions:
                action_type = action.get('action_type', '')
                if not action_type:
                    continue
                value = int(action.get('value', 0))

                if 'landing_page_view' in action_type:
                    row['lp_views'] = value
                elif action_type == 'view_content' or action_type == 'offsite_conversion.fb_pixel_view_content':
                    row['view_content'] = value
                elif 'add_to_cart' in action_type or action_type == 'offsite_conversion.fb_pixel_add_to_cart':
                    row['adds_to_cart'] = value
                elif 'initiate_checkout' in action_type or action_type == 'offsite_conversion.fb_pixel_initiate_checkout':
                    row['checkouts'] = value
                elif 'purchase' in action_type or action_type == 'offsite_conversion.fb_pixel_purchase':
                    row['purchases'] = value
                elif action_type == 'video_view':
                    row['video_3s_views'] = value

            # Try to get actual revenue from action_values
            action_values = insight.get('action_values', []) or []
            revenue_found = False
            for action_value in action_values:
                action_type = action_value.get('action_type', '')
                if not action_type:
                    continue
                if 'purchase' in action_type or action_type == 'offsite_conversion.fb_pixel_purchase':
                    row['revenue'] = float(action_value.get('value', 0))
                    revenue_found = True
                    break

            # Fallback to AOV calculation if no revenue found
            if not revenue_found and row['purchases'] > 0:
                row['revenue'] = row['purchases'] * DEFAULT_AOV

            data_list.append(row)

        if data_list:
            df = pd.DataFrame(data_list)
            df['product'] = df['entity_name']
            return df, None
        else:
            return None, f"No data found for selected {level}s and date range"

    except Exception as e:
        return None, str(e)


def calculate_metrics(df: pd.DataFrame) -> Dict:
    """Calculate all marketing metrics including new creative, cost, and revenue metrics"""
    totals = df.sum(numeric_only=True)

    def pct(a, b):
        return (a / b * 100) if b > 0 else 0

    def safe_div(a, b):
        return (a / b) if b > 0 else 0

    # Core rates
    roas = safe_div(totals.revenue, totals.spend)
    acos = pct(totals.spend, totals.revenue)
    aov = safe_div(totals.revenue, totals.purchases)

    metrics = {
        # Creative Performance
        'CTR': pct(totals.clicks, totals.impressions),
        'Outbound_CTR': pct(totals.outbound_clicks, totals.impressions),
        'Hook_Rate': pct(totals.video_3s_views, totals.impressions),
        'ThruPlay_Rate': pct(totals.video_thruplay, totals.impressions),

        # Reach & Distribution
        'CPM': safe_div(totals.spend, totals.impressions) * 1000,
        'Frequency': totals.frequency / len(df) if len(df) > 0 else 0,
        'CPC': safe_div(totals.spend, totals.clicks),

        # Funnel Conversion
        'LP_View_Rate': pct(totals.lp_views, totals.clicks),
        'View_Content_Rate': pct(totals.view_content, totals.lp_views),
        'ATC_Rate': pct(totals.adds_to_cart, totals.lp_views),
        'Checkout_Rate': pct(totals.checkouts, totals.adds_to_cart),
        'Purchase_Rate': pct(totals.purchases, totals.checkouts),
        'Overall_CVR': pct(totals.purchases, totals.clicks),

        # Cost Metrics
        'CPA': safe_div(totals.spend, totals.purchases),
        'Cost_per_ATC': safe_div(totals.spend, totals.adds_to_cart),
        'Cost_per_Checkout': safe_div(totals.spend, totals.checkouts),

        # Revenue & Efficiency
        'ROAS': roas,
        'ACoS': acos,
        'AOV': aov,
        'MER': roas,  # MER = total revenue / total spend (same as ROAS at single entity level; meaningful at account level)

        'totals': {
            'impressions': totals.impressions,
            'clicks': totals.clicks,
            'outbound_clicks': totals.outbound_clicks,
            'video_3s_views': totals.video_3s_views,
            'video_thruplay': totals.video_thruplay,
            'lp_views': totals.lp_views,
            'view_content': totals.view_content,
            'adds_to_cart': totals.adds_to_cart,
            'checkouts': totals.checkouts,
            'purchases': totals.purchases,
            'spend': totals.spend,
            'revenue': totals.revenue,
            'reach': totals.reach,
        }
    }

    return metrics


def calculate_daily_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """Calculate metrics for each day"""
    daily = df.copy()

    def safe_pct(a, b):
        return (a / b * 100).fillna(0).replace([float('inf'), float('-inf')], 0)

    def safe_div(a, b):
        return (a / b).fillna(0).replace([float('inf'), float('-inf')], 0)

    # Creative Performance
    daily['CTR'] = safe_pct(daily['clicks'], daily['impressions'])
    daily['Outbound_CTR'] = safe_pct(daily['outbound_clicks'], daily['impressions'])
    daily['Hook_Rate'] = safe_pct(daily['video_3s_views'], daily['impressions'])
    daily['ThruPlay_Rate'] = safe_pct(daily['video_thruplay'], daily['impressions'])

    # Reach & Distribution
    daily['CPM'] = safe_div(daily['spend'], daily['impressions']) * 1000
    daily['CPC'] = safe_div(daily['spend'], daily['clicks'])

    # Funnel Conversion
    daily['LP_View_Rate'] = safe_pct(daily['lp_views'], daily['clicks'])
    daily['View_Content_Rate'] = safe_pct(daily['view_content'], daily['lp_views'])
    daily['ATC_Rate'] = safe_pct(daily['adds_to_cart'], daily['lp_views'])
    daily['Checkout_Rate'] = safe_pct(daily['checkouts'], daily['adds_to_cart'])
    daily['Purchase_Rate'] = safe_pct(daily['purchases'], daily['checkouts'])
    daily['Overall_CVR'] = safe_pct(daily['purchases'], daily['clicks'])

    # Cost Metrics
    daily['CPA'] = safe_div(daily['spend'], daily['purchases'])
    daily['Cost_per_ATC'] = safe_div(daily['spend'], daily['adds_to_cart'])
    daily['Cost_per_Checkout'] = safe_div(daily['spend'], daily['checkouts'])

    # Revenue & Efficiency
    daily['ROAS'] = safe_div(daily['revenue'], daily['spend'])
    daily['ACoS'] = safe_pct(daily['spend'], daily['revenue'])
    daily['AOV'] = safe_div(daily['revenue'], daily['purchases'])
    daily['MER'] = safe_div(daily['revenue'], daily['spend'])

    # Rename raw frequency to capitalized Frequency for display consistency
    if 'frequency' in daily.columns:
        daily['Frequency'] = daily['frequency']

    return daily


def get_status_emoji(metric_name: str, value: float) -> str:
    """Get emoji based on benchmark tiers"""
    if metric_name not in BENCHMARKS:
        return '⚪'

    bench = BENCHMARKS[metric_name]
    higher_better = bench.get('higher_better', True)

    if higher_better:
        if value >= bench['good']:
            return '✅'
        elif value >= bench['acceptable']:
            return '⚠️'
        else:
            return '🚨'
    else:
        # Lower is better (CPC, CPM, CPA, ACoS, Frequency, Cost_per_ATC, Cost_per_Checkout)
        if value <= bench['good']:
            return '✅'
        elif value <= bench['acceptable']:
            return '⚠️'
        else:
            return '🚨'


def get_status_label(metric_name: str, value: float) -> str:
    """Get text label: Excellent/Good/Acceptable/Weak"""
    if metric_name not in BENCHMARKS:
        return 'N/A'

    bench = BENCHMARKS[metric_name]
    higher_better = bench.get('higher_better', True)

    if higher_better:
        if value >= bench['excellent']:
            return 'Excellent'
        elif value >= bench['good']:
            return 'Good'
        elif value >= bench['acceptable']:
            return 'Acceptable'
        else:
            return 'Weak'
    else:
        if value <= bench['excellent']:
            return 'Excellent'
        elif value <= bench['good']:
            return 'Good'
        elif value <= bench['acceptable']:
            return 'Acceptable'
        else:
            return 'Weak'


def create_funnel_chart(metrics: Dict) -> go.Figure:
    """Create funnel visualization with new stages"""
    totals = metrics['totals']

    stages = [
        ('Impressions', totals['impressions']),
        ('Link Clicks', totals['clicks']),
        ('Outbound Clicks', totals['outbound_clicks']),
        ('LP Views', totals['lp_views']),
        ('View Content', totals['view_content']),
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
            color=['#1e3a8a', '#2563eb', '#3b82f6', '#60a5fa', '#93c5fd', '#bfdbfe', '#dbeafe', '#eff6ff']
        )
    ))

    fig.update_layout(
        height=550,
        margin=dict(l=20, r=20, t=40, b=20),
        title="Conversion Funnel"
    )

    return fig


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

    higher_better = bench.get('higher_better', True)

    if higher_better:
        if actual >= bench['good']:
            color = '#10b981'
        elif actual >= bench['acceptable']:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        gauge_max = bench['max'] * 1.5
    else:
        if actual <= bench['good']:
            color = '#10b981'
        elif actual <= bench['acceptable']:
            color = '#f59e0b'
        else:
            color = '#ef4444'
        gauge_max = bench['weak'] * 1.5

    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=actual,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': metric.replace('_', ' ')},
        delta={'reference': bench['ideal'], 'increasing': {'color': "green" if higher_better else "red"}},
        gauge={
            'axis': {'range': [0, gauge_max]},
            'bar': {'color': color},
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': bench['ideal']
            }
        }
    ))

    fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))

    return fig


def get_recommendations(metrics: Dict) -> List[Dict]:
    """Generate recommendations based on metrics"""
    issues = []

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
                'Use emotional hooks for children\'s product visuals',
            ]
        })

    if metrics['Hook_Rate'] > 0 and metrics['Hook_Rate'] < BENCHMARKS['Hook_Rate']['min']:
        issues.append({
            'priority': 'HIGH',
            'metric': 'Hook Rate (3-sec video views)',
            'current': metrics['Hook_Rate'],
            'target': BENCHMARKS['Hook_Rate']['ideal'],
            'recommendations': [
                'Redesign first 3 seconds of video — lead with action or surprise',
                'Use text overlays in opening frames',
                'Test different thumbnail/opening frames',
                'Front-load the most compelling visual element',
                'Use native-looking content instead of polished ads',
            ]
        })

    if metrics['ThruPlay_Rate'] > 0 and metrics['ThruPlay_Rate'] < BENCHMARKS['ThruPlay_Rate']['min']:
        issues.append({
            'priority': 'MEDIUM',
            'metric': 'ThruPlay Rate (Video completion)',
            'current': metrics['ThruPlay_Rate'],
            'target': BENCHMARKS['ThruPlay_Rate']['ideal'],
            'recommendations': [
                'Shorten video length — aim for 15-30 seconds',
                'Add captions/subtitles for sound-off viewing',
                'Improve storytelling arc to maintain engagement',
                'Use pattern interrupts throughout the video',
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
                'Ensure landing page matches ad promise',
            ]
        })

    if metrics['ATC_Rate'] < BENCHMARKS['ATC_Rate']['min']:
        issues.append({
            'priority': 'HIGH',
            'metric': 'Add to Cart Rate',
            'current': metrics['ATC_Rate'],
            'target': BENCHMARKS['ATC_Rate']['ideal'],
            'recommendations': [
                'Improve product page design and imagery',
                'Add social proof (reviews, ratings)',
                'Ensure pricing is clear and competitive',
                'Simplify the add-to-cart experience',
                'Add urgency elements (limited stock, timer)',
            ]
        })

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
            ]
        })

    if metrics['ROAS'] < BENCHMARKS['ROAS']['min']:
        issues.append({
            'priority': 'CRITICAL',
            'metric': 'ROAS (Return on Ad Spend)',
            'current': metrics['ROAS'],
            'target': BENCHMARKS['ROAS']['ideal'],
            'recommendations': [
                'Increase product prices or average order value',
                'Improve conversion rate throughout funnel',
                'Reduce ad spend on underperforming campaigns',
                'Focus on high-value customer segments',
                'Optimize product mix for profitability',
            ]
        })

    if metrics['ACoS'] > BENCHMARKS['ACoS']['min']:
        issues.append({
            'priority': 'HIGH',
            'metric': 'ACoS (Advertising Cost of Sales)',
            'current': metrics['ACoS'],
            'target': BENCHMARKS['ACoS']['ideal'],
            'recommendations': [
                'Reduce cost per click through better targeting',
                'Improve conversion rate to lower CPA',
                'Pause underperforming ad sets',
                'Focus on audiences with lower CPAs',
                'Optimize bidding strategy',
            ]
        })

    if metrics['CPM'] > BENCHMARKS['CPM']['min']:
        issues.append({
            'priority': 'MEDIUM',
            'metric': 'CPM (Cost per 1000 Impressions)',
            'current': metrics['CPM'],
            'target': BENCHMARKS['CPM']['ideal'],
            'recommendations': [
                'Broaden audience targeting to reduce competition',
                'Test different placements (Reels, Stories)',
                'Improve ad quality score with better engagement',
                'Avoid over-segmented audiences',
                'Test lookalike audiences at different percentages',
            ]
        })

    if metrics['Cost_per_ATC'] > BENCHMARKS['Cost_per_ATC']['min']:
        issues.append({
            'priority': 'MEDIUM',
            'metric': 'Cost per Add to Cart',
            'current': metrics['Cost_per_ATC'],
            'target': BENCHMARKS['Cost_per_ATC']['ideal'],
            'recommendations': [
                'Improve landing page relevance to ad creative',
                'Target warmer audiences (retargeting, lookalikes)',
                'Optimize product page for conversions',
                'Test different offers and incentives',
            ]
        })

    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
    issues.sort(key=lambda x: priority_order[x['priority']])

    return issues


def fetch_all_child_data(ad_account_id, selected_campaign_ids, date_preset, start_date, end_date) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Fetch data for all active ad sets and ads under selected campaigns"""

    adsets, error = get_adsets(ad_account_id, selected_campaign_ids)
    active_adsets = [a for a in adsets if a['status'] == 'ACTIVE'] if adsets else []

    adset_data = None
    ad_data = None

    if active_adsets:
        adset_ids = [a['id'] for a in active_adsets]

        adset_data, _ = fetch_data(
            ad_account_id,
            adset_ids,
            level='adset',
            date_preset=date_preset,
            start_date=start_date,
            end_date=end_date
        )

        ads, error = get_ads(ad_account_id, adset_ids)
        active_ads = [a for a in ads if a['status'] == 'ACTIVE'] if ads else []

        if active_ads:
            ad_ids = [a['id'] for a in active_ads]

            ad_data, _ = fetch_data(
                ad_account_id,
                ad_ids,
                level='ad',
                date_preset=date_preset,
                start_date=start_date,
                end_date=end_date
            )

    return adset_data, ad_data


def generate_pdf_report(product_name: str, df: pd.DataFrame, metrics: Dict, mode: str,
                        ad_account_id: str = None, selected_campaign_ids: List[str] = None,
                        date_preset: str = None, start_date=None, end_date=None) -> bytes:
    """Generate a comprehensive PDF report with ALL dashboard data including new metrics"""
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter, landscape
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak, Image
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib.enums import TA_CENTER
        import plotly.io as pio

        buffer = BytesIO()
        doc = SimpleDocTemplate(buffer, pagesize=landscape(letter), topMargin=0.4*inch, bottomMargin=0.4*inch,
                                leftMargin=0.4*inch, rightMargin=0.4*inch)
        story = []
        styles = getSampleStyleSheet()

        title_style = ParagraphStyle(
            'CustomTitle', parent=styles['Heading1'], fontSize=24,
            textColor=colors.HexColor('#1f2937'), spaceAfter=30,
            alignment=TA_CENTER, fontName='Helvetica-Bold'
        )
        heading_style = ParagraphStyle(
            'CustomHeading', parent=styles['Heading2'], fontSize=16,
            textColor=colors.HexColor('#3b82f6'), spaceAfter=12, spaceBefore=12,
            fontName='Helvetica-Bold'
        )
        subheading_style = ParagraphStyle(
            'CustomSubHeading', parent=styles['Heading3'], fontSize=12,
            textColor=colors.HexColor('#6b7280'), spaceAfter=8, fontName='Helvetica-Bold'
        )

        mode_emoji_map = {'Campaign Mode': '📊', 'Ad Set Mode': '🎯', 'Ad Mode': '🎨'}
        story.append(Paragraph(f"{mode_emoji_map.get(mode, '📊')} Meta Ads Comprehensive Report", title_style))
        story.append(Paragraph(f"Primary Entity: {product_name}", heading_style))
        story.append(Paragraph(f"Generated: {datetime.now().strftime('%B %d, %Y at %I:%M %p')}", styles['Normal']))
        story.append(Spacer(1, 0.3*inch))

        # ===== Executive Summary =====
        story.append(Paragraph("Executive Summary", heading_style))
        num_days = len(df['date'].unique())
        summary_data = [
            ['Metric', 'Value'],
            ['Total Spend', f"₹{metrics['totals']['spend']:,.0f}"],
            ['Total Revenue', f"₹{metrics['totals']['revenue']:,.0f}"],
            ['Total Purchases', f"{int(metrics['totals']['purchases'])}"],
            ['ROAS', f"{metrics['ROAS']:.2f}x"],
            ['ACoS', f"{metrics['ACoS']:.2f}%"],
            ['AOV', f"₹{metrics['AOV']:.0f}"],
            ['MER', f"{metrics['MER']:.2f}x"],
            ['CPA', f"₹{metrics['CPA']:.2f}"],
            ['CPM', f"₹{metrics['CPM']:.2f}"],
            ['Overall CVR', f"{metrics['Overall_CVR']:.2f}%"],
            ['Days Analyzed', f"{num_days}"]
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
        story.append(PageBreak())

        # ===== All Metrics with Benchmarks =====
        story.append(Paragraph("Complete Performance vs Benchmarks", heading_style))

        all_metric_names = [
            'CTR', 'Outbound_CTR', 'Hook_Rate', 'ThruPlay_Rate',
            'CPM', 'Frequency', 'CPC',
            'LP_View_Rate', 'View_Content_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR',
            'CPA', 'Cost_per_ATC', 'Cost_per_Checkout',
            'ROAS', 'ACoS', 'AOV', 'MER'
        ]

        comparison_data = [['Metric', 'Your Value', 'Ideal', 'Min Acceptable', 'Gap', 'Rating', 'Status']]
        for metric_name in all_metric_names:
            if metric_name not in metrics or metric_name not in BENCHMARKS:
                continue
            actual_val = metrics[metric_name]
            bench = BENCHMARKS[metric_name]
            gap = actual_val - bench['ideal']
            status = get_status_emoji(metric_name, actual_val)
            rating = get_status_label(metric_name, actual_val)

            comparison_data.append([
                metric_name.replace('_', ' '),
                f"{actual_val:.2f}{bench['unit']}",
                f"{bench['ideal']:.2f}{bench['unit']}",
                f"{bench['min']:.2f}{bench['unit']}",
                f"{gap:+.2f}{bench['unit']}",
                rating,
                status
            ])

        comparison_table = Table(comparison_data, colWidths=[1.5*inch, 1.1*inch, 1.0*inch, 1.1*inch, 0.8*inch, 0.8*inch, 0.5*inch])
        comparison_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#10b981')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 9),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 10),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 8),
            ('TOPPADDING', (0, 1), (-1, -1), 6),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
        ]))
        story.append(comparison_table)
        story.append(PageBreak())

        # ===== Funnel Chart =====
        story.append(Paragraph("Conversion Funnel Visualization", heading_style))
        funnel_fig = create_funnel_chart(metrics)
        img_bytes = pio.to_image(funnel_fig, format='png', width=900, height=550)
        img_buffer = BytesIO(img_bytes)
        img = Image(img_buffer, width=8*inch, height=4.5*inch)
        story.append(img)
        story.append(PageBreak())

        # ===== Daily Trends Chart =====
        story.append(Paragraph("Daily Performance Trends", heading_style))
        fig_conversions = px.line(
            df, x="date",
            y=["clicks", "outbound_clicks", "lp_views", "view_content", "adds_to_cart", "checkouts", "purchases"],
            title="Daily Conversions Trend",
            labels={"value": "Count", "variable": "Metric", "date": "Date"}
        )
        fig_conversions.update_layout(width=900, height=450, showlegend=True)
        conv_img_bytes = pio.to_image(fig_conversions, format='png', width=900, height=450)
        conv_img_buffer = BytesIO(conv_img_bytes)
        conv_img = Image(conv_img_buffer, width=8*inch, height=3.5*inch)
        story.append(conv_img)
        story.append(PageBreak())

        # ===== Day-wise Performance Table =====
        story.append(Paragraph("Day-wise Performance Breakdown", heading_style))

        daily_metrics = calculate_daily_metrics(df)
        daily_data = [['Date', 'CTR%', 'OutCTR%', 'Hook%', 'Thru%', 'CPM', 'CPC', 'LP%', 'VC%', 'ATC%', 'Chk%', 'Pur%', 'CVR%', 'ROAS', 'ACoS%', 'AOV', 'CPA']]

        for _, row in daily_metrics.iterrows():
            daily_data.append([
                row['date'].strftime('%m/%d'),
                f"{row['CTR']:.1f}",
                f"{row['Outbound_CTR']:.1f}",
                f"{row['Hook_Rate']:.1f}",
                f"{row['ThruPlay_Rate']:.1f}",
                f"{row['CPM']:.0f}",
                f"{row['CPC']:.1f}",
                f"{row['LP_View_Rate']:.1f}",
                f"{row['View_Content_Rate']:.1f}",
                f"{row['ATC_Rate']:.1f}",
                f"{row['Checkout_Rate']:.1f}",
                f"{row['Purchase_Rate']:.1f}",
                f"{row['Overall_CVR']:.1f}",
                f"{row['ROAS']:.2f}",
                f"{row['ACoS']:.1f}",
                f"{row['AOV']:.0f}",
                f"{row['CPA']:.0f}"
            ])

        col_w = 0.58 * inch
        daily_table = Table(daily_data, colWidths=[0.55*inch] + [col_w]*16)
        daily_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#3b82f6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightgrey),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.black),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 5.5),
            ('TOPPADDING', (0, 1), (-1, -1), 4),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 4),
        ]))
        story.append(daily_table)
        story.append(PageBreak())

        # ===== Performance vs Benchmarks Charts =====
        story.append(Paragraph("Performance vs Benchmarks - Charts", heading_style))

        chart_metrics = ['CTR', 'Hook_Rate', 'ATC_Rate', 'Checkout_Rate', 'Overall_CVR', 'ROAS', 'CPM', 'CPC']
        for cm in chart_metrics:
            chart = create_actual_vs_ideal_chart(df, cm)
            if chart:
                chart_img = pio.to_image(chart, format='png', width=900, height=400)
                chart_img_buffer = BytesIO(chart_img)
                story.append(Image(chart_img_buffer, width=8*inch, height=3.2*inch))
                story.append(Spacer(1, 0.15*inch))

        story.append(PageBreak())

        # ===== Raw Data Table =====
        story.append(Paragraph("Raw Data - Main Entity", subheading_style))
        raw_cols = ['date', 'product', 'impressions', 'clicks', 'outbound_clicks', 'spend', 'cpm',
                    'video_3s_views', 'video_thruplay', 'lp_views', 'view_content',
                    'adds_to_cart', 'checkouts', 'purchases', 'revenue']
        raw_display = df[raw_cols].copy()
        raw_display['date'] = pd.to_datetime(raw_display['date']).dt.strftime('%Y-%m-%d')

        raw_data = [['Date', 'Entity', 'Impr', 'Clk', 'OutClk', 'Spend', 'CPM', '3sV', 'Thru', 'LP', 'VC', 'ATC', 'Chk', 'Pur', 'Rev']]
        for _, row in raw_display.head(60).iterrows():
            raw_data.append([
                row['date'],
                str(row['product'])[:15] + '...' if len(str(row['product'])) > 15 else row['product'],
                f"{int(row['impressions'])}",
                f"{int(row['clicks'])}",
                f"{int(row['outbound_clicks'])}",
                f"{row['spend']:.0f}",
                f"{row['cpm']:.0f}",
                f"{int(row['video_3s_views'])}",
                f"{int(row['video_thruplay'])}",
                f"{int(row['lp_views'])}",
                f"{int(row['view_content'])}",
                f"{int(row['adds_to_cart'])}",
                f"{int(row['checkouts'])}",
                f"{int(row['purchases'])}",
                f"{row['revenue']:.0f}"
            ])

        cw = 0.65 * inch
        raw_table = Table(raw_data, colWidths=[0.6*inch, 1.0*inch] + [cw]*13)
        raw_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 6),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
            ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
            ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 1), (-1, -1), 5.5),
            ('TOPPADDING', (0, 1), (-1, -1), 3),
            ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
        ]))
        story.append(raw_table)
        story.append(Paragraph(f"Total rows: {len(raw_display)}", styles['Normal']))
        story.append(PageBreak())

        # ===== Child Entities (Campaign Mode) =====
        if mode == 'Campaign Mode' and ad_account_id and selected_campaign_ids:
            adset_data, ad_data = fetch_all_child_data(ad_account_id, selected_campaign_ids, date_preset, start_date, end_date)

            if adset_data is not None and len(adset_data) > 0:
                story.append(Paragraph("Active Ad Sets Analysis", heading_style))
                unique_adsets = adset_data['product'].unique()
                story.append(Paragraph(f"Found {len(unique_adsets)} active ad set(s)", subheading_style))
                story.append(Spacer(1, 0.1*inch))

                for adset_name in unique_adsets[:10]:
                    adset_df = adset_data[adset_data['product'] == adset_name]
                    adset_metrics = calculate_metrics(adset_df)

                    adset_summary = [
                        ['Metric', 'Value'],
                        ['Ad Set', str(adset_name)[:40]],
                        ['Spend', f"₹{adset_metrics['totals']['spend']:,.0f}"],
                        ['Revenue', f"₹{adset_metrics['totals']['revenue']:,.0f}"],
                        ['ROAS', f"{adset_metrics['ROAS']:.2f}x"],
                        ['ACoS', f"{adset_metrics['ACoS']:.2f}%"],
                        ['AOV', f"₹{adset_metrics['AOV']:.0f}"],
                        ['CPM', f"₹{adset_metrics['CPM']:.2f}"],
                        ['Hook Rate', f"{adset_metrics['Hook_Rate']:.2f}%"],
                        ['Cost/ATC', f"₹{adset_metrics['Cost_per_ATC']:.0f}"],
                        ['Cost/Purchase', f"₹{adset_metrics['CPA']:.0f}"],
                    ]

                    adset_table = Table(adset_summary, colWidths=[2*inch, 3*inch])
                    adset_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 10),
                        ('GRID', (0, 0), (-1, -1), 1, colors.black),
                        ('FONTSIZE', (0, 1), (-1, -1), 9),
                    ]))
                    story.append(adset_table)
                    story.append(Spacer(1, 0.15*inch))

                story.append(PageBreak())

                # Raw data for ad sets
                story.append(Paragraph("Raw Data - All Active Ad Sets", subheading_style))
                adset_raw = adset_data[raw_cols].copy()
                adset_raw['date'] = pd.to_datetime(adset_raw['date']).dt.strftime('%Y-%m-%d')

                adset_raw_data = [['Date', 'Ad Set', 'Impr', 'Clk', 'OutClk', 'Spend', 'CPM', '3sV', 'Thru', 'LP', 'VC', 'ATC', 'Chk', 'Pur', 'Rev']]
                for _, row in adset_raw.iterrows():
                    adset_raw_data.append([
                        row['date'],
                        str(row['product'])[:15] + '...' if len(str(row['product'])) > 15 else row['product'],
                        f"{int(row['impressions'])}", f"{int(row['clicks'])}", f"{int(row['outbound_clicks'])}",
                        f"{row['spend']:.0f}", f"{row['cpm']:.0f}",
                        f"{int(row['video_3s_views'])}", f"{int(row['video_thruplay'])}",
                        f"{int(row['lp_views'])}", f"{int(row['view_content'])}",
                        f"{int(row['adds_to_cart'])}", f"{int(row['checkouts'])}",
                        f"{int(row['purchases'])}", f"{row['revenue']:.0f}"
                    ])

                adset_raw_table = Table(adset_raw_data, colWidths=[0.6*inch, 1.0*inch] + [cw]*13)
                adset_raw_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#8b5cf6')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 6),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.lavender),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 5.5),
                    ('TOPPADDING', (0, 1), (-1, -1), 3),
                    ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                ]))
                story.append(adset_raw_table)
                story.append(Paragraph(f"Total rows: {len(adset_raw)}", styles['Normal']))
                story.append(PageBreak())

                # Active Ads
                if ad_data is not None and len(ad_data) > 0:
                    story.append(Paragraph("Active Ads Analysis", heading_style))
                    unique_ads = ad_data['product'].unique()
                    story.append(Paragraph(f"Found {len(unique_ads)} active ad(s)", subheading_style))
                    story.append(Spacer(1, 0.1*inch))

                    for ad_name in unique_ads:
                        ad_df = ad_data[ad_data['product'] == ad_name]
                        ad_m = calculate_metrics(ad_df)

                        ad_summary = [
                            ['Metric', 'Value'],
                            ['Ad', str(ad_name)[:40]],
                            ['Spend', f"₹{ad_m['totals']['spend']:,.0f}"],
                            ['Revenue', f"₹{ad_m['totals']['revenue']:,.0f}"],
                            ['ROAS', f"{ad_m['ROAS']:.2f}x"],
                            ['ACoS', f"{ad_m['ACoS']:.2f}%"],
                            ['AOV', f"₹{ad_m['AOV']:.0f}"],
                            ['CTR', f"{ad_m['CTR']:.2f}%"],
                            ['Hook Rate', f"{ad_m['Hook_Rate']:.2f}%"],
                            ['CVR', f"{ad_m['Overall_CVR']:.2f}%"],
                            ['Cost/ATC', f"₹{ad_m['Cost_per_ATC']:.0f}"],
                            ['Cost/Purchase', f"₹{ad_m['CPA']:.0f}"],
                        ]

                        ad_table = Table(ad_summary, colWidths=[2*inch, 2*inch])
                        ad_table.setStyle(TableStyle([
                            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ec4899')),
                            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                            ('FONTSIZE', (0, 0), (-1, 0), 10),
                            ('BACKGROUND', (0, 1), (-1, -1), colors.pink),
                            ('GRID', (0, 0), (-1, -1), 1, colors.black),
                            ('FONTSIZE', (0, 1), (-1, -1), 9),
                            ('TOPPADDING', (0, 1), (-1, -1), 6),
                            ('BOTTOMPADDING', (0, 1), (-1, -1), 6),
                        ]))
                        story.append(ad_table)
                        story.append(Spacer(1, 0.15*inch))

                    story.append(PageBreak())

                    # Raw data for ads
                    story.append(Paragraph("Raw Data - All Active Ads", subheading_style))
                    ad_raw = ad_data[raw_cols].copy()
                    ad_raw['date'] = pd.to_datetime(ad_raw['date']).dt.strftime('%Y-%m-%d')

                    ad_raw_data = [['Date', 'Ad Name', 'Impr', 'Clk', 'OutClk', 'Spend', 'CPM', '3sV', 'Thru', 'LP', 'VC', 'ATC', 'Chk', 'Pur', 'Rev']]
                    for _, row in ad_raw.iterrows():
                        ad_raw_data.append([
                            row['date'],
                            str(row['product'])[:15] + '...' if len(str(row['product'])) > 15 else row['product'],
                            f"{int(row['impressions'])}", f"{int(row['clicks'])}", f"{int(row['outbound_clicks'])}",
                            f"{row['spend']:.0f}", f"{row['cpm']:.0f}",
                            f"{int(row['video_3s_views'])}", f"{int(row['video_thruplay'])}",
                            f"{int(row['lp_views'])}", f"{int(row['view_content'])}",
                            f"{int(row['adds_to_cart'])}", f"{int(row['checkouts'])}",
                            f"{int(row['purchases'])}", f"{row['revenue']:.0f}"
                        ])

                    ad_raw_table = Table(ad_raw_data, colWidths=[0.6*inch, 1.0*inch] + [cw]*13)
                    ad_raw_table.setStyle(TableStyle([
                        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#ec4899')),
                        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                        ('FONTSIZE', (0, 0), (-1, 0), 6),
                        ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                        ('BACKGROUND', (0, 1), (-1, -1), colors.pink),
                        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                        ('FONTSIZE', (0, 1), (-1, -1), 5.5),
                        ('TOPPADDING', (0, 1), (-1, -1), 3),
                        ('BOTTOMPADDING', (0, 1), (-1, -1), 3),
                    ]))
                    story.append(ad_raw_table)
                    story.append(Paragraph(f"Total rows: {len(ad_raw)}", styles['Normal']))
                    story.append(PageBreak())

        # ===== Recommendations =====
        recommendations = get_recommendations(metrics)
        if recommendations:
            story.append(Paragraph("Issues Detected & Recommendations", heading_style))

            for issue in recommendations:
                priority_color = '#ef4444' if issue['priority'] == 'CRITICAL' else '#f97316' if issue['priority'] == 'HIGH' else '#f59e0b'
                story.append(Paragraph(f"<font color='{priority_color}'><b>{issue['priority']}: {issue['metric']}</b></font>", subheading_style))
                story.append(Paragraph(f"Current: {issue['current']:.2f} | Target: {issue['target']:.2f}", styles['Normal']))
                story.append(Spacer(1, 0.1*inch))
                for rec in issue['recommendations']:
                    story.append(Paragraph(f"  - {rec}", styles['Normal']))
                story.append(Spacer(1, 0.2*inch))

        doc.build(story)
        buffer.seek(0)
        return buffer.getvalue()

    except ImportError:
        st.error("PDF generation requires reportlab and kaleido. Install with: pip install reportlab kaleido")
        return None
    except Exception as e:
        st.error(f"Error generating PDF: {str(e)}")
        return None


# ==================== MAIN APP ====================

st.title("📊 Meta Ads Live Analytics Dashboard")
st.markdown("**Real-time data from Meta Ads Manager API with Advanced Analytics**")

# Sidebar - API Configuration
st.sidebar.header("🔑 API Configuration")

with st.sidebar.expander("📝 Setup Instructions", expanded=not st.session_state.api_initialized):
    st.markdown("""
    **Enter your Meta API credentials:**

    1. **App ID** - From your Meta App settings
    2. **App Secret** - From your Meta App settings
    3. **Access Token** - From Graph API Explorer
    4. **Ad Account ID** - From Ads Manager (with 'act_' prefix)

    These are saved in your browser session only.
    """)

access_token = st.sidebar.text_input("Access Token", type="password", key="input_access_token")

# Hardcoded credentials
app_id = "1196805395915193"
app_secret = "7aa8c5a3254f8abcdb657e54642dd92b"
ad_account_id = "act_24472841068985090"

if st.sidebar.button("🔌 Connect to Meta API", type="primary"):
    if all([app_id, app_secret, access_token, ad_account_id]):
        with st.spinner("Connecting to Meta API..."):
            success, message = initialize_api(app_id, app_secret, access_token)
            if success:
                st.session_state.api_initialized = True
                st.session_state.saved_app_id = app_id
                st.session_state.saved_app_secret = app_secret
                st.session_state.saved_access_token = access_token
                st.session_state.saved_ad_account_id = ad_account_id
                st.sidebar.success("✅ Connected successfully!")
                st.rerun()
            else:
                st.sidebar.error(f"❌ {message}")
    else:
        st.sidebar.warning("⚠️ Please fill in all credentials")

# Main content
if not st.session_state.api_initialized:
    st.info("👈 Please configure your API credentials in the sidebar to get started")

    st.markdown("""
    ### 🚀 Getting Started

    This dashboard connects directly to your Meta Ads Manager account to pull real-time data.

    **What you'll need:**
    1. Meta App credentials (App ID & Secret)
    2. Access Token from Graph API Explorer
    3. Your Ad Account ID from Ads Manager

    **What you'll get:**
    - ✅ Real-time campaign performance data
    - ✅ **ROAS, ACoS, AOV & MER tracking**
    - ✅ **Creative metrics: Hook Rate, ThruPlay Rate, Outbound CTR**
    - ✅ **Cost metrics: Cost per ATC, Cost per Checkout, CPM**
    - ✅ **Multi-level analysis: Campaign, Ad Set, and Ad modes**
    - ✅ Comprehensive visualizations (gauges, trends, benchmarks)
    - ✅ **Day-wise performance breakdown with all metrics**
    - ✅ **PDF report generation with complete data**
    - ✅ Automated insights and recommendations
    - ✅ No manual Excel uploads needed!
    """)

else:
    # MODE SELECTOR
    st.sidebar.markdown("---")
    st.sidebar.header("🎯 Analysis Mode")

    mode_options = {
        '📊 Campaign Mode': 'Campaign Mode',
        '🎯 Ad Set Mode': 'Ad Set Mode',
        '🎨 Ad Mode': 'Ad Mode'
    }

    selected_mode_display = st.sidebar.radio(
        "Select Analysis Level:",
        options=list(mode_options.keys()),
        index=list(mode_options.values()).index(st.session_state.analysis_mode),
        help="Choose the level of granularity for your analysis"
    )

    st.session_state.analysis_mode = mode_options[selected_mode_display]

    mode_colors = {
        'Campaign Mode': '#3b82f6',
        'Ad Set Mode': '#8b5cf6',
        'Ad Mode': '#ec4899'
    }

    mode_emoji = {
        'Campaign Mode': '📊',
        'Ad Set Mode': '🎯',
        'Ad Mode': '🎨'
    }

    st.markdown(f"""
    <div style='padding: 10px; background-color: {mode_colors[st.session_state.analysis_mode]}20;
    border-left: 4px solid {mode_colors[st.session_state.analysis_mode]}; margin-bottom: 20px;'>
        <h3 style='margin: 0; color: {mode_colors[st.session_state.analysis_mode]};'>
            {mode_emoji[st.session_state.analysis_mode]} {st.session_state.analysis_mode}
        </h3>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("---")
    st.sidebar.header("📊 Select Data")

    # ==================== CAMPAIGN MODE ====================
    if st.session_state.analysis_mode == 'Campaign Mode':
        with st.spinner("Loading campaigns..."):
            campaigns, error = get_campaigns(st.session_state.saved_ad_account_id)

        if error:
            st.error(f"Error loading campaigns: {error}")
        elif campaigns:
            active_campaigns = [c for c in campaigns if c['status'] == 'ACTIVE']
            paused_campaigns = [c for c in campaigns if c['status'] == 'PAUSED']
            archived_campaigns = [c for c in campaigns if c['status'] == 'ARCHIVED']

            st.sidebar.markdown("### 🎯 Campaign Selection")
            st.sidebar.markdown("**Quick Select:**")
            col1, col2 = st.sidebar.columns(2)

            with col1:
                select_all_active = st.sidebar.button("✅ All Active", use_container_width=True)
            with col2:
                clear_selection = st.sidebar.button("❌ Clear All", use_container_width=True)

            st.sidebar.markdown("---")
            st.sidebar.markdown(f"""
            **Campaign Summary:**
            - 🟢 Active: {len(active_campaigns)}
            - 🟡 Paused: {len(paused_campaigns)}
            - 🔴 Archived: {len(archived_campaigns)}
            """)
            st.sidebar.markdown("---")

            campaign_options = {}

            if active_campaigns:
                st.sidebar.markdown("**🟢 Active Campaigns:**")
                for c in active_campaigns:
                    display_name = f"🟢 {c['name']}"
                    campaign_options[display_name] = c['id']

            if paused_campaigns:
                st.sidebar.markdown("**🟡 Paused Campaigns:**")
                for c in paused_campaigns:
                    display_name = f"🟡 {c['name']}"
                    campaign_options[display_name] = c['id']

            if archived_campaigns:
                with st.sidebar.expander("🔴 Archived Campaigns (Click to expand)", expanded=False):
                    for c in archived_campaigns:
                        display_name = f"🔴 {c['name']}"
                        campaign_options[display_name] = c['id']

            default_selection = []

            if select_all_active:
                default_selection = [f"🟢 {c['name']}" for c in active_campaigns]
            elif clear_selection:
                default_selection = []
            elif 'selected_campaign_names' in st.session_state:
                default_selection = st.session_state.selected_campaign_names

            selected_campaign_names = st.sidebar.multiselect(
                "Select Campaigns to Analyze:",
                options=list(campaign_options.keys()),
                default=default_selection,
                help="Select one or more campaigns",
                key=f"campaign_selector_{select_all_active}_{clear_selection}"
            )

            st.session_state.selected_campaign_names = selected_campaign_names
            selected_entity_ids = [campaign_options[name] for name in selected_campaign_names]

            if selected_campaign_names:
                st.sidebar.success(f"✅ {len(selected_campaign_names)} campaign(s) selected")

    # ==================== AD SET MODE ====================
    elif st.session_state.analysis_mode == 'Ad Set Mode':
        with st.spinner("Loading campaigns..."):
            campaigns, error = get_campaigns(st.session_state.saved_ad_account_id)

        if error:
            st.error(f"Error loading campaigns: {error}")
        elif campaigns:
            st.sidebar.markdown("### 📊 Step 1: Select Campaign(s)")

            campaign_options = {f"{c['name']}": c['id'] for c in campaigns}
            selected_campaign_names = st.sidebar.multiselect(
                "Select Campaigns:",
                options=list(campaign_options.keys()),
                help="First select campaigns to filter ad sets"
            )

            selected_campaign_ids = [campaign_options[name] for name in selected_campaign_names]

            if selected_campaign_ids:
                st.sidebar.success(f"✅ {len(selected_campaign_ids)} campaign(s) selected")
                st.sidebar.markdown("---")

                st.sidebar.markdown("### 🎯 Step 2: Select Ad Set(s)")

                with st.spinner("Loading ad sets..."):
                    adsets, error = get_adsets(st.session_state.saved_ad_account_id, selected_campaign_ids)

                if error:
                    st.sidebar.error(f"Error loading ad sets: {error}")
                elif adsets:
                    active_adsets = [a for a in adsets if a['status'] == 'ACTIVE']
                    paused_adsets = [a for a in adsets if a['status'] == 'PAUSED']

                    st.sidebar.markdown(f"""
                    **Ad Set Summary:**
                    - 🟢 Active: {len(active_adsets)}
                    - 🟡 Paused: {len(paused_adsets)}
                    """)

                    adset_options = {}

                    if active_adsets:
                        st.sidebar.markdown("**🟢 Active Ad Sets:**")
                        for a in active_adsets:
                            display_name = f"🟢 {a['name']} ({a['campaign_name']})"
                            adset_options[display_name] = a['id']

                    if paused_adsets:
                        st.sidebar.markdown("**🟡 Paused Ad Sets:**")
                        for a in paused_adsets:
                            display_name = f"🟡 {a['name']} ({a['campaign_name']})"
                            adset_options[display_name] = a['id']

                    selected_adset_names = st.sidebar.multiselect(
                        "Select Ad Sets to Analyze:",
                        options=list(adset_options.keys()),
                        help="Select one or more ad sets"
                    )

                    selected_entity_ids = [adset_options[name] for name in selected_adset_names]

                    if selected_adset_names:
                        st.sidebar.success(f"✅ {len(selected_adset_names)} ad set(s) selected")
                else:
                    st.sidebar.warning("No ad sets found for selected campaigns")
                    selected_entity_ids = []
            else:
                st.sidebar.info("👆 Please select campaigns first")
                selected_entity_ids = []

    # ==================== AD MODE ====================
    elif st.session_state.analysis_mode == 'Ad Mode':
        with st.spinner("Loading campaigns..."):
            campaigns, error = get_campaigns(st.session_state.saved_ad_account_id)

        if error:
            st.error(f"Error loading campaigns: {error}")
        elif campaigns:
            st.sidebar.markdown("### 📊 Step 1: Select Campaign(s)")

            campaign_options = {f"{c['name']}": c['id'] for c in campaigns}
            selected_campaign_names = st.sidebar.multiselect(
                "Select Campaigns:",
                options=list(campaign_options.keys()),
                help="First select campaigns"
            )

            selected_campaign_ids = [campaign_options[name] for name in selected_campaign_names]

            if selected_campaign_ids:
                st.sidebar.success(f"✅ {len(selected_campaign_ids)} campaign(s) selected")
                st.sidebar.markdown("---")

                st.sidebar.markdown("### 🎯 Step 2: Select Ad Set(s)")

                with st.spinner("Loading ad sets..."):
                    adsets, error = get_adsets(st.session_state.saved_ad_account_id, selected_campaign_ids)

                if error:
                    st.sidebar.error(f"Error loading ad sets: {error}")
                    selected_entity_ids = []
                elif adsets:
                    adset_options = {f"{a['name']} ({a['campaign_name']})": a['id'] for a in adsets}

                    selected_adset_names = st.sidebar.multiselect(
                        "Select Ad Sets:",
                        options=list(adset_options.keys()),
                        help="Select ad sets to filter ads"
                    )

                    selected_adset_ids = [adset_options[name] for name in selected_adset_names]

                    if selected_adset_ids:
                        st.sidebar.success(f"✅ {len(selected_adset_ids)} ad set(s) selected")
                        st.sidebar.markdown("---")

                        st.sidebar.markdown("### 🎨 Step 3: Select Ad(s)")

                        with st.spinner("Loading ads..."):
                            ads, error = get_ads(st.session_state.saved_ad_account_id, selected_adset_ids)

                        if error:
                            st.sidebar.error(f"Error loading ads: {error}")
                            selected_entity_ids = []
                        elif ads:
                            active_ads = [a for a in ads if a['status'] == 'ACTIVE']
                            paused_ads = [a for a in ads if a['status'] == 'PAUSED']

                            st.sidebar.markdown(f"""
                            **Ad Summary:**
                            - 🟢 Active: {len(active_ads)}
                            - 🟡 Paused: {len(paused_ads)}
                            """)

                            ad_options = {}

                            if active_ads:
                                st.sidebar.markdown("**🟢 Active Ads:**")
                                for a in active_ads:
                                    display_name = f"🟢 {a['name']} ({a['adset_name']})"
                                    ad_options[display_name] = a['id']

                            if paused_ads:
                                st.sidebar.markdown("**🟡 Paused Ads:**")
                                for a in paused_ads:
                                    display_name = f"🟡 {a['name']} ({a['adset_name']})"
                                    ad_options[display_name] = a['id']

                            selected_ad_names = st.sidebar.multiselect(
                                "Select Ads to Analyze:",
                                options=list(ad_options.keys()),
                                help="Select one or more ads"
                            )

                            selected_entity_ids = [ad_options[name] for name in selected_ad_names]

                            if selected_ad_names:
                                st.sidebar.success(f"✅ {len(selected_ad_names)} ad(s) selected")
                        else:
                            st.sidebar.warning("No ads found for selected ad sets")
                            selected_entity_ids = []
                    else:
                        st.sidebar.info("👆 Please select ad sets first")
                        selected_entity_ids = []
                else:
                    st.sidebar.warning("No ad sets found for selected campaigns")
                    selected_entity_ids = []
            else:
                st.sidebar.info("👆 Please select campaigns first")
                selected_entity_ids = []

    # ==================== DATE RANGE & FETCH ====================
    if 'selected_entity_ids' in locals() and selected_entity_ids:
        st.sidebar.markdown("---")
        date_option = st.sidebar.radio(
            "Date Range",
            ["Today", "Yesterday", "Last 7 Days", "Last 30 Days", "This Month", "Custom Range"]
        )

        start_date = None
        end_date = None
        date_preset = None

        if date_option == "Today":
            start_date = datetime.now().date()
            end_date = datetime.now().date()
        elif date_option == "Yesterday":
            start_date = (datetime.now() - timedelta(days=1)).date()
            end_date = (datetime.now() - timedelta(days=1)).date()
        elif date_option == "Custom Range":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
            with col2:
                end_date = st.date_input("End Date", datetime.now())
        else:
            date_preset_map = {
                "Last 7 Days": "last_7d",
                "Last 30 Days": "last_30d",
                "This Month": "this_month",
            }
            date_preset = date_preset_map[date_option]

        # Fetch data button
        if st.sidebar.button("📥 Fetch Data", type="primary"):
            if selected_entity_ids:
                level_map = {
                    'Campaign Mode': 'campaign',
                    'Ad Set Mode': 'adset',
                    'Ad Mode': 'ad'
                }
                level = level_map[st.session_state.analysis_mode]

                with st.spinner(f"Fetching data from Meta API ({st.session_state.analysis_mode})..."):
                    df, error = fetch_data(
                        st.session_state.saved_ad_account_id,
                        selected_entity_ids,
                        level=level,
                        date_preset=date_preset,
                        start_date=start_date,
                        end_date=end_date
                    )

                    if error:
                        st.error(f"Error: {error}")
                    elif df is not None and len(df) > 0:
                        st.session_state.df = df
                        st.session_state.data_loaded = True
                        st.session_state.current_mode = st.session_state.analysis_mode
                        st.session_state.date_preset = date_preset
                        st.session_state.start_date = start_date
                        st.session_state.end_date = end_date

                        if st.session_state.analysis_mode == 'Campaign Mode':
                            st.session_state.export_campaign_ids = selected_entity_ids
                        else:
                            st.session_state.export_campaign_ids = selected_campaign_ids if 'selected_campaign_ids' in locals() else []

                        num_entities = len(df['product'].unique())
                        num_days = len(df['date'].unique())
                        entity_label = level.replace('adset', 'ad set')
                        st.success(f"✅ Loaded {num_days} days of data for {num_entities} {entity_label}(s)!")
                    else:
                        st.warning(f"No data found for selected {level}s and date range")
            else:
                st.warning(f"Please select at least one entity")

        # ==================== DISPLAY DATA ====================
        if st.session_state.data_loaded and 'df' in st.session_state and 'current_mode' in st.session_state:
            df = st.session_state.df
            current_mode = st.session_state.current_mode

            st.sidebar.markdown("---")

            unique_entities = df['product'].unique()

            if len(unique_entities) > 1:
                entity_type = {
                    'Campaign Mode': 'Campaigns',
                    'Ad Set Mode': 'Ad Sets',
                    'Ad Mode': 'Ads'
                }[current_mode]

                view_mode = st.sidebar.radio(
                    "View Mode:",
                    [f"All {entity_type} Combined", f"Individual {entity_type[:-1]}"],
                    help=f"Choose to view all {entity_type.lower()} together or analyze them individually"
                )

                if view_mode == f"All {entity_type} Combined":
                    df_filtered = df.groupby('date', as_index=False).agg({
                        'impressions': 'sum',
                        'clicks': 'sum',
                        'spend': 'sum',
                        'reach': 'sum',
                        'frequency': 'mean',
                        'lp_views': 'sum',
                        'view_content': 'sum',
                        'adds_to_cart': 'sum',
                        'checkouts': 'sum',
                        'purchases': 'sum',
                        'revenue': 'sum',
                        'outbound_clicks': 'sum',
                        'video_3s_views': 'sum',
                        'video_thruplay': 'sum',
                        'cpm': 'mean',
                    })
                    df_filtered['product'] = f'All {entity_type} Combined'
                    selected_product = f'All {entity_type} Combined'
                else:
                    selected_product = st.sidebar.selectbox(
                        f"Select {entity_type[:-1]}:",
                        unique_entities,
                        help=f"Choose a specific {entity_type[:-1].lower()} to analyze"
                    )
                    df_filtered = df[df['product'] == selected_product]
            else:
                df_filtered = df
                selected_product = df['product'].iloc[0]

            # Calculate metrics
            metrics = calculate_metrics(df_filtered)

            # ===== HEADER =====
            col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
            with col1:
                entity_emoji = mode_emoji[current_mode]
                st.header(f"{entity_emoji} {selected_product}")
            with col2:
                num_days = len(df_filtered['date'].unique())
                st.metric("Days of Data", num_days)
            with col3:
                st.metric("Total Spend", f"₹{metrics['totals']['spend']:,.0f}")
            with col4:
                pdf_bytes = generate_pdf_report(
                    selected_product,
                    df_filtered,
                    metrics,
                    current_mode,
                    st.session_state.saved_ad_account_id if current_mode == 'Campaign Mode' else None,
                    st.session_state.get('export_campaign_ids', []) if current_mode == 'Campaign Mode' else None,
                    st.session_state.get('date_preset', 'last_30d'),
                    st.session_state.get('start_date', None),
                    st.session_state.get('end_date', None)
                )
                if pdf_bytes:
                    st.download_button(
                        label="📥 PDF Report",
                        data=pdf_bytes,
                        file_name=f"{datetime.now().strftime('%B_%d_%Y')}.pdf",
                        mime="application/pdf",
                        use_container_width=True
                    )

            st.divider()

            # ===== CREATIVE PERFORMANCE =====
            st.subheader("🎬 Creative Performance")
            creative_cols = st.columns(4)
            creative_metrics = [
                ('CTR', 'CTR'),
                ('Outbound_CTR', 'Outbound CTR'),
                ('Hook_Rate', 'Hook Rate'),
                ('ThruPlay_Rate', 'ThruPlay Rate'),
            ]
            for idx, (metric_name, label) in enumerate(creative_metrics):
                with creative_cols[idx]:
                    value = metrics[metric_name]
                    emoji = get_status_emoji(metric_name, value)
                    ideal = BENCHMARKS[metric_name]['ideal']
                    delta_val = value - ideal
                    unit = BENCHMARKS[metric_name]['unit']
                    st.metric(
                        label=f"{emoji} {label}",
                        value=f"{value:.2f}{unit}",
                        delta=f"{delta_val:+.2f}{unit}"
                    )

            st.divider()

            # ===== REACH & DISTRIBUTION =====
            st.subheader("📡 Reach & Distribution")
            reach_cols = st.columns(3)
            reach_metrics = [
                ('CPM', 'CPM'),
                ('Frequency', 'Frequency'),
                ('CPC', 'CPC'),
            ]
            for idx, (metric_name, label) in enumerate(reach_metrics):
                with reach_cols[idx]:
                    value = metrics[metric_name]
                    emoji = get_status_emoji(metric_name, value)
                    ideal = BENCHMARKS[metric_name]['ideal']
                    delta_val = value - ideal
                    unit = BENCHMARKS[metric_name]['unit']
                    # For lower-is-better metrics, invert delta display
                    display_delta = -delta_val if not BENCHMARKS[metric_name]['higher_better'] else delta_val
                    st.metric(
                        label=f"{emoji} {label}",
                        value=f"{value:.2f}{unit}",
                        delta=f"{display_delta:+.2f}{unit}"
                    )

            st.divider()

            # ===== FUNNEL CONVERSION =====
            st.subheader("🔄 Funnel Conversion Rates")
            funnel_cols = st.columns(6)
            funnel_metrics = [
                ('LP_View_Rate', 'LP View'),
                ('View_Content_Rate', 'View Content'),
                ('ATC_Rate', 'ATC Rate'),
                ('Checkout_Rate', 'Checkout'),
                ('Purchase_Rate', 'Purchase'),
                ('Overall_CVR', 'Overall CVR'),
            ]
            for idx, (metric_name, label) in enumerate(funnel_metrics):
                with funnel_cols[idx]:
                    value = metrics[metric_name]
                    emoji = get_status_emoji(metric_name, value)
                    ideal = BENCHMARKS[metric_name]['ideal']
                    delta_val = value - ideal
                    unit = BENCHMARKS[metric_name]['unit']
                    st.metric(
                        label=f"{emoji} {label}",
                        value=f"{value:.1f}{unit}",
                        delta=f"{delta_val:+.1f}{unit}"
                    )

            st.divider()

            # ===== COST METRICS =====
            st.subheader("💸 Cost Metrics")
            cost_cols = st.columns(3)
            cost_metrics_list = [
                ('CPA', 'Cost/Purchase'),
                ('Cost_per_ATC', 'Cost/ATC'),
                ('Cost_per_Checkout', 'Cost/Checkout'),
            ]
            for idx, (metric_name, label) in enumerate(cost_metrics_list):
                with cost_cols[idx]:
                    value = metrics[metric_name]
                    emoji = get_status_emoji(metric_name, value)
                    ideal = BENCHMARKS[metric_name]['ideal']
                    delta_val = value - ideal
                    unit = BENCHMARKS[metric_name]['unit']
                    display_delta = -delta_val  # Lower is better
                    st.metric(
                        label=f"{emoji} {label}",
                        value=f"{unit}{value:.0f}",
                        delta=f"{display_delta:+.0f}{unit}"
                    )

            st.divider()

            # ===== REVENUE & EFFICIENCY =====
            st.subheader("💰 Revenue & Efficiency")
            rev_cols = st.columns(4)
            rev_metrics = [
                ('ROAS', 'ROAS'),
                ('ACoS', 'ACoS'),
                ('AOV', 'AOV'),
                ('MER', 'MER'),
            ]
            for idx, (metric_name, label) in enumerate(rev_metrics):
                with rev_cols[idx]:
                    value = metrics[metric_name]
                    emoji = get_status_emoji(metric_name, value)
                    ideal = BENCHMARKS[metric_name]['ideal']
                    delta_val = value - ideal
                    unit = BENCHMARKS[metric_name]['unit']
                    higher_better = BENCHMARKS[metric_name]['higher_better']
                    display_delta = delta_val if higher_better else -delta_val
                    if metric_name == 'AOV':
                        st.metric(label=f"{emoji} {label}", value=f"{unit}{value:.0f}", delta=f"{display_delta:+.0f}{unit}")
                    else:
                        st.metric(label=f"{emoji} {label}", value=f"{value:.2f}{unit}", delta=f"{display_delta:+.2f}{unit}")

            st.divider()

            # ===== COMPLETE BENCHMARKS TABLE =====
            st.subheader("📊 Complete Performance vs Benchmarks")

            all_metric_names = [
                'CTR', 'Outbound_CTR', 'Hook_Rate', 'ThruPlay_Rate',
                'CPM', 'Frequency', 'CPC',
                'LP_View_Rate', 'View_Content_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR',
                'CPA', 'Cost_per_ATC', 'Cost_per_Checkout',
                'ROAS', 'ACoS', 'AOV', 'MER'
            ]

            comparison_data = []
            for metric_name in all_metric_names:
                if metric_name not in metrics or metric_name not in BENCHMARKS:
                    continue
                actual_val = metrics[metric_name]
                bench = BENCHMARKS[metric_name]
                gap = actual_val - bench['ideal']
                status = get_status_emoji(metric_name, actual_val)
                rating = get_status_label(metric_name, actual_val)

                comparison_data.append({
                    'Metric': metric_name.replace('_', ' '),
                    'Your Value': f"{actual_val:.2f}{bench['unit']}",
                    'Ideal Target': f"{bench['ideal']:.2f}{bench['unit']}",
                    'Min Acceptable': f"{bench['min']:.2f}{bench['unit']}",
                    'Gap': f"{gap:+.2f}{bench['unit']}",
                    'Rating': rating,
                    'Status': status
                })

            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)

            st.divider()

            # ===== PERFORMANCE GAUGES =====
            st.subheader("🎯 Performance Gauges")

            gauge_cols = st.columns(4)
            key_gauge_metrics = ['CTR', 'Hook_Rate', 'Overall_CVR', 'ROAS']

            for idx, metric_name in enumerate(key_gauge_metrics):
                with gauge_cols[idx]:
                    gauge_fig = create_performance_gauge(metrics[metric_name], metric_name)
                    if gauge_fig:
                        st.plotly_chart(gauge_fig, use_container_width=True)

            gauge_cols2 = st.columns(4)
            key_gauge_metrics2 = ['Checkout_Rate', 'ATC_Rate', 'CPM', 'CPC']

            for idx, metric_name in enumerate(key_gauge_metrics2):
                with gauge_cols2[idx]:
                    gauge_fig = create_performance_gauge(metrics[metric_name], metric_name)
                    if gauge_fig:
                        st.plotly_chart(gauge_fig, use_container_width=True)

            st.divider()

            # ===== DAILY PERFORMANCE VS BENCHMARKS =====
            st.subheader("📈 Daily Performance vs Benchmarks")

            chart_col1, chart_col2 = st.columns(2)

            with chart_col1:
                ctr_chart = create_actual_vs_ideal_chart(df_filtered, 'CTR')
                if ctr_chart:
                    st.plotly_chart(ctr_chart, use_container_width=True)

                hook_chart = create_actual_vs_ideal_chart(df_filtered, 'Hook_Rate')
                if hook_chart:
                    st.plotly_chart(hook_chart, use_container_width=True)

                atc_chart = create_actual_vs_ideal_chart(df_filtered, 'ATC_Rate')
                if atc_chart:
                    st.plotly_chart(atc_chart, use_container_width=True)

                roas_chart = create_actual_vs_ideal_chart(df_filtered, 'ROAS')
                if roas_chart:
                    st.plotly_chart(roas_chart, use_container_width=True)

            with chart_col2:
                outbound_chart = create_actual_vs_ideal_chart(df_filtered, 'Outbound_CTR')
                if outbound_chart:
                    st.plotly_chart(outbound_chart, use_container_width=True)

                checkout_chart = create_actual_vs_ideal_chart(df_filtered, 'Checkout_Rate')
                if checkout_chart:
                    st.plotly_chart(checkout_chart, use_container_width=True)

                cvr_chart = create_actual_vs_ideal_chart(df_filtered, 'Overall_CVR')
                if cvr_chart:
                    st.plotly_chart(cvr_chart, use_container_width=True)

                cpm_chart = create_actual_vs_ideal_chart(df_filtered, 'CPM')
                if cpm_chart:
                    st.plotly_chart(cpm_chart, use_container_width=True)

            st.divider()

            # ===== DAY-WISE PERFORMANCE TABLE =====
            st.subheader("📅 Day-wise Performance Breakdown")

            daily_metrics = calculate_daily_metrics(df_filtered)
            display_cols = ['date', 'CTR', 'Outbound_CTR', 'Hook_Rate', 'ThruPlay_Rate',
                            'CPM', 'CPC', 'Frequency',
                            'LP_View_Rate', 'View_Content_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR',
                            'CPA', 'Cost_per_ATC', 'Cost_per_Checkout',
                            'ROAS', 'ACoS', 'AOV', 'MER']
            daily_display = daily_metrics[display_cols].copy()
            daily_display['date'] = pd.to_datetime(daily_display['date']).dt.strftime('%Y-%m-%d')

            for col in display_cols[1:]:
                daily_display[col] = daily_display[col].round(2)

            st.dataframe(daily_display, use_container_width=True, hide_index=True)
            st.info("💡 **Rating Guide:** ✅ Good/Excellent | ⚠️ Acceptable | 🚨 Weak")

            st.divider()

            # ===== CONVERSION FUNNEL & REVENUE =====
            col1, col2 = st.columns(2)

            with col1:
                st.subheader("📊 Conversion Funnel")
                fig_funnel = create_funnel_chart(metrics)
                st.plotly_chart(fig_funnel, use_container_width=True)

            with col2:
                st.subheader("💰 Revenue & Cost Summary")

                st.markdown(f"""
                <div style='padding: 15px; background-color: #eff6ff; border-left: 4px solid #3b82f6; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>Total Spent</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>₹{metrics['totals']['spend']:,.0f}</div>
                </div>
                <div style='padding: 15px; background-color: #dcfce7; border-left: 4px solid #22c55e; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>Total Revenue</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>₹{metrics['totals']['revenue']:,.0f}</div>
                </div>
                <div style='padding: 15px; background-color: #f3e8ff; border-left: 4px solid #a855f7; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>ROAS</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>{metrics['ROAS']:.2f}x</div>
                    <div style='color: #6b7280; font-size: 11px;'>Target: 4x | Min: 2x</div>
                </div>
                <div style='padding: 15px; background-color: #fef3c7; border-left: 4px solid #f59e0b; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>ACoS</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>{metrics['ACoS']:.2f}%</div>
                    <div style='color: #6b7280; font-size: 11px;'>Target: 25% | Max: 20%</div>
                </div>
                <div style='padding: 15px; background-color: #fce7f3; border-left: 4px solid #ec4899; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>AOV (Avg Order Value)</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>₹{metrics['AOV']:.0f}</div>
                    <div style='color: #6b7280; font-size: 11px;'>Target: ₹600 | Good: ₹900+</div>
                </div>
                <div style='padding: 15px; background-color: #fee2e2; border-left: 4px solid #ef4444; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>Cost Per Purchase</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>₹{metrics['CPA']:.0f}</div>
                    <div style='color: #6b7280; font-size: 11px;'>Target: ₹300 | Good: ₹200</div>
                </div>
                <div style='padding: 15px; background-color: #e0e7ff; border-left: 4px solid #6366f1; margin-bottom: 10px;'>
                    <div style='color: #1f2937; font-size: 14px;'>CPM</div>
                    <div style='font-size: 24px; font-weight: bold; color: #000000;'>₹{metrics['CPM']:.0f}</div>
                    <div style='color: #6b7280; font-size: 11px;'>Target: ₹150 | Good: under ₹100</div>
                </div>
                """, unsafe_allow_html=True)

            st.divider()

            # ===== DAILY TRENDS =====
            st.subheader("📈 Daily Trends")

            col1, col2 = st.columns(2)

            with col1:
                fig_conversions = px.line(
                    df_filtered,
                    x="date",
                    y=["clicks", "outbound_clicks", "lp_views", "view_content", "adds_to_cart", "checkouts", "purchases"],
                    title="Daily Conversions (Full Funnel)",
                    labels={"value": "Count", "variable": "Metric"}
                )
                st.plotly_chart(fig_conversions, use_container_width=True)

            with col2:
                fig_spend = px.line(
                    df_filtered,
                    x="date",
                    y="spend",
                    title="Daily Spend & Revenue",
                )
                fig_spend.add_scatter(x=df_filtered['date'], y=df_filtered['revenue'], mode='lines', name='Revenue')
                st.plotly_chart(fig_spend, use_container_width=True)

            # Creative metrics trend
            col3, col4 = st.columns(2)
            with col3:
                daily_calc = calculate_daily_metrics(df_filtered)
                fig_creative = px.line(
                    daily_calc,
                    x="date",
                    y=["Hook_Rate", "ThruPlay_Rate"],
                    title="Creative Performance Trend",
                    labels={"value": "%", "variable": "Metric"}
                )
                st.plotly_chart(fig_creative, use_container_width=True)

            with col4:
                fig_costs = px.line(
                    daily_calc,
                    x="date",
                    y=["CPA", "Cost_per_ATC", "Cost_per_Checkout"],
                    title="Cost Metrics Trend (₹)",
                    labels={"value": "₹", "variable": "Metric"}
                )
                st.plotly_chart(fig_costs, use_container_width=True)

            st.divider()

            # ===== RECOMMENDATIONS =====
            recommendations = get_recommendations(metrics)

            if recommendations:
                st.subheader("🚨 Issues Detected & Recommendations")

                for issue in recommendations:
                    with st.expander(f"{issue['priority']}: {issue['metric']} - Current: {issue['current']:.2f} → Target: {issue['target']:.2f}", expanded=True):
                        st.markdown(f"**Current Performance:** {issue['current']:.2f}")
                        st.markdown(f"**Target Performance:** {issue['target']:.2f}")
                        st.markdown("**Action Items:**")

                        for rec in issue['recommendations']:
                            st.markdown(f"• {rec}")
            else:
                st.success("🎉 All metrics are performing well! Keep up the good work.")

            # ===== RAW DATA =====
            with st.expander("📄 View Raw Data (All Columns)"):
                st.dataframe(df_filtered, use_container_width=True)

# Footer
st.markdown("---")
st.markdown("**Meta Ads Live Dashboard** | Powered by Meta Marketing API | Full Creative, Funnel, Cost & Revenue Analytics")
