#!/usr/bin/env python3
"""
Email Tracking Service - Prestige Production
===========================================

This Flask web service provides:
1. Email open tracking (tracking pixel)
2. Email click tracking (wrapped links)
3. Bounce tracking integration
4. Web dashboard for tracking reports

Usage: python email_tracker.py
Access dashboard at: http://localhost:5000/dashboard
"""

from flask import Flask, request, redirect, render_template_string, jsonify, send_file
import sqlite3
import uuid
import os
import json
from datetime import datetime
from werkzeug.serving import make_server
import threading
import time
from pathlib import Path

app = Flask(__name__)

# Database setup
DB_PATH = 'email_tracking.db'

def init_database():
    """Initialize the tracking database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create tracking table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS email_tracking (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tracking_id TEXT UNIQUE NOT NULL,
            client_name TEXT NOT NULL,
            client_email TEXT NOT NULL,
            sent_date DATETIME NOT NULL,
            opened_date DATETIME,
            clicked_date DATETIME,
            bounce_date DATETIME,
            open_count INTEGER DEFAULT 0,
            click_count INTEGER DEFAULT 0,
            user_agent TEXT,
            ip_address TEXT,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    conn.close()
    print("📊 Email tracking database initialized")

def create_tracking_entry(client_name, client_email):
    """Create a new tracking entry and return tracking ID"""
    tracking_id = str(uuid.uuid4())
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        INSERT INTO email_tracking (tracking_id, client_name, client_email, sent_date)
        VALUES (?, ?, ?, ?)
    ''', (tracking_id, client_name, client_email, datetime.now()))
    
    conn.commit()
    conn.close()
    
    return tracking_id

def update_tracking_event(tracking_id, event_type, user_agent=None, ip_address=None):
    """Update tracking event in database"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    if event_type == 'open':
        cursor.execute('''
            UPDATE email_tracking 
            SET opened_date = ?, open_count = open_count + 1, user_agent = ?, ip_address = ?
            WHERE tracking_id = ?
        ''', (datetime.now(), user_agent, ip_address, tracking_id))
    elif event_type == 'click':
        cursor.execute('''
            UPDATE email_tracking 
            SET clicked_date = ?, click_count = click_count + 1, user_agent = ?, ip_address = ?
            WHERE tracking_id = ?
        ''', (datetime.now(), user_agent, ip_address, tracking_id))
    elif event_type == 'bounce':
        cursor.execute('''
            UPDATE email_tracking 
            SET bounce_date = ?
            WHERE tracking_id = ?
        ''', (datetime.now(), tracking_id))
    
    conn.commit()
    conn.close()

@app.route('/track/open/<tracking_id>')
def track_open(tracking_id):
    """Track email opens with 1x1 pixel"""
    user_agent = request.headers.get('User-Agent', '')
    ip_address = request.remote_addr
    
    update_tracking_event(tracking_id, 'open', user_agent, ip_address)
    
    # Return 1x1 transparent GIF
    pixel_data = b'\x47\x49\x46\x38\x39\x61\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00\x21\xf9\x04\x01\x00\x00\x00\x00\x2c\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02\x04\x01\x00\x3b'
    
    return pixel_data, 200, {
        'Content-Type': 'image/gif',
        'Cache-Control': 'no-cache, no-store, must-revalidate',
        'Pragma': 'no-cache',
        'Expires': '0'
    }

@app.route('/track/click/<tracking_id>')
def track_click(tracking_id):
    """Track email clicks and redirect to target URL"""
    user_agent = request.headers.get('User-Agent', '')
    ip_address = request.remote_addr
    target_url = request.args.get('url', 'https://prestigeproduction.ch')
    
    update_tracking_event(tracking_id, 'click', user_agent, ip_address)
    
    return redirect(target_url, code=302)

@app.route('/track/bounce/<tracking_id>')
def track_bounce(tracking_id):
    """Track email bounces (called by email service)"""
    update_tracking_event(tracking_id, 'bounce')
    return jsonify({'status': 'success'})

