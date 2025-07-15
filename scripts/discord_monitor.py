import discord
import asyncio
import os
import json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv
from io import BytesIO
import threading
import time

# Load environment variables
load_dotenv()

# Discord configuration
BOT_TOKEN = os.getenv('BOT_TOKEN')
MONITOR_CHANNEL_ID = int(os.getenv('MONITOR_CHANNEL_ID', os.getenv('CHANNEL_ID', 0)))

class DiscordMonitor:
    def __init__(self):
        self.intents = discord.Intents.default()
        self.intents.message_content = True
        self.client = discord.Client(intents=self.intents)
        self.channel = None
        self.is_connected = False
        self.message_queue = []
        self.lock = threading.Lock()
        
        @self.client.event
        async def on_ready():
            print(f'🔍 Monitor Bot connected as {self.client.user}')
            self.channel = self.client.get_channel(MONITOR_CHANNEL_ID)
            if self.channel:
                self.is_connected = True
                channel_name = getattr(self.channel, 'name', 'Unknown')
                print(f'📺 Monitoring channel: {channel_name}')
                
                # Send startup message
                await self.send_startup_message()
                
                # Process queued messages
                await self.process_message_queue()
            else:
                print(f'❌ Monitor channel {MONITOR_CHANNEL_ID} not found')
    
    async def send_startup_message(self):
        """Send a startup notification"""
        if not self.channel:
            return
            
        embed = discord.Embed(
            title="🚀 Client Outreach Monitor Started",
            description="Real-time monitoring of client outreach process",
            color=0x00ff00,
            timestamp=datetime.utcnow()
        )
        embed.add_field(
            name="🔍 Status",
            value="Monitor is now active and ready to track progress",
            inline=False
        )
        embed.set_footer(text="Prestige Production • Live Monitor")
        
        if self.channel:
            await self.channel.send(embed=embed)
    
    async def process_message_queue(self):
        """Process any queued messages"""
        with self.lock:
            for message_data in self.message_queue:
                try:
                    if message_data['type'] == 'embed':
                        await self.channel.send(embed=message_data['embed'])
                    elif message_data['type'] == 'message':
                        await self.channel.send(message_data['content'])
                except Exception as e:
                    print(f"❌ Error sending queued message: {e}")
            self.message_queue.clear()
    
    def queue_message(self, message_type, content=None, embed=None):
        """Queue a message to be sent when connected"""
        with self.lock:
            self.message_queue.append({
                'type': message_type,
                'content': content,
                'embed': embed
            })
    
    def send_status_update(self, title, description, color=0x3498db, fields=None):
        """Send a status update to Discord"""
        # Create CEST timezone (UTC+2)
        cest_tz = timezone(timedelta(hours=2))
        embed = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.now(cest_tz)
        )
        
        if fields:
            for field in fields:
                embed.add_field(
                    name=field['name'],
                    value=field['value'],
                    inline=field.get('inline', False)
                )
        
        embed.set_footer(text="Prestige Production • Live Monitor")
        
        # Always queue the message - it will be sent by the bot thread
        self.queue_message('embed', embed=embed)
    
    def send_client_update(self, client_name, client_email, status, details=None):
        """Send a client-specific update"""
        status_colors = {
            'processing': 0x3498db,  # Blue
            'approved': 0x2ecc71,   # Green
            'rejected': 0xe74c3c,   # Red
            'error': 0xf39c12,      # Orange
            'timeout': 0x95a5a6      # Gray
        }
        
        status_emojis = {
            'processing': '🔄',
            'approved': '✅',
            'rejected': '❌',
            'error': '⚠️',
            'timeout': '⏰'
        }
        
        color = status_colors.get(status, 0x3498db)
        emoji = status_emojis.get(status, '📧')
        
        embed = discord.Embed(
            title=f"{emoji} Client Update",
            description=f"**{client_name}** ({client_email})",
            color=color,
            timestamp=datetime.utcnow()
        )
        
        embed.add_field(
            name="📊 Status",
            value=status.upper(),
            inline=True
        )
        
        if details:
            embed.add_field(
                name="📝 Details",
                value=details,
                inline=False
            )
        
        embed.set_footer(text="Prestige Production • Client Monitor")
        
        # Always queue the message - it will be sent by the bot thread
        self.queue_message('embed', embed=embed)
    
    def send_summary_report(self, stats):
        """Send a summary report"""
        # Create CEST timezone (UTC+2)
        cest_tz = timezone(timedelta(hours=2))
        embed = discord.Embed(
            title="📊 Outreach Campaign Summary",
            description="Final results of the client outreach campaign",
            color=0x9b59b6,
            timestamp=datetime.now(cest_tz)
        )
        
        embed.add_field(
            name="📈 Total Processed",
            value=f"{stats.get('processed', 0)}/{stats.get('total_clients', 0)}",
            inline=True
        )
        
        embed.add_field(
            name="✅ Approved",
            value=str(stats.get('approved', 0)),
            inline=True
        )
        
        embed.add_field(
            name="❌ Rejected",
            value=str(stats.get('rejected', 0)),
            inline=True
        )
        
        embed.add_field(
            name="⚠️ Errors",
            value=str(stats.get('errors', 0)),
            inline=True
        )
        
        embed.add_field(
            name="⏱️ Duration",
            value=f"{stats.get('duration_seconds', 0):.1f}s",
            inline=True
        )
        
        success_rate = (stats.get('approved', 0) / max(stats.get('total_clients', 1), 1)) * 100
        embed.add_field(
            name="📊 Success Rate",
            value=f"{success_rate:.1f}%",
            inline=True
        )
        
        embed.set_footer(text="Prestige Production • Campaign Complete")
        
        # Always queue the message - it will be sent by the bot thread
        self.queue_message('embed', embed=embed)
    
    def start_monitoring(self):
        """Start the monitoring bot in a separate thread"""
        if not BOT_TOKEN:
            print("❌ BOT_TOKEN not configured")
            return None
            
        def run_bot():
            try:
                asyncio.run(self.client.start(BOT_TOKEN))  # type: ignore
            except Exception as e:
                print(f"❌ Monitor bot error: {e}")
        
        monitor_thread = threading.Thread(target=run_bot, daemon=True)
        monitor_thread.start()
        
        # Give the bot time to connect
        time.sleep(2)
        
        return monitor_thread
    
    def stop_monitoring(self):
        """Stop the monitoring bot"""
        if self.client:
            try:
                # Try to close gracefully if there's an event loop
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    asyncio.run_coroutine_threadsafe(self.client.close(), loop)
                else:
                    # No running loop, just mark as disconnected
                    self.is_connected = False
            except RuntimeError:
                # No event loop available, just mark as disconnected
                self.is_connected = False
            except Exception as e:
                print(f"⚠️  Error closing Discord client: {e}")
                self.is_connected = False

# Global monitor instance
monitor = DiscordMonitor()

def start_monitor():
    """Start the Discord monitor"""
    print("🔍 Starting Discord monitor...")
    return monitor.start_monitoring()

def send_status(title, description, color=0x3498db, fields=None):
    """Send a status update"""
    monitor.send_status_update(title, description, color, fields)

def send_client_status(client_name, client_email, status, details=None):
    """Send a client status update"""
    monitor.send_client_update(client_name, client_email, status, details)

def send_summary(stats):
    """Send a summary report"""
    monitor.send_summary_report(stats)

def stop_monitor():
    """Stop the monitor"""
    monitor.stop_monitoring()

if __name__ == "__main__":
    # Test the monitor
    print("🧪 Testing Discord Monitor...")
    start_monitor()
    
    # Send test messages
    time.sleep(3)
    send_status("🧪 Test Status", "This is a test message")
    send_client_status("John Doe", "john@example.com", "processing", "Testing client update")
    
    time.sleep(5)
    send_summary({
        'total_clients': 5,
        'processed': 5,
        'approved': 3,
        'rejected': 1,
        'errors': 1,
        'duration_seconds': 120.5
    })
    
    # Keep running
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Stopping monitor...")
        stop_monitor() 