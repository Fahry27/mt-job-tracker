import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

DIRECTORY = os.path.dirname(os.path.abspath(__file__))
CREDENTIALS_FILE = os.path.join(DIRECTORY, "service_account.json")
STATE_FILE = os.path.join(DIRECTORY, "data", "dashboard_state.json")
JOBS_FILE = os.path.join(DIRECTORY, "output", "latest", "jobs_ranked.csv")
SHEET_NAME = "MT Job Tracker Data" # The name of the Google Sheet

def sync_to_sheets():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"[{__file__}] service_account.json not found. Skipping Google Sheets sync.")
        return

    print(f"[{__file__}] Syncing data to Google Sheets...")
    
    scope = ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    
    try:
        creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        
        # Open or create sheet
        try:
            sheet = client.open_by_key("1dbbtGhqDMpxuIRUYm-1qS7ctAxP0PA9f_Q1COFuPcN8").sheet1
        except gspread.exceptions.SpreadsheetNotFound:
            print(f"[{__file__}] Sheet '{SHEET_NAME}' not found. Please create it or change SHEET_NAME.")
            return
            
        # Prepare data
        kanban_state = {}
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                kanban_state = json.load(f).get("kanban", {})
                
        # Read jobs from CSV
        rows = []
        if os.path.exists(JOBS_FILE):
            import csv
            with open(JOBS_FILE, "r", encoding="utf-8-sig") as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames + ["Status Kanban"]
                rows.append(headers)
                
                for row in reader:
                    # Determine ID to match kanban
                    job_id = "".join(e for e in str(row.get("Company", "") + row.get("Job Title", "") + row.get("Location", "")) if e.isalnum()).lower()
                    
                    # Exact slugify logic from dashboard JS
                    import re
                    def slugify(text):
                        return re.sub(r'[^a-z0-9]', '', str(text).lower())
                        
                    job_id = slugify(row.get("Company", "") + row.get("Job Title", "") + row.get("Location", ""))
                    
                    status = kanban_state.get(job_id, "Not Applied")
                    
                    row_data = [row.get(h, "") for h in reader.fieldnames]
                    row_data.append(status)
                    rows.append(row_data)
                    
        # Update sheet
        if rows:
            sheet.clear()
            sheet.update(values=rows, range_name='A1')
            print(f"[{__file__}] Successfully synced {len(rows)-1} jobs to Google Sheets.")
            
    except Exception as e:
        print(f"[{__file__}] Error syncing to sheets: {e}")

if __name__ == "__main__":
    sync_to_sheets()
