from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, timezone
import csv
import os

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# =========================
# GOOGLE SHEETS CONFIG
# =========================

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CREDS_FILE = os.getenv("GOOGLE_CREDS_FILE", "google_credentials.json")

# You can use either SHEET_ID or SHEET_NAME
SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "").strip()
SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "HeavensRoar WhatsApp Logs")

# IMPORTANT: make this match your actual tab
TAB_NAME = os.getenv("TEMPLATE_NAME", "EasterOutreach2026")

_sheet = None

def get_sheet():
    global _sheet
    if _sheet is not None:
        return _sheet

    creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
    gc = gspread.authorize(creds)

    if SHEET_ID:
        spreadsheet = gc.open_by_key(SHEET_ID)
    else:
        spreadsheet = gc.open(SHEET_NAME)

    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    if TAB_NAME not in existing_tabs:
        _sheet = spreadsheet.add_worksheet(title=TAB_NAME, rows=1000, cols=6)
        _sheet.append_row(["name", "phone_number", "message", "date", "time", "status"])
        print(f"✅ Created new tab: {TAB_NAME}")
    else:
        _sheet = spreadsheet.worksheet(TAB_NAME)
        print(f"✅ Connected to tab: {TAB_NAME}")

    return _sheet


# =========================
# LOCAL FILES
# =========================

CSV_FILE = "whatsapp_responses.csv"
CLEAN_CSV = "whatsapp_clean_log.csv"
UNSUB_FILE = "unsubscribed_numbers.csv"

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "timestamp", "from_number", "message_body", "command_type", "device", "status"
        ])

if not os.path.exists(CLEAN_CSV):
    with open(CLEAN_CSV, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            "name", "phone_number", "message", "date", "time", "status"
        ])

if not os.path.exists(UNSUB_FILE):
    with open(UNSUB_FILE, "w", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow(["phone_number", "unsubscribed_at"])

def add_unsubscribed_number(phone_number):
    existing = set()

    with open(UNSUB_FILE, "r", newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            existing.add(row["phone_number"].strip())

    if phone_number not in existing:
        with open(UNSUB_FILE, "a", newline="", encoding="utf-8") as f:
            csv.writer(f).writerow([phone_number, datetime.now(timezone.utc).isoformat()])
        print(f"🚫 Added to unsubscribe list: {phone_number}")


# =========================
# ROUTES
# =========================

@app.route("/", methods=["GET"])
def home():
    return "Heaven's Roar Webhook is running!", 200


@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200


@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    now = datetime.now(timezone.utc)
    timestamp = now.isoformat()
    date_only = now.strftime("%Y-%m-%d")
    time_only = now.strftime("%H:%M:%S")

    incoming_msg = request.values.get("Body", "").strip()
    phone_number = request.values.get("From", "").replace("whatsapp:", "").strip()
    profile_name = request.values.get("ProfileName", "").strip() or phone_number
    device_info = request.headers.get("User-Agent", "Unknown Device")
    button_payload = request.values.get("ButtonPayload", "").strip()

    msg_upper = incoming_msg.upper()

    # =========================
    # DECISION LOGIC
    # =========================

    if msg_upper in ["STOP", "UNSUBSCRIBE", "CANCEL", "END"]:
        status = "UNSUBSCRIBED"
        command_type = "STOP"
        reply_text = "You have been unsubscribed from further notifications."
        add_unsubscribed_number(phone_number)

    elif button_payload == "Easter_celeb":
        status = "RSVP_CONFIRMED"
        command_type = "RSVP_YES"
        reply_text = (
            "Thank you for confirming! 🌸\n\n"
            "*Easter Celebration*\n"
            "📅 April 20\n"
            "⏰ 6:00 PM\n"
            "📍 951 West Side Ave, Jersey City, NJ 07306\n\n"
            "We look forward to seeing you!"
        )

    else:
        status = "ACTIVE"
        command_type = "MESSAGE"
        reply_text = f"📩 Message received: {incoming_msg}"

    # =========================
    # LOGGING
    # =========================

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            timestamp, phone_number, incoming_msg, command_type, device_info, status
        ])

    with open(CLEAN_CSV, "a", newline="", encoding="utf-8") as f:
        csv.writer(f).writerow([
            profile_name, phone_number, incoming_msg, date_only, time_only, status
        ])

    try:
        get_sheet().append_row([
            profile_name, phone_number, incoming_msg, date_only, time_only, status
        ])
        print(f"✅ Logged to Google Sheet: {profile_name} | {phone_number} | {status}")
    except Exception as e:
        print("❌ GOOGLE SHEETS ERROR:", e)

    # =========================
    # AUTO REPLY
    # =========================

    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)