@app.route('/dashboard')
def dashboard():
    """Main tracking dashboard"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Get all tracking data
    cursor.execute('''
        SELECT tracking_id, client_name, client_email, sent_date, opened_date, clicked_date, 
               bounce_date, open_count, click_count
        FROM email_tracking
        ORDER BY sent_date DESC
    ''')
    
    tracking_data = cursor.fetchall()
    
    # Get summary statistics
    cursor.execute('''
        SELECT 
            COUNT(*) as total_sent,
            COUNT(opened_date) as total_opened,
            COUNT(clicked_date) as total_clicked,
            COUNT(bounce_date) as total_bounced,
            ROUND(AVG(open_count), 2) as avg_opens,
            ROUND(AVG(click_count), 2) as avg_clicks
        FROM email_tracking
    ''')
    
    stats = cursor.fetchone()
    conn.close()
    
    return render_template_string(DASHBOARD_TEMPLATE, 
                                tracking_data=tracking_data, 
                                stats=stats)

@app.route('/api/stats')
def api_stats():
    """API endpoint for tracking statistics"""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT 
            COUNT(*) as total_sent,
            COUNT(opened_date) as total_opened,
            COUNT(clicked_date) as total_clicked,
            COUNT(bounce_date) as total_bounced,
            ROUND(100.0 * COUNT(opened_date) / COUNT(*), 1) as open_rate,
            ROUND(100.0 * COUNT(clicked_date) / COUNT(*), 1) as click_rate
        FROM email_tracking
    ''')
    
    stats = cursor.fetchone()
    conn.close()
    
    return jsonify({
        'total_sent': stats[0],
        'total_opened': stats[1],
        'total_clicked': stats[2],
        'total_bounced': stats[3],
        'open_rate': stats[4],
        'click_rate': stats[5]
    })

# Dashboard HTML template
DASHBOARD_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>Email Tracking Dashboard - Prestige Production</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background-color: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { background: #2c3e50; color: white; padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: white; padding: 20px; border-radius: 10px; text-align: center; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        .stat-number { font-size: 2em; font-weight: bold; color: #2c3e50; }
        .stat-label { color: #7f8c8d; margin-top: 5px; }
        .table-container { background: white; border-radius: 10px; overflow: hidden; box-shadow: 0 2px 5px rgba(0,0,0,0.1); }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background-color: #34495e; color: white; }
        tr:hover { background-color: #f8f9fa; }
        .status { padding: 4px 8px; border-radius: 4px; font-size: 0.8em; }
        .opened { background-color: #d4edda; color: #155724; }
        .clicked { background-color: #cce5ff; color: #004085; }
        .bounced { background-color: #f8d7da; color: #721c24; }
        .pending { background-color: #fff3cd; color: #856404; }
        .refresh-btn { 
            background: #3498db; color: white; padding: 10px 20px; border: none; 
            border-radius: 5px; cursor: pointer; margin-bottom: 20px;
        }
        .refresh-btn:hover { background: #2980b9; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Email Tracking Dashboard</h1>
            <p>Prestige Production - Real-time Email Campaign Analytics</p>
        </div>
        
        <button class="refresh-btn" onclick="location.reload()">🔄 Refresh Data</button>
        
        <div class="stats">
            <div class="stat-card">
                <div class="stat-number">{{ stats[0] }}</div>
                <div class="stat-label">Emails Sent</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats[1] }}</div>
                <div class="stat-label">Opened</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats[2] }}</div>
                <div class="stat-label">Clicked</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ stats[3] }}</div>
                <div class="stat-label">Bounced</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.1f"|format((stats[1] / stats[0] * 100) if stats[0] > 0 else 0) }}%</div>
                <div class="stat-label">Open Rate</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ "%.1f"|format((stats[2] / stats[0] * 100) if stats[0] > 0 else 0) }}%</div>
                <div class="stat-label">Click Rate</div>
            </div>
        </div>
        
        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Client Name</th>
                        <th>Email</th>
                        <th>Sent Date</th>
                        <th>Status</th>
                        <th>Opens</th>
                        <th>Clicks</th>
                        <th>Last Activity</th>
                    </tr>
                </thead>
                <tbody>
                    {% for row in tracking_data %}
                    <tr>
                        <td>{{ row[1] }}</td>
                        <td>{{ row[2] }}</td>
                        <td>{{ row[3][:19] if row[3] else '' }}</td>
                        <td>
                            {% if row[6] %}
                                <span class="status bounced">Bounced</span>
                            {% elif row[5] %}
                                <span class="status clicked">Clicked</span>
                            {% elif row[4] %}
                                <span class="status opened">Opened</span>
                            {% else %}
                                <span class="status pending">Pending</span>
                            {% endif %}
                        </td>
                        <td>{{ row[7] }}</td>
                        <td>{{ row[8] }}</td>
                        <td>
                            {% if row[5] %}
                                {{ row[5][:19] }}
                            {% elif row[4] %}
                                {{ row[4][:19] }}
                            {% else %}
                                -
                            {% endif %}
                        </td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
    </div>
</body>
</html>
'''

def start_tracking_server():
    """Start the tracking server in a separate thread"""
    init_database()
    
    server = make_server('0.0.0.0', 5000, app)
    print("📊 Email tracking server starting on http://0.0.0.0:5000")
    print("📈 Dashboard available at: http://localhost:5000/dashboard")
    
    # Start server in a separate thread
    server_thread = threading.Thread(target=server.serve_forever)
    server_thread.daemon = True
    server_thread.start()
    
    return server

if __name__ == "__main__":
    # Start the tracking server
    server = start_tracking_server()
    
    print("🚀 Email Tracking Service Started!")
    print("📊 Dashboard: http://localhost:5000/dashboard")
    print("🔍 API Stats: http://localhost:5000/api/stats")
    print("Press Ctrl+C to stop...")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n⏹️  Stopping tracking server...") 