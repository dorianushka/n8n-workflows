import discord
import asyncio
import os
import json
import sys
from datetime import datetime
import subprocess
from dotenv import load_dotenv
from io import BytesIO
import tempfile
from pathlib import Path

# Load environment variables
load_dotenv()

# Discord configuration
import os
BOT_TOKEN = os.getenv('BOT_TOKEN')
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

CHANNEL_ID_STR = os.getenv('CHANNEL_ID')
if not CHANNEL_ID_STR:
    raise ValueError("CHANNEL_ID environment variable is required")
CHANNEL_ID = int(CHANNEL_ID_STR)

# Reaction emojis
APPROVE_EMOJI = "👍"
REJECT_EMOJI = "👎"
TIMEOUT_SECONDS = 86400  # 24 hours timeout for approval

# Import the template function from send_email module
from send_email import create_client_email_template

def create_email_preview_file(client_data):
    """
    Create an HTML file with email preview for Discord attachment
    
    Args:
        client_data (dict): Client information from Excel
    
    Returns:
        tuple: (file_content_bytes, filename)
    """
    subject, text_body, html_body = create_client_email_template(client_data)
    
    # Create a comprehensive preview HTML file
    preview_html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Email Preview - {client_data.get('Name', 'Client')}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 0;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .preview-container {{
            max-width: 800px;
            margin: 0 auto;
            background-color: white;
            border-radius: 10px;
            overflow: hidden;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .preview-header {{
            background-color: #34495e;
            color: white;
            padding: 20px;
            text-align: center;
        }}
        .email-info {{
            background-color: #ecf0f1;
            padding: 15px;
            border-bottom: 1px solid #bdc3c7;
        }}
        .email-info strong {{
            color: #2c3e50;
        }}
        .email-content {{
            padding: 0;
        }}
        .text-version {{
            background-color: #f8f9fa;
            padding: 20px;
            border-bottom: 1px solid #e9ecef;
        }}
        .text-version h3 {{
            margin-top: 0;
            color: #495057;
        }}
        .text-version pre {{
            background-color: white;
            padding: 15px;
            border-radius: 5px;
            border-left: 4px solid #6c757d;
            white-space: pre-wrap;
            font-family: monospace;
        }}
        .html-version {{
            padding: 20px;
        }}
        .html-version h3 {{
            margin-top: 0;
            color: #495057;
        }}
    </style>
</head>
<body>
    <div class="preview-container">
        <div class="preview-header">
            <h1>📧 Email Preview</h1>
            <p>Prestige Production - Client Outreach</p>
            <p><em>Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</em></p>
        </div>
        
        <div class="email-info">
            <p><strong>To:</strong> {client_data.get('Name', 'Unknown')} &lt;{client_data.get('Email', 'unknown@example.com')}&gt;</p>
            <p><strong>From:</strong> Dorian - Prestige Production &lt;dorian@prestigeproduction.ch&gt;</p>
            <p><strong>Subject:</strong> {subject}</p>
            <p><strong>Company:</strong> {client_data.get('Company', 'Not specified')}</p>
        </div>
        
        <div class="email-content">
            <div class="text-version">
                <h3>📝 Plain Text Version</h3>
                <pre>{text_body}</pre>
            </div>
            
            <div class="html-version">
                <h3>🎨 HTML Version (How it will appear)</h3>
                <div style="border: 2px solid #e9ecef; border-radius: 5px; overflow: hidden;">
                    {html_body}
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""
    
    # Generate filename
    client_name = client_data.get('Name', 'Unknown').replace(' ', '_')
    filename = f"email_preview_{client_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
    
    return preview_html.encode('utf-8'), filename

def create_client_approval_message(client_data):
    """
    Create a Discord message for client approval
    
    Args:
        client_data (dict): Client information from Excel
    
    Returns:
        discord.Embed: Formatted message embed
    """
    # Get email subject for preview
    subject, _, _ = create_client_email_template(client_data)
    
    embed = discord.Embed(
        title="📧 Client Email Approval Required",
        description=f"**Subject:** {subject}\n\n📎 Email preview is attached - download to see exactly how it will look!",
        color=0x3498db,
        timestamp=datetime.utcnow()
    )
    
    # Add client information
    embed.add_field(
        name="👤 Client Name",
        value=client_data.get('Name', 'Not provided'),
        inline=True
    )
    
    embed.add_field(
        name="📧 Email",
        value=client_data.get('Email', 'Not provided'),
        inline=True
    )
    
    embed.add_field(
        name="🏢 Company",
        value=client_data.get('Company', 'Not provided'),
        inline=True
    )
    
    # Add additional fields if available
    if 'Phone' in client_data and client_data['Phone']:
        embed.add_field(
            name="📞 Phone",
            value=client_data['Phone'],
            inline=True
        )
    
    if 'Industry' in client_data and client_data['Industry']:
        embed.add_field(
            name="🏭 Industry",
            value=client_data['Industry'],
            inline=True
        )
    
    embed.add_field(
        name="📋 Instructions",
        value=f"📎 **Email preview is attached** - Download to see how it will look\n\n{APPROVE_EMOJI} **Approve** - Send the email immediately\n{REJECT_EMOJI} **Reject** - Skip this client\n\n⏰ **You have 24 hours to respond** - No rush!",
        inline=False
    )
    
    embed.set_footer(text="Prestige Production • Client Outreach System")
    
    return embed

async def request_client_approval(client_data):
    """
    Send client information to Discord and wait for approval
    
    Args:
        client_data (dict): Client information from Excel
    
    Returns:
        dict: Approval result
    """
    # Set up Discord client with necessary intents
    intents = discord.Intents.default()
    intents.message_content = True
    intents.reactions = True
    
    client = discord.Client(intents=intents)
    
    approval_result = {"approved": False, "error": None}
    
    @client.event
    async def on_ready():
        print(f'✅ Bot logged in as {client.user}')
        
        try:
            # Get the channel
            channel = client.get_channel(CHANNEL_ID)
            if not channel:
                approval_result["error"] = f"Channel with ID {CHANNEL_ID} not found!"
                await client.close()
                return
            
            # Check if it's a text channel that can receive messages
            if not isinstance(channel, (discord.TextChannel, discord.DMChannel)):
                approval_result["error"] = f"Channel {CHANNEL_ID} is not a text channel!"
                await client.close()
                return
            
            # Create email preview file
            print("📎 Generating email preview...")
            preview_content, preview_filename = create_email_preview_file(client_data)
            preview_file = discord.File(BytesIO(preview_content), filename=preview_filename)
            
            # Create and send approval message with email preview
            embed = create_client_approval_message(client_data)
            message = await channel.send(
                embed=embed,
                file=preview_file
            )
            
            # Add reaction buttons
            await message.add_reaction(APPROVE_EMOJI)
            await message.add_reaction(REJECT_EMOJI)
            
            print(f"📤 Approval request sent for {client_data.get('Name', 'Unknown')}")
            print(f"📎 Email preview attached: {preview_filename}")
            print(f"⏱️  Waiting for approval (timeout: 24 hours)...")
            print(f"💡 You have 24 hours to respond - process at your own pace!")
            
            # Wait for reaction
            def check_reaction(reaction, user):
                return (
                    reaction.message.id == message.id and
                    str(reaction.emoji) in [APPROVE_EMOJI, REJECT_EMOJI] and
                    not user.bot
                )
            
            try:
                reaction, user = await client.wait_for(
                    'reaction_add',
                    timeout=TIMEOUT_SECONDS,
                    check=check_reaction
                )
                
                if str(reaction.emoji) == APPROVE_EMOJI:
                    approval_result["approved"] = True
                    approval_result["approved_by"] = str(user)
                    print(f"✅ Approved by {user}")
                    
                    # Update message to show approval
                    embed.color = 0x2ecc71  # Green
                    embed.set_field_at(
                        len(embed.fields) - 1,
                        name="✅ Status",
                        value=f"**APPROVED** by {user}\n📧 Email is being sent...",
                        inline=False
                    )
                    await message.edit(embed=embed)
                    
                elif str(reaction.emoji) == REJECT_EMOJI:
                    approval_result["approved"] = False
                    approval_result["rejected_by"] = str(user)
                    print(f"❌ Rejected by {user}")
                    
                    # Update message to show rejection
                    embed.color = 0xe74c3c  # Red
                    embed.set_field_at(
                        len(embed.fields) - 1,
                        name="❌ Status",
                        value=f"**REJECTED** by {user}\n🚫 Email will not be sent",
                        inline=False
                    )
                    await message.edit(embed=embed)
                    
            except asyncio.TimeoutError:
                approval_result["error"] = f"No response within 24 hours"
                print(f"⏰ Timeout: No response within 24 hours")
                
                # Update message to show timeout
                embed.color = 0x95a5a6  # Gray
                embed.set_field_at(
                    len(embed.fields) - 1,
                    name="⏰ Status",
                    value=f"**TIMEOUT** - No response within 24 hours\n🚫 Email will not be sent",
                    inline=False
                )
                await message.edit(embed=embed)
                
        except Exception as e:
            approval_result["error"] = str(e)
            print(f"❌ Error: {e}")
        
        await client.close()
    
    # Start the bot
    await client.start(BOT_TOKEN)  # type: ignore # Already validated above
    
    return approval_result

def main():
    """
    Main function to handle command line usage
    """
    try:
        print("🤖 Discord Approval Bot - Prestige Production")
        print("=" * 50)
        
        # Check if client data is passed as argument
        if len(sys.argv) < 2:
            print("❌ Error: Client data required")
            print("Usage: python discord_api_message_send.py '<client_json_data>'")
            sys.exit(1)
        
        # Parse client data
        client_json = sys.argv[1]
        client_data = json.loads(client_json)
        
        # Validate required fields
        if 'Email' not in client_data or not client_data['Email']:
            print("❌ Error: Client email address is required")
            sys.exit(1)
        
        print(f"📤 Requesting approval for: {client_data.get('Name', 'Unknown')} ({client_data.get('Email', 'Unknown')})")
        
        # Request approval
        result = asyncio.run(request_client_approval(client_data))
        
        # Output result
        print("=== APPROVAL RESULT START ===")
        print(json.dumps(result, indent=2))
        print("=== APPROVAL RESULT END ===")
        
        if result.get("approved"):
            print("✅ Client approved for email outreach!")
            
            # If approved, call email sending script
            print("📧 Sending email...")
            email_result = subprocess.run([
                'python', 'scripts/send_email.py', client_json
            ], capture_output=True, text=True)
            
            if email_result.returncode == 0:
                print("✅ Email sent successfully!")
            else:
                print(f"❌ Email failed: {email_result.stderr}")
                
        elif result.get("error"):
            print(f"❌ Error: {result['error']}")
            sys.exit(1)
        else:
            print("❌ Client rejected or timed out")
            
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing client data: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        sys.exit(1)

# Run the main function
if __name__ == "__main__":
    main()
