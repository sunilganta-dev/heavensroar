import csv
import os
import json
import time
from twilio.rest import Client
from dotenv import load_dotenv
import gspread
from google.oauth2.service_account import Credentials

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
content_sid = "HXd8c5536a0bd9d414cebbc80ce933df40"

if not account_sid or not auth_token or not whatsapp_from:
    raise ValueError("Missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_WHATSAPP_FROM in environment.")

client = Client(account_sid, auth_token)

# =========================
# GOOGLE SHEETS SETUP
# =========================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]
CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "google_credentials.json")
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "HeavensRoar WhatsApp Logs")
BASE_URL = os.getenv("BASE_URL", "").strip().rstrip("/")

# Fetch template name from Twilio
print(f"🔍 Fetching template info for {content_sid}...")
template = client.content.v1.contents(content_sid).fetch()
template_name = template.friendly_name
print(f"📋 Template name: {template_name}")

# Connect to Google Sheets
creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
gc = gspread.authorize(creds)
spreadsheet = gc.open_by_key(SHEET_ID) if SHEET_ID else gc.open(SHEET_NAME)
existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

# Create campaign tab if needed
if template_name not in existing_tabs:
    campaign_sheet = spreadsheet.add_worksheet(title=template_name, rows=1000, cols=6)
    campaign_sheet.append_row(["name", "phone_number", "message", "date", "time", "status"])
    print(f"✅ Created new sheet tab: {template_name}")
else:
    print(f"✅ Sheet tab already exists: {template_name}")

# Update Config tab so webhook knows the active campaign
if "Config" not in existing_tabs:
    config_sheet = spreadsheet.add_worksheet(title="Config", rows=10, cols=2)
    config_sheet.update("A1:B1", [["active_campaign", template_name]])
    print(f"✅ Created Config tab with active_campaign = {template_name}")
else:
    config_sheet = spreadsheet.worksheet("Config")
    config_sheet.update_cell(1, 2, template_name)
    print(f"✅ Updated Config tab: active_campaign = {template_name}")

def clean_header(h: str) -> str:
    return (
        h.replace("\ufeff", "")
         .replace("ï»¿", "")
         .replace("ï»", "")
         .replace("»¿", "")
         .strip()
    )

def normalize_phone(phone: str) -> str:
    phone = phone.strip().replace(" ", "").replace("-", "")
    if phone.startswith("whatsapp:"):
        phone = phone[len("whatsapp:"):]
    if not phone.startswith("+"):
        phone = "+" + phone
    return f"whatsapp:{phone}"

results_file = "send_results.csv"

with open("contacts.csv", "r", encoding="latin-1") as f:
    reader = csv.DictReader(f)
    reader.fieldnames = [clean_header(n) for n in reader.fieldnames]
    rows = list(reader)

with open(results_file, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Name",
        "PhoneNumber",
        "MessageSID",
        "Status",
        "Error_Code",
        "Error_Message"
    ])

for row in rows:
    name = row["Name"].strip() or "Friend"
    phone = row.get("PhoneNumber", row.get("Phone", "")).strip()
    to_number = normalize_phone(phone)

    payload = {
        "from_": whatsapp_from,
        "to": to_number,
        "content_sid": content_sid,
        "content_variables": json.dumps({"1": name}),
    }
    if BASE_URL:
        payload["status_callback"] = f"{BASE_URL}/status-callback"

    print(f"Sending to {name} ({to_number})")
    print("DEBUG PAYLOAD:", payload)

    try:
        msg = client.messages.create(**payload)
        print("Queued:", msg.sid)

        final_status = msg.status
        final_error_code = ""
        final_error_message = ""

        for _ in range(8):
            time.sleep(5)
            fetched = client.messages(msg.sid).fetch()
            final_status = fetched.status
            final_error_code = fetched.error_code or ""
            final_error_message = fetched.error_message or ""

            print(
                "Status:", final_status,
                "Error:", final_error_code,
                "Message:", final_error_message
            )

            if final_status in ["delivered", "sent", "failed", "undelivered"]:
                break

        with open(results_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                name,
                phone,
                msg.sid,
                final_status,
                final_error_code,
                final_error_message
            ])

    except Exception as e:
        print(f"Fatal error for {name}: {e}")
        with open(results_file, "a", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow([
                name,
                phone,
                "",
                "fatal_error",
                "",
                str(e)
            ])

print(f"Done. Results saved to {results_file}")