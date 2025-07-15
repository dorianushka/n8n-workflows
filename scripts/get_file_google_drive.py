import os
import sys
import traceback
from dotenv import load_dotenv
import json
import base64

# Wrap everything in try-catch to capture all errors
try:
    print("🔍 Starting Google Drive script debug...")
    
    # Load environment variables
    load_dotenv()
    print("✓ Loaded .env file")
    
    # Check all environment variables
    print("🔍 Checking environment variables...")
    CLIENT_ID = os.getenv('CLIENT_ID')
    CLIENT_SECRET = os.getenv('CLIENT_SECRET')
    FILE_ID = os.getenv('FILE_ID')
    GOOGLE_TOKEN_JSON = os.getenv('GOOGLE_TOKEN_JSON')
    GOOGLE_TOKEN_JSON_BASE64 = os.getenv('GOOGLE_TOKEN_JSON_BASE64')
    
    print(f"CLIENT_ID: {'✓' if CLIENT_ID else '❌ Missing'}")
    print(f"CLIENT_SECRET: {'✓' if CLIENT_SECRET else '❌ Missing'}")
    print(f"FILE_ID: {'✓' if FILE_ID else '❌ Missing'}")
    print(f"GOOGLE_TOKEN_JSON: {'✓' if GOOGLE_TOKEN_JSON else '❌ Missing'}")
    print(f"GOOGLE_TOKEN_JSON_BASE64: {'✓' if GOOGLE_TOKEN_JSON_BASE64 else '❌ Missing'}")
    
    # Check if we have any token data
    if not GOOGLE_TOKEN_JSON and not GOOGLE_TOKEN_JSON_BASE64:
        print("❌ ERROR: No token data found!")
        print("Please set either GOOGLE_TOKEN_JSON or GOOGLE_TOKEN_JSON_BASE64")
        sys.exit(1)
    
    # Try to import Google libraries
    print("🔍 Importing Google libraries...")
    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaIoBaseDownload
        import io
        print("✓ Google libraries imported successfully")
    except ImportError as e:
        print(f"❌ ERROR importing Google libraries: {e}")
        sys.exit(1)
    
    # Try to import pandas
    print("🔍 Importing pandas...")
    try:
        import pandas as pd
        print("✓ Pandas imported successfully")
    except ImportError as e:
        print(f"❌ ERROR importing pandas: {e}")
        sys.exit(1)
    
    # Try to load credentials
    print("🔍 Loading credentials...")
    creds = None
    SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
    
    # Try regular JSON first
    if GOOGLE_TOKEN_JSON:
        try:
            token_data = json.loads(GOOGLE_TOKEN_JSON)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            print("✓ Loaded credentials from GOOGLE_TOKEN_JSON")
        except json.JSONDecodeError as e:
            print(f"❌ Invalid JSON in GOOGLE_TOKEN_JSON: {e}")
        except Exception as e:
            print(f"❌ Error loading credentials from GOOGLE_TOKEN_JSON: {e}")
    
    # Try base64 if regular JSON failed
    if not creds and GOOGLE_TOKEN_JSON_BASE64:
        try:
            decoded_json = base64.b64decode(GOOGLE_TOKEN_JSON_BASE64).decode('utf-8')
            token_data = json.loads(decoded_json)
            creds = Credentials.from_authorized_user_info(token_data, SCOPES)
            print("✓ Loaded credentials from GOOGLE_TOKEN_JSON_BASE64")
        except Exception as e:
            print(f"❌ Error loading base64 credentials: {e}")
    
    if not creds:
        print("❌ ERROR: Could not load any credentials!")
        sys.exit(1)
    
    # Try to build Google Drive service
    print("🔍 Building Google Drive service...")
    try:
        service = build('drive', 'v3', credentials=creds)
        print("✓ Google Drive service built successfully")
    except Exception as e:
        print(f"❌ Error building Google Drive service: {e}")
        sys.exit(1)
    
    # Try to download file
    print(f"🔍 Downloading file {FILE_ID}...")
    try:
        request = service.files().get_media(fileId=FILE_ID)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while not done:
            status, done = downloader.next_chunk()
        print("✓ File downloaded successfully")
    except Exception as e:
        print(f"❌ Error downloading file: {e}")
        sys.exit(1)
    
    # Try to read Excel
    print("🔍 Reading Excel file...")
    try:
        fh.seek(0)
        df = pd.read_excel(fh)
        print("✓ Excel file read successfully")
        print(f"DataFrame shape: {df.shape}")
        print(f"Columns: {list(df.columns)}")
        
        # Check if "Last Contacted" column exists
        if "Last Contacted" not in df.columns:
            print("⚠️  Warning: 'Last Contacted' column not found in Excel file")
            print(f"Available columns: {list(df.columns)}")
            contactable_clients = df
        else:
            # Filter clients where "Last Contacted" is empty/null
            print("🔍 Filtering clients with empty 'Last Contacted'...")
            contactable_clients = df[df["Last Contacted"].isna() | (df["Last Contacted"] == "")]
            
            print(f"✓ Found {len(contactable_clients)} clients that can be contacted")
            print(f"Total clients in file: {len(df)}")
        
        # Convert DataFrame to JSON
        print("🔍 Converting to JSON...")
        
        # Handle NaN values by replacing with None
        df_clean = contactable_clients.where(pd.notnull(contactable_clients), None)
        
        # Convert to JSON with records orientation (list of dictionaries)
        json_data = df_clean.to_json(orient='records', indent=2)
        
        # Parse back to Python object to ensure it's valid
        if json_data is None:
            raise ValueError("DataFrame conversion to JSON failed")
        data_dict = json.loads(json_data)
        
        # Create response object with metadata
        response = {
            "success": True,
            "metadata": {
                "total_rows": len(df),
                "total_columns": len(df.columns),
                "columns": list(df.columns),
                "file_id": FILE_ID,
                "contactable_clients": len(contactable_clients),
                "has_last_contacted_column": "Last Contacted" in df.columns
            },
            "data": data_dict
        }
        
        print("✓ JSON conversion successful")
        print("🎉 Script completed successfully!")
        
        # Output the final JSON for n8n to capture
        print("=== JSON OUTPUT START ===")
        print(json.dumps(response, indent=2))
        print("=== JSON OUTPUT END ===")
        
    except Exception as e:
        print(f"❌ Error reading Excel file: {e}")
        sys.exit(1)
    
except Exception as e:
    print(f"❌ FATAL ERROR: {e}")
    print("📋 Full traceback:")
    traceback.print_exc()
    sys.exit(1)