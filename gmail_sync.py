import os
import json
import re
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from telegram_agent import send_message
from config.notifications import TELEGRAM_CHAT_ID

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(DIRECTORY, "data", "dashboard_state.json")
JOBS_FILE = os.path.join(DIRECTORY, "output", "latest", "jobs_ranked.csv")
TOKEN_FILE = os.path.join(DIRECTORY, 'token.json')
CREDENTIALS_FILE = os.path.join(DIRECTORY, 'credentials.json')

def slugify(text):
    return re.sub(r'[^a-z0-9]', '', str(text).lower())

def sync_gmail_kanban():
    if not os.path.exists(CREDENTIALS_FILE) and not os.path.exists(TOKEN_FILE):
        print(f"[{__file__}] credentials.json not found. Skipping Gmail sync.")
        return

    creds = None
    if os.path.exists(TOKEN_FILE):
        creds = Credentials.from_authorized_user_file(TOKEN_FILE, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if not os.path.exists(CREDENTIALS_FILE):
                return
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, 'w') as token:
            token.write(creds.to_json())

    try:
        service = build('gmail', 'v1', credentials=creds)
        
        # Search for interview invitations in the last 7 days
        query = "subject:interview OR subject:assessment OR subject:invitation newer_than:7d"
        results = service.users().messages().list(userId='me', q=query).execute()
        messages = results.get('messages', [])

        if not messages:
            print(f"[{__file__}] No new interview/assessment emails found.")
            return

        # Load current Kanban state
        kanban_state = {}
        full_state = {"kanban": {}, "hidden": {}}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                full_state = json.load(f)
                kanban_state = full_state.get("kanban", {})

        # Load jobs
        jobs = []
        if os.path.exists(JOBS_FILE):
            import csv
            with open(JOBS_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    jobs.append({
                        "id": slugify(row.get("Company", "") + row.get("Job Title", "") + row.get("Location", "")),
                        "company": row.get("Company", "").lower(),
                        "title": row.get("Job Title", "")
                    })

        updated = 0
        for msg in messages:
            msg_data = service.users().messages().get(userId='me', id=msg['id'], format='metadata').execute()
            headers = msg_data.get('payload', {}).get('headers', [])
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "").lower()
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "").lower()

            # Determine if interview or assessment
            target_status = "assessment"
            if "interview" in subject:
                target_status = "interview"

            # Match company
            for job in jobs:
                if job["company"] in sender or job["company"] in subject:
                    current_status = kanban_state.get(job["id"])
                    
                    if current_status not in ["interview", "result"] and current_status != target_status:
                        # Update Kanban!
                        kanban_state[job["id"]] = target_status
                        full_state["kanban"] = kanban_state
                        
                        # Save
                        with open(STATE_FILE, "w") as f:
                            json.dump(full_state, f)
                            
                        # Notify
                        company_name = job["company"].title()
                        send_message(TELEGRAM_CHAT_ID, f"🔔 **AUTO-SYNC KANBAN**\n\nEmail undangan {target_status.upper()} dari **{company_name}** terdeteksi!\n\nKartu lamaran otomatis dipindahkan ke tahap {target_status.capitalize()}. Cek dashboard Anda!")
                        updated += 1
                        break
        
        print(f"[{__file__}] Gmail sync complete. {updated} jobs updated.")

    except Exception as e:
        print(f"[{__file__}] Error syncing Gmail: {e}")

if __name__ == '__main__':
    sync_gmail_kanban()
