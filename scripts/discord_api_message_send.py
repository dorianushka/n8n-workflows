import discord
import asyncio
import os
from io import BytesIO

# Discord configuration
import os
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = int(os.getenv('CHANNEL_ID'))

# Create a simple HTML file content
html_content = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Simple HTML File</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f4f4f4;
        }
        .container {
            background-color: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        h1 {
            color: #333;
            text-align: center;
        }
        p {
            color: #666;
            line-height: 1.6;
        }
        .highlight {
            background-color: #e7f3ff;
            padding: 15px;
            border-left: 4px solid #007bff;
            margin: 20px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Hello from Discord Bot!</h1>
        <p>This is a simple HTML file sent as an attachment to Discord.</p>
        <div class="highlight">
            <p><strong>Note:</strong> This HTML file was generated and sent automatically by a Discord bot.</p>
        </div>
        <p>You can open this file in any web browser to view it properly.</p>
        <p>Generated on: <span id="timestamp"></span></p>
    </div>
    
    <script>
        document.getElementById('timestamp').textContent = new Date().toLocaleString();
    </script>
</body>
</html>"""

async def send_html_file():
    # Set up Discord client with necessary intents
    intents = discord.Intents.default()
    intents.message_content = True
    
    client = discord.Client(intents=intents)
    
    @client.event
    async def on_ready():
        print(f'Bot logged in as {client.user}')
        
        # Get the channel
        channel = client.get_channel(CHANNEL_ID)
        if not channel:
            print(f"Channel with ID {CHANNEL_ID} not found!")
            print("Make sure the bot has access to the server and channel.")
            await client.close()
            return
        
        # Check if it's a text channel that can receive messages
        if not isinstance(channel, (discord.TextChannel, discord.DMChannel)):
            print(f"Channel {CHANNEL_ID} is not a text channel!")
            await client.close()
            return
        
        # Create HTML file in memory as bytes
        html_bytes = html_content.encode('utf-8')
        html_file = BytesIO(html_bytes)
        
        # Create Discord file object
        discord_file = discord.File(html_file, filename="simple_page.html")
        
        # Send the file
        try:
            await channel.send("Here's your HTML file!", file=discord_file)
            print("HTML file sent successfully!")
        except discord.Forbidden:
            print("Bot doesn't have permission to send messages in this channel!")
        except discord.HTTPException as e:
            print(f"HTTP error sending file: {e}")
        except Exception as e:
            print(f"Error sending file: {e}")
        
        # Close the client
        await client.close()
    
    # Start the bot
    await client.start(BOT_TOKEN)

# Run the async function
if __name__ == "__main__":
    asyncio.run(send_html_file())
