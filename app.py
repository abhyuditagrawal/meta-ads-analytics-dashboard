import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, List
from io import BytesIO
from datetime import datetime, timedelta
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
import json

# Page config
st.set_page_config(
    page_title="Meta Ads Live Dashboard",
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

# Initialize session state
if 'api_initialized' not in st.session_state:
    st.session_state.api_initialized = False
if 'data_loaded' not in st.session_state:
    st.session_state.data_loaded = False

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

def fetch_campaign_data(ad_account_id, campaign_ids, date_preset='last_30d', start_date=None, end_date=None):
    """Fetch performance data for selected campaigns"""
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
            'ctr',
            'actions',
            'action_values',
            'cost_per_action_type',
        ]
        
        params = {
            'level': 'campaign',
            'time_increment': 1,
            'filtering': [{'field': 'campaign.id', 'operator': 'IN', 'value': campaign_ids}],
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
                'product': insight.get('campaign_name'),
                'impressions': int(insight.get('impressions', 0)),
                'clicks': int(insight.get('clicks', 0)),
                'spend': float(insight.get('spend', 0)),
                'reach': int(insight.get('reach', 0)),
                'frequency': float(insight.get('frequency', 0)),
                'cpc': float(insight.get('cpc', 0)),
                'ctr': float(insight.get('ctr', 0)),
                'lp_views': 0,
                'adds_to_cart': 0,
                'checkouts': 0,
                'purchases': 0,
            }
            
            actions = insight.get('actions', [])
            for action in actions:
                action_type = action.get('action_type')
                value = int(action.get('value', 0))
                
                if 'landing_page_view' in action_type:
                    row['lp_views'] = value
                elif 'add_to_cart' in action_type or action_type == 'offsite_conversion.fb_pixel_add_to_cart':
                    row['adds_to_cart'] = value
                elif 'initiate_checkout' in action_type or action_type == 'offsite_conversion.fb_pixel_initiate_checkout':
                    row['checkouts'] = value
                elif 'purchase' in action_type or action_type == 'offsite_conversion.fb_pixel_purchase':
                    row['purchases'] = value
            
            data_list.append(row)
        
        if data_list:
            df = pd.DataFrame(data_list)
            return df, None
        else:
            return None, "No data found for selected campaigns and date range"
            
    except Exception as e:
        return None, str(e)

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
        'Frequency': totals.frequency / len(df) if len(df) > 0 else 0,
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

def get_status_emoji(metric_name: str, value: float) -> str:
    """Get emoji for status"""
    if metric_name not in BENCHMARKS:
        return '⚪'
    
    bench = BENCHMARKS[metric_name]
    if value >= bench['ideal']:
        return '✅'
    elif value >= bench['min']:
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
            ]
        })
    
    priority_order = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2}
    issues.sort(key=lambda x: priority_order[x['priority']])
    
    return issues

# ==================== MAIN APP ====================

st.title("📊 Meta Ads Live Analytics Dashboard")
st.markdown("**Real-time data from Meta Ads Manager API**")

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

# app_id = st.sidebar.text_input("App ID", type="password", key="input_app_id")
# app_secret = st.sidebar.text_input("App Secret", type="password", key="input_app_secret")
access_token = st.sidebar.text_input("Access Token", type="password", key="input_access_token")
# ad_account_id = st.sidebar.text_input("Ad Account ID", placeholder="act_123456789", key="input_ad_account_id")

