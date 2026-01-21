"""
Meta Ads API Connection Test
This script tests your API credentials and fetches basic campaign data
"""

from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.adobjects.campaign import Campaign
import pandas as pd
from datetime import datetime, timedelta

# ============================================
# CONFIGURATION - FILL IN YOUR CREDENTIALS
# ============================================

# Replace these with your actual credentials
ACCESS_TOKEN = 'EAARAfPh9IbkBQrQBujBjMEHJped6uYniCfinIyYDZCarPVPSRQT25m0VXX8gH53yxxqYGUi1gVFvKITLELEGcH1JEWI5Lhj1q4BOlIVAIGSzQbGfQTJcCle9QBSanEYa1W1lhnXJ4WjtwhHziYBABiA09dH94czXx5RVR8C3lXZB8u1cPXkbkWz8HjCKfSxgZAsqbyqtw4BiFT2eJVhRai8TwrFgG6LlAdychDZBwFt86eKxUpplqdVOQNPjCs1BqIH9bo1WOXN4eVdDjZABtr3fWIVbQVsCYLSAZD'
APP_SECRET = '7aa8c5a3254f8abcdb657e54642dd92b'
APP_ID = '1196805395915193'
AD_ACCOUNT_ID = 'act_24472841068985090'  # Must include 'act_' prefix

# ============================================
# STEP 1: Initialize API
# ============================================

print("=" * 60)
print("META ADS API CONNECTION TEST")
print("=" * 60)

try:
    # Initialize the API
    FacebookAdsApi.init(
        app_id=APP_ID,
        app_secret=APP_SECRET,
        access_token=ACCESS_TOKEN
    )
    print("✅ API Initialized Successfully!")
    
except Exception as e:
    print(f"❌ Error initializing API: {e}")
    exit()

# ============================================
# STEP 2: Connect to Ad Account
# ============================================

try:
    ad_account = AdAccount(AD_ACCOUNT_ID)
    
    # Test connection by getting account info
    account_info = ad_account.api_get(fields=['name', 'account_status', 'currency'])
    
    print(f"\n✅ Connected to Ad Account!")
    print(f"   Account Name: {account_info.get('name', 'N/A')}")
    print(f"   Account Status: {account_info.get('account_status', 'N/A')}")
    print(f"   Currency: {account_info.get('currency', 'N/A')}")
    
except Exception as e:
    print(f"❌ Error connecting to ad account: {e}")
    print("\nTroubleshooting:")
    print("1. Check your AD_ACCOUNT_ID includes 'act_' prefix")
    print("2. Verify your access token has ads_read permission")
    print("3. Make sure the account ID is correct")
    exit()

# ============================================
# STEP 3: Fetch Campaigns
# ============================================

print("\n" + "=" * 60)
print("FETCHING CAMPAIGNS")
print("=" * 60)

try:
    # Get all campaigns
    campaigns = ad_account.get_campaigns(
        fields=[
            'name',
            'id',
            'status',
            'objective',
            'daily_budget',
            'lifetime_budget',
        ]
    )
    
    campaign_list = []
    for campaign in campaigns:
        campaign_list.append({
            'Campaign ID': campaign.get('id'),
            'Campaign Name': campaign.get('name'),
            'Status': campaign.get('status'),
            'Objective': campaign.get('objective'),
            'Daily Budget': campaign.get('daily_budget', 'N/A'),
            'Lifetime Budget': campaign.get('lifetime_budget', 'N/A'),
        })
    
    if campaign_list:
        df_campaigns = pd.DataFrame(campaign_list)
        print(f"\n✅ Found {len(campaign_list)} campaigns!")
        print("\nYour Campaigns:")
        print(df_campaigns.to_string(index=False))
    else:
        print("\n⚠️ No campaigns found in this ad account.")
    
except Exception as e:
    print(f"❌ Error fetching campaigns: {e}")
    exit()

# ============================================
# STEP 4: Fetch Campaign Performance Data
# ============================================

print("\n" + "=" * 60)
print("FETCHING PERFORMANCE DATA (Last 7 Days)")
print("=" * 60)

try:
    # Date range - last 7 days
    end_date = datetime.now()
    start_date = end_date - timedelta(days=7)
    
    date_preset = 'last_7d'  # You can also use: 'today', 'yesterday', 'last_30d', 'this_month', 'lifetime'
    
    # Fields to fetch
    fields = [
        'campaign_name',
        'impressions',
        'clicks',
        'spend',
        'reach',
        'frequency',
        'cpc',
        'cpm',
        'cpp',
        'ctr',
        'actions',  # This contains conversions like purchases, add to cart, etc.
        'cost_per_action_type',
        'action_values',
    ]
    
    # Parameters
    params = {
        'level': 'campaign',
        'date_preset': date_preset,
        'time_increment': 1,  # 1 = daily breakdown
    }
    
    # Fetch insights
    insights = ad_account.get_insights(
        fields=fields,
        params=params
    )
    
    insights_list = []
    for insight in insights:
        row = {
            'Date': insight.get('date_start'),
            'Campaign': insight.get('campaign_name'),
            'Impressions': insight.get('impressions', 0),
            'Clicks': insight.get('clicks', 0),
            'Spend': float(insight.get('spend', 0)),
            'Reach': insight.get('reach', 0),
            'Frequency': float(insight.get('frequency', 0)),
            'CPC': float(insight.get('cpc', 0)),
            'CTR': float(insight.get('ctr', 0)),
        }
        
        # Extract conversion actions
        actions = insight.get('actions', [])
        for action in actions:
            action_type = action.get('action_type')
            value = int(action.get('value', 0))
            
            if action_type == 'landing_page_view':
                row['Landing Page Views'] = value
            elif action_type == 'add_to_cart':
                row['Adds to Cart'] = value
            elif action_type == 'initiate_checkout':
                row['Checkouts Initiated'] = value
            elif action_type == 'purchase' or action_type == 'offsite_conversion.fb_pixel_purchase':
                row['Purchases'] = value
            elif action_type == 'link_click':
                row['Link Clicks'] = value
            elif action_type == 'video_view':
                row['Video Views'] = value
        
        insights_list.append(row)
    
    if insights_list:
        df_insights = pd.DataFrame(insights_list)
        
        # Fill missing columns with 0
        for col in ['Landing Page Views', 'Adds to Cart', 'Checkouts Initiated', 'Purchases', 'Link Clicks']:
            if col not in df_insights.columns:
                df_insights[col] = 0
        
        print(f"\n✅ Fetched {len(insights_list)} rows of performance data!")
        print("\nPerformance Summary:")
        print(df_insights.to_string(index=False))
        
        # Save to CSV
        filename = f"meta_ads_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        df_insights.to_csv(filename, index=False)
        print(f"\n💾 Data saved to: {filename}")
        
    else:
        print("\n⚠️ No performance data found for the selected date range.")
    
except Exception as e:
    print(f"❌ Error fetching performance data: {e}")
    print(f"\nError details: {str(e)}")

# ============================================
# SUCCESS!
# ============================================

print("\n" + "=" * 60)
print("✅ API CONNECTION TEST COMPLETED SUCCESSFULLY!")
print("=" * 60)
print("\nNext Steps:")
print("1. Check the CSV file with your data")
print("2. Ready to build the full dashboard!")
print("3. All your credentials are working correctly!")