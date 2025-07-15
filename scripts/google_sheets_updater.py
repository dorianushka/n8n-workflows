#!/usr/bin/env python3
"""
Google Sheets Updater for Email Tracking - Prestige Production
=============================================================

This script updates Google Sheets with email tracking data:
- Updates "Last Contacted" column with current date
- Updates "Last marketing email send date" 
- Updates tracking columns (delivered, opened, clicked, bounced)

Usage: from google_sheets_updater import update_email_tracking
"""

import os
import json
from datetime import datetime
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
import pickle
from pathlib import Path

# Google Sheets API configuration
SCOPES = ['https://www.googleapis.com/auth/spreadsheets']

def authenticate_google_sheets():
    """Authenticate and return Google Sheets service"""
    creds = None
    
    # Load existing credentials
    if os.path.exists('token.json'):
        with open('token.json', 'r') as token:
            creds_data = json.load(token)
            creds = Credentials.from_authorized_user_info(creds_data, SCOPES)
    
    # If no valid credentials, authenticate
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # You'll need to set up OAuth2 credentials
            print("⚠️  Google Sheets credentials not found. Please run authentication first.")
            return None
        
        # Save credentials for next run
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    
    return build('sheets', 'v4', credentials=creds)

def find_client_row(service, spreadsheet_id, sheet_name, client_email):
    """Find the row number for a specific client email"""
    try:
        # Read the entire sheet to find the client
        result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!A:Z"
        ).execute()
        
        values = result.get('values', [])
        if not values:
            return None
        
        # Find the header row and email column
        headers = values[0] if values else []
        
        # Find email column index
        email_col_index = None
        for i, header in enumerate(headers):
            if 'email' in header.lower():
                email_col_index = i
                break
        
        if email_col_index is None:
            print(f"❌ Could not find email column in sheet")
            return None
        
        # Find the client row
        for row_idx, row in enumerate(values[1:], start=2):  # Start from row 2 (skip header)
            if row_idx < len(row) and row[email_col_index] == client_email:
                return row_idx
        
        return None
        
    except Exception as e:
        print(f"❌ Error finding client row: {e}")
        return None