app_id="1196805395915193"
app_secret="7aa8c5a3254f8abcdb657e54642dd92b"
# access_token="EAARAfPh9IbkBQl8h8MkRXfWsxutlZADQOJvAF4a1OnxZAjKvZAi2BZBHNzitSOfllZBJaH4jxsVSDCKCIIC2Ll8wwNLyjDkWgZBnlbSiNWXFxsNi0WlZCHlCC4NQzcZAIRV6QnXCmi3ewFgshjKdiUzxbM0wXOHwnZBBfCm20C0pj3pihFp3E7SOFcH3HXLVdHQ0st19q7dXkZBDBvk22mCBAcT6eopGZAy6w2nhgQVQhfzpq3qghKs923RdkeZArzTEluvXGxcZCYkFURYWdgBkvbHMDkfgliXZCa7OwuzCm9"
ad_account_id="act_24472841068985090"


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
    - ✅ Automated insights and recommendations
    - ✅ Conversion funnel analysis
    - ✅ Benchmark comparisons
    - ✅ No manual Excel uploads needed!
    """)
    
else:
    # Fetch campaigns
    st.sidebar.header("📊 Select Data")
    
    with st.spinner("Loading campaigns..."):
        campaigns, error = get_campaigns(st.session_state.saved_ad_account_id)
    
    if error:
        st.error(f"Error loading campaigns: {error}")
    elif campaigns:
        # Campaign selector
        campaign_options = {f"{c['name']} ({c['status']})": c['id'] for c in campaigns}
        selected_campaign_names = st.sidebar.multiselect(
            "Select Campaigns",
            options=list(campaign_options.keys()),
            default=[list(campaign_options.keys())[0]] if campaign_options else []
        )
        
        selected_campaign_ids = [campaign_options[name] for name in selected_campaign_names]
        
        # Date range selector
        date_option = st.sidebar.radio(
            "Date Range",
            ["Last 7 Days", "Last 30 Days", "This Month", "Custom Range"]
        )
        
        date_preset_map = {
            "Last 7 Days": "last_7d",
            "Last 30 Days": "last_30d",
            "This Month": "this_month",
        }
        
        start_date = None
        end_date = None
        date_preset = None
        
        if date_option == "Custom Range":
            col1, col2 = st.sidebar.columns(2)
            with col1:
                start_date = st.date_input("Start Date", datetime.now() - timedelta(days=30))
            with col2:
                end_date = st.date_input("End Date", datetime.now())
        else:
            date_preset = date_preset_map[date_option]
        
        # Fetch data button
        if st.sidebar.button("📥 Fetch Data", type="primary"):
            if selected_campaign_ids:
                with st.spinner("Fetching data from Meta API..."):
                    df, error = fetch_campaign_data(
                        st.session_state.saved_ad_account_id,
                        selected_campaign_ids,
                        date_preset=date_preset,
                        start_date=start_date,
                        end_date=end_date
                    )
                    
                    if error:
                        st.error(f"Error: {error}")
                    elif df is not None and len(df) > 0:
                        st.session_state.df = df
                        st.session_state.data_loaded = True
                        st.success(f"✅ Loaded {len(df)} days of data!")
                    else:
                        st.warning("No data found for selected campaigns and date range")
            else:
                st.warning("Please select at least one campaign")
        
        # Display data if loaded
        if st.session_state.data_loaded and 'df' in st.session_state:
            df = st.session_state.df
            
            # If multiple campaigns, show selector
            if len(df['product'].unique()) > 1:
                st.sidebar.markdown("---")
                view_mode = st.sidebar.radio("View Mode", ["Single Campaign", "Compare Campaigns"])
                
                if view_mode == "Single Campaign":
                    selected_product = st.sidebar.selectbox("Select Campaign", df['product'].unique())
                    df_filtered = df[df['product'] == selected_product]
                else:
                    df_filtered = df
            else:
                df_filtered = df
                selected_product = df['product'].iloc[0]
            
            # Calculate metrics
            metrics = calculate_metrics(df_filtered)
            
            # Display header
            col1, col2, col3 = st.columns([2, 1, 1])
            with col1:
                if len(df['product'].unique()) == 1:
                    st.header(f"📦 {selected_product}")
            with col2:
                st.metric("Days of Data", len(df_filtered))
            with col3:
                st.metric("Total Spend", f"₹{metrics['totals']['spend']:,.0f}")
            
            st.divider()
            
            # Performance Overview
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
                        delta=f"{delta_val:+.2f}% vs target"
                    )
            
            st.divider()
            
            # Performance vs Benchmarks
            st.subheader("📊 Performance vs Benchmarks")
            
            comparison_data = []
            for metric_name in ['CTR', 'LP_View_Rate', 'ATC_Rate', 'Checkout_Rate', 'Purchase_Rate', 'Overall_CVR', 'CPC', 'CPA', 'Frequency']:
                actual_val = metrics[metric_name]
                bench = BENCHMARKS[metric_name]
                
                gap = actual_val - bench['ideal']
                status = get_status_emoji(metric_name, actual_val)
                
                comparison_data.append({
                    'Metric': metric_name.replace('_', ' '),
                    'Your Average': f"{actual_val:.2f}{bench['unit']}",
                    'Ideal Target': f"{bench['ideal']:.2f}{bench['unit']}",
                    'Min Acceptable': f"{bench['min']:.2f}{bench['unit']}",
                    'Gap': f"{gap:+.2f}{bench['unit']}",
                    'Status': status
                })
            
            comparison_df = pd.DataFrame(comparison_data)
            st.dataframe(comparison_df, use_container_width=True, hide_index=True)
            
            st.divider()
            
            # Charts
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
            
            # Daily Trends
            st.subheader("📈 Daily Trends")
            
            col1, col2 = st.columns(2)
            
            with col1:
                fig_conversions = px.line(
                    df_filtered,
                    x="date",
                    y=["clicks", "adds_to_cart", "purchases"],
                    title="Daily Conversions",
                    labels={"value": "Count", "variable": "Metric"}
                )
                st.plotly_chart(fig_conversions, use_container_width=True)
            
            with col2:
                fig_spend = px.line(
                    df_filtered,
                    x="date",
                    y="spend",
                    title="Daily Spend"
                )
                st.plotly_chart(fig_spend, use_container_width=True)
            
            st.divider()
            
            # Recommendations
            recommendations = get_recommendations(metrics)
            
            if recommendations:
                st.subheader("🚨 Issues Detected & Recommendations")
                
                for issue in recommendations:
                    with st.expander(f"{issue['priority']}: {issue['metric']} - Current: {issue['current']:.1f}% → Target: {issue['target']}%", expanded=True):
                        st.markdown(f"**Current Performance:** {issue['current']:.2f}%")
                        st.markdown(f"**Target Performance:** {issue['target']:.2f}%")
                        st.markdown("**Action Items:**")
                        
                        for rec in issue['recommendations']:
                            st.markdown(f"• {rec}")
            else:
                st.success("🎉 All metrics are performing well! Keep up the good work.")
            
            # Raw Data
            with st.expander("📄 View Raw Data"):
                st.dataframe(df_filtered, use_container_width=True)
    
    else:
        st.warning("No campaigns found in this ad account")

# Footer
st.markdown("---")
st.markdown("**Meta Ads Live Dashboard** | Powered by Meta Marketing API | Real-time Analytics")