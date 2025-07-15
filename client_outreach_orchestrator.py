#!/usr/bin/env python3
"""
Client Outreach Orchestrator with Live Monitoring - Prestige Production
=======================================================================

This script orchestrates the entire client outreach workflow:
1. Fetches client data from Google Drive Excel file
2. Identifies clients with empty "Last Contacted" field
3. Sends ALL clients to Discord for approval simultaneously
4. Processes approvals as they come in (up to 24 hours each)
5. Sends approved emails immediately when approved
6. Provides live monitoring via Discord for you and Alex

Usage: python client_outreach_orchestrator.py
"""

import subprocess
import json
import sys
import time
import asyncio
from datetime import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading

# Import Discord monitoring
try:
    from scripts.discord_monitor import start_monitor, send_status, send_client_status, send_summary, stop_monitor
    MONITORING_ENABLED = True
except ImportError:
    print("⚠️  Discord monitoring not available - continuing without live monitoring")
    MONITORING_ENABLED = False

def run_script(script_path, *args):
    """
    Run a Python script and return the result
    
    Args:
        script_path (str): Path to the Python script
        *args: Arguments to pass to the script
    
    Returns:
        dict: Result containing stdout, stderr, and return code
    """
    try:
        cmd = ['python', script_path] + list(args)
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=86400)  # 24 hour timeout
        
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "return_code": result.returncode
        }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "stdout": "",
            "stderr": "Script timed out after 24 hours",
            "return_code": -1
        }
    except Exception as e:
        return {
            "success": False,
            "stdout": "",
            "stderr": str(e),
            "return_code": -1
        }

def extract_json_from_output(output):
    """
    Extract JSON data from script output between markers
    
    Args:
        output (str): Script output
    
    Returns:
        dict: Parsed JSON data or None if not found
    """
    try:
        start_marker = "=== JSON OUTPUT START ==="
        end_marker = "=== JSON OUTPUT END ==="
        
        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            json_str = output[start_idx + len(start_marker):end_idx].strip()
            return json.loads(json_str)
        
        # Try to find APPROVAL RESULT markers
        start_marker = "=== APPROVAL RESULT START ==="
        end_marker = "=== APPROVAL RESULT END ==="
        
        start_idx = output.find(start_marker)
        end_idx = output.find(end_marker)
        
        if start_idx != -1 and end_idx != -1:
            json_str = output[start_idx + len(start_marker):end_idx].strip()
            return json.loads(json_str)
        
        return None
    except json.JSONDecodeError:
        return None

def process_client_approval(client_data, client_index, total_clients, results_lock, shared_results):
    """
    Process a single client approval request
    
    Args:
        client_data (dict): Client information
        client_index (int): Index of client (1-based)
        total_clients (int): Total number of clients
        results_lock (threading.Lock): Lock for thread-safe results updates
        shared_results (dict): Shared results dictionary
    
    Returns:
        dict: Client processing result
    """
    client_name = client_data.get('Name', 'Unknown')
    client_email = client_data.get('Email', 'Unknown')
    
    print(f"🚀 [{client_index}/{total_clients}] Starting approval process for: {client_name} ({client_email})")
    
    # Send live monitoring update
    if MONITORING_ENABLED:
        send_client_status(client_name, client_email, "processing", f"Approval request sent to Discord")
    
    # Convert client data to JSON string for passing to script
    client_json_str = json.dumps(client_data)
    
    # Request approval via Discord (this will now wait up to 24 hours)
    discord_result = run_script('scripts/discord_api_message_send.py', client_json_str)
    
    client_result = {
        "client_name": client_name,
        "client_email": client_email,
        "client_data": client_data,
        "discord_result": discord_result,
        "timestamp": datetime.now().isoformat(),
        "client_index": client_index
    }
    
    if discord_result["success"]:
        # Extract approval result
        approval_data = extract_json_from_output(discord_result["stdout"])
        
        if approval_data and approval_data.get("approved"):
            print(f"✅ [{client_index}/{total_clients}] {client_name} - APPROVED and email sent!")
            if MONITORING_ENABLED:
                send_client_status(client_name, client_email, "approved", f"Email sent successfully")
            with results_lock:
                shared_results["approved"] += 1
            client_result["status"] = "approved_and_sent"
        elif approval_data and approval_data.get("error"):
            print(f"❌ [{client_index}/{total_clients}] {client_name} - ERROR: {approval_data['error']}")
            if MONITORING_ENABLED:
                send_client_status(client_name, client_email, "error", f"Error: {approval_data['error']}")
            with results_lock:
                shared_results["errors"] += 1
            client_result["status"] = "error"
            client_result["error"] = approval_data["error"]
        else:
            print(f"❌ [{client_index}/{total_clients}] {client_name} - REJECTED or TIMEOUT")
            if MONITORING_ENABLED:
                send_client_status(client_name, client_email, "rejected", f"User rejected or timed out")
            with results_lock:
                shared_results["rejected"] += 1
            client_result["status"] = "rejected"
    else:
        print(f"❌ [{client_index}/{total_clients}] {client_name} - SCRIPT ERROR: {discord_result['stderr']}")
        if MONITORING_ENABLED:
            send_client_status(client_name, client_email, "error", f"Script error: {discord_result['stderr']}")
        with results_lock:
            shared_results["errors"] += 1
        client_result["status"] = "script_error"
        client_result["error"] = discord_result["stderr"]
    
    with results_lock:
        shared_results["processed"] += 1
        shared_results["client_results"].append(client_result)
    
    return client_result

