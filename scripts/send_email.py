import smtplib
import os
import sys
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from datetime import datetime
import traceback
from pathlib import Path

# Import tracking and Google Sheets integration
try:
    from email_tracker import create_tracking_entry
    from google_sheets_updater import update_email_tracking
    TRACKING_ENABLED = True
except ImportError:
    TRACKING_ENABLED = False
    print("⚠️  Email tracking not available - emails will be sent without tracking")

# Email configuration
SENDER_EMAIL = "dorian@prestigeproduction.ch"
SENDER_NAME = "Dorian - Prestige Production"
CC_RECIPIENTS = ["alex@prestigeproduction.ch", "dorian@prestigeproduction.ch"]

# SMTP configuration (you'll need to set these in your .env)
SMTP_SERVER = os.getenv('SMTP_SERVER', 'smtp.hostinger.com')  # Default to Hostinger
SMTP_PORT = int(os.getenv('SMTP_PORT', '465'))  # Default to SSL port
SMTP_USERNAME = os.getenv('SMTP_USERNAME')  # Your email username
SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')  # Your email password/app password

def send_email(recipient_email, recipient_name, subject, body_text, body_html=None, enable_tracking=True):
    """
    Send an email to a client with optional tracking
    
    Args:
        recipient_email (str): Client's email address
        recipient_name (str): Client's name
        subject (str): Email subject
        body_text (str): Plain text body
        body_html (str, optional): HTML body
        enable_tracking (bool): Whether to enable email tracking
    
    Returns:
        dict: Success status, message, and tracking ID if enabled
    """
    try:
        # Validate required environment variables
        if not SMTP_USERNAME or not SMTP_PASSWORD:
            return {
                "success": False,
                "error": "SMTP credentials not configured. Please set SMTP_USERNAME and SMTP_PASSWORD environment variables."
            }
        
        # Generate tracking ID if tracking is enabled
        tracking_id = None
        if enable_tracking and TRACKING_ENABLED:
            tracking_id = create_tracking_entry(recipient_name, recipient_email)
            print(f"📊 Created tracking ID: {tracking_id}")
        
        # Create message
        message = MIMEMultipart('alternative')
        message['From'] = f"{SENDER_NAME} <{SENDER_EMAIL}>"
        message['To'] = f"{recipient_name} <{recipient_email}>"
        message['Cc'] = ', '.join(CC_RECIPIENTS)
        message['Subject'] = subject
        
        # Add plain text part
        text_part = MIMEText(body_text, 'plain')
        message.attach(text_part)
        
        # Add HTML part if provided
        if body_html:
            # Add tracking URLs to HTML if tracking is enabled
            if enable_tracking and TRACKING_ENABLED and tracking_id:
                # Get tracking server URL from environment or use localhost
                tracking_server = os.getenv('TRACKING_SERVER_URL', 'http://localhost:5000')
                
                # Add tracking pixel and click tracking URLs
                tracking_pixel_url = f"{tracking_server}/track/open/{tracking_id}"
                tracking_click_url = f"{tracking_server}/track/click/{tracking_id}"
                
                # Replace placeholders in HTML template
                body_html = body_html.replace('{tracking_pixel_url}', tracking_pixel_url)
                body_html = body_html.replace('{tracking_click_url}', tracking_click_url)
                
                print(f"📊 Added tracking URLs to email")
            else:
                # Remove tracking placeholders if tracking is disabled
                body_html = body_html.replace('{tracking_pixel_url}', '')
                body_html = body_html.replace('{tracking_click_url}', 'mailto:dorian@prestigeproduction.ch')
            
            html_part = MIMEText(body_html, 'html')
            message.attach(html_part)
        
        # Connect to server and send email
        print(f"📧 Connecting to SMTP server: {SMTP_SERVER}:{SMTP_PORT}")
        if SMTP_PORT == 465:
            # Use SSL for port 465
            server = smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT)
        else:
            # Use TLS for port 587
            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()  # Enable TLS encryption
        
        print("🔐 Authenticating with SMTP server...")
        server.login(SMTP_USERNAME, SMTP_PASSWORD)
        
        print(f"📤 Sending email to {recipient_email}...")
        print(f"📧 CC: {', '.join(CC_RECIPIENTS)}")
        
        # Send to all recipients (TO + CC)
        all_recipients = [recipient_email] + CC_RECIPIENTS
        server.send_message(message, to_addrs=all_recipients)
        server.quit()
        
        # Update Google Sheets after successful email send
        if enable_tracking and TRACKING_ENABLED:
            print(f"📊 Updating Google Sheets for {recipient_name}...")
            update_email_tracking(recipient_email, recipient_name)
        
        return {
            "success": True,
            "tracking_id": tracking_id if enable_tracking and TRACKING_ENABLED else None,
            "message": f"Email sent successfully to {recipient_email}",
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

def create_client_email_template(client_data):
    """
    Create a professional email template for client outreach
    
    Args:
        client_data (dict): Client information from Excel
    
    Returns:
        tuple: (subject, text_body, html_body)
    """
    
    # Extract client information
    client_name = client_data.get('Name', 'Valued Client')
    company = client_data.get('Company', '')
    
    # Create subject
    subject = f"Partnership Opportunity - Prestige Production"
    
    # Create text body
    text_body = f"""Hello {client_name},

I hope this message finds you well.

I'm reaching out from Prestige Production to explore potential partnership opportunities with {'your company' if not company else company}.

We specialize in high-quality production services and believe there could be great synergy between our organizations. Our team has extensive experience in:

• Video Production & Post-Production
• Audio Engineering & Sound Design
• Creative Content Development
• Brand Strategy & Marketing

Would you be interested in a brief conversation to discuss how we might collaborate? I'd love to learn more about your current projects and explore potential synergies.

We're always excited to work with innovative companies and would love to explore how we can support your goals.

Best regards,
Dorian
Prestige Production
dorian@prestigeproduction.ch

---
This email was sent as part of our client outreach program. If you'd prefer not to receive future communications, please reply with "UNSUBSCRIBE" in the subject line.
"""

    # Load HTML template from file
    try:
        template_path = Path(__file__).parent / "email_template.html"
        with open(template_path, 'r', encoding='utf-8') as f:
            html_template = f.read()
        
        # Format the template with client data
        company_text = 'your organization' if not company else f'<strong>{company}</strong>'
        
        html_body = html_template.format(
            subject=subject,
            client_name=client_name,
            company_text=company_text
        )
        
        print(f"✅ Loaded email template from {template_path}")
        
    except Exception as e:
        print(f"⚠️  Warning: Could not load HTML template: {e}")
        print("📧 Using fallback HTML template")
        
        # Fallback HTML template
        html_body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333;">
            <div style="max-width: 600px; margin: 0 auto; padding: 20px;">
                <h2 style="color: #2c3e50;">Hello {client_name},</h2>
                
                <p>I hope this message finds you well.</p>
                
                <p>I'm reaching out from <strong>Prestige Production</strong> to explore potential partnership opportunities with {'your organization' if not company else f'<strong>{company}</strong>'}.</p>
                
                <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #007bff; margin: 20px 0;">
                    <p><strong>About Prestige Production:</strong></p>
                    <p>We specialize in high-quality production services and believe there could be great synergy between our organizations.</p>
                </div>
                
                <p>Would you be interested in a brief conversation to discuss how we might collaborate?</p>
                
                <div style="margin-top: 30px; padding-top: 20px; border-top: 1px solid #eee;">
                    <p><strong>Best regards,</strong><br>
                    Dorian<br>
                    Prestige Production<br>
                    <a href="mailto:dorian@prestigeproduction.ch">dorian@prestigeproduction.ch</a></p>
                </div>
                
                <p style="font-size: 12px; color: #666; margin-top: 20px;">
                    This email was sent as part of our client outreach program.
                </p>
            </div>
        </body>
        </html>
        """
    
    return subject, text_body, html_body

def main():
    """
    Main function to handle command line usage
    """
    try:
        print("📧 Email Sending Script - Prestige Production")
        print("=" * 50)
        
        # Check if client data is passed as argument
        if len(sys.argv) < 2:
            print("❌ Error: Client data required")
            print("Usage: python send_email.py '<client_json_data>'")
            sys.exit(1)
        
        # Parse client data
        client_json = sys.argv[1]
        client_data = json.loads(client_json)
        
        # Validate required fields
        if 'Email' not in client_data or not client_data['Email']:
            print("❌ Error: Client email address is required")
            sys.exit(1)
        
        recipient_email = client_data['Email']
        recipient_name = client_data.get('Name', 'Valued Client')
        
        print(f"📧 Preparing email for: {recipient_name} ({recipient_email})")
        
        # Create email template
        subject, text_body, html_body = create_client_email_template(client_data)
        
        # Send email
        result = send_email(recipient_email, recipient_name, subject, text_body, html_body)
        
        # Output result
        print("=== EMAIL RESULT START ===")
        print(json.dumps(result, indent=2))
        print("=== EMAIL RESULT END ===")
        
        if result['success']:
            print("✅ Email sent successfully!")
            sys.exit(0)
        else:
            print(f"❌ Email failed: {result['error']}")
            sys.exit(1)
            
    except json.JSONDecodeError as e:
        print(f"❌ Error parsing client data: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        print("📋 Full traceback:")
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()