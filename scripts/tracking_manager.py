#!/usr/bin/env python3
"""
Email Tracking Manager - Prestige Production
===========================================

This script manages email tracking services:
1. Starts/stops the tracking server
2. Syncs tracking data with Google Sheets
3. Provides tracking statistics

Usage:
    python tracking_manager.py start    # Start tracking server
    python tracking_manager.py stop     # Stop tracking server
    python tracking_manager.py sync     # Sync tracking data to Google Sheets
    python tracking_manager.py stats    # Show tracking statistics
"""

import sys
import os
import json
import time
import sqlite3
import subprocess
import threading
from datetime import datetime, timedelta
from pathlib import Path

# Add current directory to path to import local modules
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

try:
    from email_tracker import start_tracking_server, init_database, DB_PATH
    from google_sheets_updater import update_tracking_stats_batch
    TRACKING_AVAILABLE = True
except ImportError:
    TRACKING_AVAILABLE = False

# PID file for tracking server
PID_FILE = '/tmp/email_tracking_server.pid'

def start_tracking_service():
    """Start the email tracking server"""
    if not TRACKING_AVAILABLE:
        print("❌ Tracking modules not available")
        return False
    
    # Check if server is already running
    if is_server_running():
        print("⚠️  Tracking server is already running")
        return True
    
    print("🚀 Starting email tracking server...")
    
    # Initialize database
    init_database()
    
    # Start server in background
    try:
        # Create a daemon process for the server
        script_path = os.path.join(os.path.dirname(__file__), 'email_tracker.py')
        server_process = subprocess.Popen([
            sys.executable, script_path
        ], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        
        # Save PID
        with open(PID_FILE, 'w') as f:
            f.write(str(server_process.pid))
        
        # Wait a moment to see if server started successfully
        time.sleep(3)
        
        if server_process.poll() is None:
            print("✅ Email tracking server started successfully")
            print(f"📊 Dashboard: http://localhost:5000/dashboard")
            print(f"🔍 API: http://localhost:5000/api/stats")
            print(f"📝 PID: {server_process.pid}")
            return True
        else:
            print("❌ Failed to start tracking server")
            # Print error details
            stdout, stderr = server_process.communicate()
            print(f"❌ Exit code: {server_process.returncode}")
            print(f"❌ STDOUT: {stdout.decode()}")
            print(f"❌ STDERR: {stderr.decode()}")
            return False
            
    except Exception as e:
        print(f"❌ Error starting tracking server: {e}")
        return False

def stop_tracking_service():
    """Stop the email tracking server"""
    if not os.path.exists(PID_FILE):
        print("⚠️  No tracking server PID file found")
        return True
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Try to kill the process
        os.kill(pid, 9)  # SIGKILL
        
        # Remove PID file
        os.remove(PID_FILE)
        
        print("✅ Email tracking server stopped")
        return True
        
    except ProcessLookupError:
        print("⚠️  Process not found (already stopped)")
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return True
    except Exception as e:
        print(f"❌ Error stopping tracking server: {e}")
        return False

def is_server_running():
    """Check if the tracking server is running"""
    if not os.path.exists(PID_FILE):
        return False
    
    try:
        with open(PID_FILE, 'r') as f:
            pid = int(f.read().strip())
        
        # Check if process is running
        os.kill(pid, 0)  # Signal 0 just checks if process exists
        return True
        
    except (ProcessLookupError, ValueError):
        # Process doesn't exist
        if os.path.exists(PID_FILE):
            os.remove(PID_FILE)
        return False

def sync_tracking_data():
    """Sync tracking data from SQLite to Google Sheets"""
    if not TRACKING_AVAILABLE:
        print("❌ Tracking modules not available")
        return False
    
    if not os.path.exists(DB_PATH):
        print("❌ No tracking database found")
        return False
    
    print("📊 Syncing tracking data to Google Sheets...")
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get all tracking data
        cursor.execute('''
            SELECT client_name, client_email, open_count, click_count, 
                   bounce_date, sent_date, opened_date, clicked_date
            FROM email_tracking
            ORDER BY sent_date DESC
        ''')
        
        tracking_data = cursor.fetchall()
        conn.close()
        
        if not tracking_data:
            print("ℹ️  No tracking data to sync")
            return True
        
        # Prepare data for batch update
        sync_data = []
        for row in tracking_data:
            sync_data.append({
                'client_name': row[0],
                'client_email': row[1],
                'opens': row[2],
                'clicks': row[3],
                'bounced': row[4] is not None,
                'sent_date': row[5],
                'opened_date': row[6],
                'clicked_date': row[7]
            })
        
        # Batch update Google Sheets
        success_count = update_tracking_stats_batch(sync_data)
        
        print(f"✅ Synced {success_count}/{len(sync_data)} tracking records")
        return True
        
    except Exception as e:
        print(f"❌ Error syncing tracking data: {e}")
        return False

def show_tracking_stats():
    """Show tracking statistics"""
    if not TRACKING_AVAILABLE:
        print("❌ Tracking modules not available")
        return False
    
    if not os.path.exists(DB_PATH):
        print("❌ No tracking database found")
        return False
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get overall statistics
        cursor.execute('''
            SELECT 
                COUNT(*) as total_sent,
                COUNT(opened_date) as total_opened,
                COUNT(clicked_date) as total_clicked,
                COUNT(bounce_date) as total_bounced,
                SUM(open_count) as total_opens,
                SUM(click_count) as total_clicks,
                MIN(sent_date) as first_sent,
                MAX(sent_date) as last_sent
            FROM email_tracking
        ''')
        
        stats = cursor.fetchone()
        
        # Get recent activity (last 7 days)
        cursor.execute('''
            SELECT 
                COUNT(*) as recent_sent,
                COUNT(opened_date) as recent_opened,
                COUNT(clicked_date) as recent_clicked
            FROM email_tracking
            WHERE sent_date > datetime('now', '-7 days')
        ''')
        
        recent_stats = cursor.fetchone()
        
        conn.close()
        
        print("📊 Email Tracking Statistics")
        print("=" * 40)
        print(f"📧 Total Emails Sent: {stats[0]}")
        print(f"👀 Total Opened: {stats[1]} ({stats[4]} total opens)")
        print(f"🖱️  Total Clicked: {stats[2]} ({stats[5]} total clicks)")
        print(f"❌ Total Bounced: {stats[3]}")
        print()
        
        if stats[0] > 0:
            open_rate = (stats[1] / stats[0]) * 100
            click_rate = (stats[2] / stats[0]) * 100
            bounce_rate = (stats[3] / stats[0]) * 100
            
            print(f"📈 Open Rate: {open_rate:.1f}%")
            print(f"📈 Click Rate: {click_rate:.1f}%")
            print(f"📈 Bounce Rate: {bounce_rate:.1f}%")
            print()
        
        print("🕒 Recent Activity (Last 7 Days)")
        print("-" * 30)
        print(f"📧 Sent: {recent_stats[0]}")
        print(f"👀 Opened: {recent_stats[1]}")
        print(f"🖱️  Clicked: {recent_stats[2]}")
        print()
        
        if stats[6] and stats[7]:
            print(f"📅 Campaign Period: {stats[6][:19]} to {stats[7][:19]}")
        
        print(f"🔍 Server Status: {'Running' if is_server_running() else 'Stopped'}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error getting tracking stats: {e}")
        return False

def main():
    """Main function"""
    if len(sys.argv) < 2:
        print("Usage: python tracking_manager.py <command>")
        print("Commands:")
        print("  start  - Start tracking server")
        print("  stop   - Stop tracking server")
        print("  sync   - Sync tracking data to Google Sheets")
        print("  stats  - Show tracking statistics")
        return
    
    command = sys.argv[1].lower()
    
    if command == 'start':
        start_tracking_service()
    elif command == 'stop':
        stop_tracking_service()
    elif command == 'sync':
        sync_tracking_data()
    elif command == 'stats':
        show_tracking_stats()
    else:
        print(f"❌ Unknown command: {command}")

if __name__ == "__main__":
    main() 