def update_email_tracking(client_email, client_name, tracking_data=None):
    """
    Update Google Sheets with email tracking data
    
    Args:
        client_email (str): Client's email address
        client_name (str): Client's name
        tracking_data (dict): Optional tracking data with opens, clicks, bounces
    
    Returns:
        bool: Success status
    """
    try:
        # Get configuration from environment
        spreadsheet_id = os.getenv('GOOGLE_SHEETS_FILE_ID')
        sheet_name = os.getenv('GOOGLE_SHEETS_SHEET_NAME', 'Sheet1')
        
        if not spreadsheet_id:
            print("⚠️  GOOGLE_SHEETS_FILE_ID not configured")
            return False
        
        # Authenticate
        service = authenticate_google_sheets()
        if not service:
            return False
        
        # Find client row
        client_row = find_client_row(service, spreadsheet_id, sheet_name, client_email)
        if not client_row:
            print(f"❌ Client {client_email} not found in spreadsheet")
            return False
        
        # Get current sheet headers to find column indices
        header_result = service.spreadsheets().values().get(
            spreadsheetId=spreadsheet_id,
            range=f"{sheet_name}!1:1"
        ).execute()
        
        headers = header_result.get('values', [[]])[0]
        
        # Map column names to indices
        column_mapping = {}
        for i, header in enumerate(headers):
            header_lower = header.lower()
            if 'last contacted' in header_lower:
                column_mapping['last_contacted'] = i
            elif 'last marketing email send date' in header_lower:
                column_mapping['last_email_sent'] = i
            elif 'marketing emails delivered' in header_lower:
                column_mapping['emails_delivered'] = i
            elif 'marketing emails opened' in header_lower:
                column_mapping['emails_opened'] = i
            elif 'marketing emails clicked' in header_lower:
                column_mapping['emails_clicked'] = i
            elif 'marketing emails bounced' in header_lower:
                column_mapping['emails_bounced'] = i
        
        # Prepare updates
        current_date = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        updates = []
        
        # Always update "Last Contacted" and "Last marketing email send date"
        if 'last_contacted' in column_mapping:
            col_letter = chr(ord('A') + column_mapping['last_contacted'])
            updates.append({
                'range': f"{sheet_name}!{col_letter}{client_row}",
                'values': [[current_date]]
            })
        
        if 'last_email_sent' in column_mapping:
            col_letter = chr(ord('A') + column_mapping['last_email_sent'])
            updates.append({
                'range': f"{sheet_name}!{col_letter}{client_row}",
                'values': [[current_date]]
            })
        
        # Update delivered count (increment by 1)
        if 'emails_delivered' in column_mapping:
            col_letter = chr(ord('A') + column_mapping['emails_delivered'])
            # Get current value
            current_result = service.spreadsheets().values().get(
                spreadsheetId=spreadsheet_id,
                range=f"{sheet_name}!{col_letter}{client_row}"
            ).execute()
            
            current_value = current_result.get('values', [[0]])[0][0] if current_result.get('values') else 0
            try:
                current_count = int(current_value) if current_value else 0
            except (ValueError, TypeError):
                current_count = 0
            
            updates.append({
                'range': f"{sheet_name}!{col_letter}{client_row}",
                'values': [[current_count + 1]]
            })
        
        # Update tracking data if provided
        if tracking_data:
            if tracking_data.get('opened') and 'emails_opened' in column_mapping:
                col_letter = chr(ord('A') + column_mapping['emails_opened'])
                updates.append({
                    'range': f"{sheet_name}!{col_letter}{client_row}",
                    'values': [[tracking_data['opened']]]
                })
            
            if tracking_data.get('clicked') and 'emails_clicked' in column_mapping:
                col_letter = chr(ord('A') + column_mapping['emails_clicked'])
                updates.append({
                    'range': f"{sheet_name}!{col_letter}{client_row}",
                    'values': [[tracking_data['clicked']]]
                })
            
            if tracking_data.get('bounced') and 'emails_bounced' in column_mapping:
                col_letter = chr(ord('A') + column_mapping['emails_bounced'])
                updates.append({
                    'range': f"{sheet_name}!{col_letter}{client_row}",
                    'values': [[tracking_data['bounced']]]
                })
        
        # Perform batch update
        if updates:
            body = {
                'valueInputOption': 'USER_ENTERED',
                'data': updates
            }
            
            service.spreadsheets().values().batchUpdate(
                spreadsheetId=spreadsheet_id,
                body=body
            ).execute()
            
            print(f"✅ Updated Google Sheets for {client_name} ({client_email})")
            return True
        else:
            print("⚠️  No columns found to update")
            return False
            
    except Exception as e:
        print(f"❌ Error updating Google Sheets: {e}")
        return False

def update_tracking_stats_batch(tracking_stats):
    """
    Update multiple clients' tracking stats in batch
    
    Args:
        tracking_stats (list): List of dicts with client_email, opens, clicks, bounces
    """
    print(f"📊 Updating tracking stats for {len(tracking_stats)} clients...")
    
    success_count = 0
    for stats in tracking_stats:
        if update_email_tracking(
            stats['client_email'],
            stats.get('client_name', 'Unknown'),
            {
                'opened': stats.get('opens', 0),
                'clicked': stats.get('clicks', 0),
                'bounced': 1 if stats.get('bounced') else 0
            }
        ):
            success_count += 1
    
    print(f"✅ Successfully updated {success_count}/{len(tracking_stats)} clients")
    return success_count

if __name__ == "__main__":
    # Test the updater
    test_email = "test@example.com"
    test_name = "Test Client"
    
    print("🧪 Testing Google Sheets updater...")
    success = update_email_tracking(test_email, test_name)
    
    if success:
        print("✅ Google Sheets updater test successful!")
    else:
        print("❌ Google Sheets updater test failed!") 