def main():
    """
    Main orchestrator function
    """
    start_time = datetime.now()
    
    print("🚀 Client Outreach Orchestrator - Prestige Production")
    print("=" * 60)
    print(f"Started at: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("📋 NEW: Parallel processing with 24-hour approval windows")
    print("🔍 LIVE: Discord monitoring for you and Alex")
    print()
    
    # Start Discord monitoring
    if MONITORING_ENABLED:
        print("🔍 Starting Discord monitoring...")
        start_monitor()
        send_status("🚀 Campaign Started", "Client outreach campaign is starting up", 0x00ff00)
    
    # Step 1: Fetch client data from Google Drive
    print("📥 Step 1: Fetching client data from Google Drive...")
    print("-" * 40)
    
    if MONITORING_ENABLED:
        send_status("📥 Fetching Data", "Loading client data from Google Drive", 0x3498db)
    
    google_drive_result = run_script('scripts/get_file_google_drive.py')
    
    if not google_drive_result["success"]:
        print("❌ Failed to fetch client data from Google Drive")
        print(f"Error: {google_drive_result['stderr']}")
        if MONITORING_ENABLED:
            send_status("❌ Data Fetch Failed", f"Error: {google_drive_result['stderr']}", 0xe74c3c)
        sys.exit(1)
    
    # Extract client data
    client_data_json = extract_json_from_output(google_drive_result["stdout"])
    
    if not client_data_json:
        print("❌ Failed to extract client data from Google Drive response")
        print("Raw output:", google_drive_result["stdout"])
        if MONITORING_ENABLED:
            send_status("❌ Data Parse Failed", "Could not parse client data from Google Drive", 0xe74c3c)
        sys.exit(1)
    
    clients = client_data_json.get("data", [])
    metadata = client_data_json.get("metadata", {})
    
    print(f"✅ Successfully fetched client data")
    print(f"   Total clients in file: {metadata.get('total_rows', 0)}")
    print(f"   Contactable clients: {metadata.get('contactable_clients', 0)}")
    print(f"   Columns: {metadata.get('columns', [])}")
    print()
    
    if MONITORING_ENABLED:
        send_status("✅ Data Loaded", f"Found {len(clients)} contactable clients", 0x2ecc71, [
            {"name": "📊 Total in file", "value": str(metadata.get('total_rows', 0)), "inline": True},
            {"name": "📧 Contactable", "value": str(len(clients)), "inline": True},
            {"name": "📋 Columns", "value": str(len(metadata.get('columns', []))), "inline": True}
        ])
    
    if not clients:
        print("ℹ️  No clients to contact at this time.")
        print("   All clients may have already been contacted.")
        if MONITORING_ENABLED:
            send_status("ℹ️  No Clients", "All clients have already been contacted", 0x95a5a6)
        sys.exit(0)
    
    # Step 2: Send ALL approval requests to Discord simultaneously
    print("🤖 Step 2: Sending ALL approval requests to Discord...")
    print("-" * 40)
    print(f"🚀 Starting {len(clients)} parallel approval processes")
    print("💡 Each client has 24 hours to be approved")
    print("⚡ Emails will be sent immediately when approved")
    print("🔍 Live monitoring available on Discord")
    print()
    
    if MONITORING_ENABLED:
        send_status("🤖 Starting Approvals", f"Sending {len(clients)} approval requests to Discord", 0x3498db, [
            {"name": "⏰ Timeout", "value": "24 hours per client", "inline": True},
            {"name": "⚡ Action", "value": "Immediate email on approval", "inline": True},
            {"name": "🔍 Monitoring", "value": "Live updates enabled", "inline": True}
        ])
    
    # Shared results dictionary (thread-safe)
    results_lock = threading.Lock()
    shared_results = {
        "total_clients": len(clients),
        "processed": 0,
        "approved": 0,
        "rejected": 0,
        "errors": 0,
        "client_results": []
    }
    
    # Process all clients in parallel using ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=len(clients)) as executor:
        # Submit all client approval tasks
        future_to_client = {
            executor.submit(
                process_client_approval, 
                client, 
                i + 1, 
                len(clients), 
                results_lock, 
                shared_results
            ): client
            for i, client in enumerate(clients)
        }
        
        print(f"🎯 All {len(clients)} approval requests sent to Discord!")
        print("⏳ Waiting for responses (up to 24 hours each)...")
        print("📊 Results will appear as they come in:")
        print("🔍 Live monitoring: Check Discord for real-time updates")
        print()
        
        # Process results as they complete
        for future in as_completed(future_to_client):
            client = future_to_client[future]
            try:
                result = future.result()
                # Result is already processed in the thread function
                # Just continue to next
                pass
            except Exception as exc:
                client_name = client.get('Name', 'Unknown')
                print(f"❌ Client {client_name} generated an exception: {exc}")
                if MONITORING_ENABLED:
                    send_client_status(client_name, client.get('Email', 'Unknown'), "error", f"Exception: {exc}")
                with results_lock:
                    shared_results["errors"] += 1
                    shared_results["processed"] += 1
    
    # Step 3: Generate final report
    print()
    print("📊 Step 3: Final Report")
    print("-" * 40)
    
    end_time = datetime.now()
    duration = end_time - start_time
    
    print(f"🎉 Outreach campaign completed!")
    print(f"   Duration: {duration}")
    print(f"   Total clients: {shared_results['total_clients']}")
    print(f"   Processed: {shared_results['processed']}")
    print(f"   Approved & Sent: {shared_results['approved']}")
    print(f"   Rejected: {shared_results['rejected']}")
    print(f"   Errors: {shared_results['errors']}")
    print()
    
    # Output detailed results as JSON
    final_results = shared_results.copy()
    final_results["start_time"] = start_time.isoformat()
    final_results["end_time"] = end_time.isoformat()
    final_results["duration_seconds"] = duration.total_seconds()
    final_results["metadata"] = metadata
    
    # Send final monitoring summary
    if MONITORING_ENABLED:
        send_summary(final_results)
    
    print("=== ORCHESTRATOR RESULTS START ===")
    print(json.dumps(final_results, indent=2))
    print("=== ORCHESTRATOR RESULTS END ===")
    
    # Stop monitoring
    if MONITORING_ENABLED:
        time.sleep(3)  # Give time for final messages to send
        stop_monitor()
    
    # Exit with appropriate code
    if final_results["errors"] > 0:
        sys.exit(1)
    else:
        sys.exit(0)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n⏹️  Orchestrator interrupted by user")
        if MONITORING_ENABLED:
            send_status("⏹️  Campaign Stopped", "User interrupted the campaign", 0xff9900)
            stop_monitor()
        sys.exit(130)
    except Exception as e:
        print(f"❌ Unexpected error in orchestrator: {e}")
        print("📋 Full traceback:")
        traceback.print_exc()
        if MONITORING_ENABLED:
            send_status("❌ Campaign Error", f"Unexpected error: {e}", 0xe74c3c)
            stop_monitor()
        sys.exit(1) 