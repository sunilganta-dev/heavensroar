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

# Optional override — if set, always use this tab; otherwise read from Config tab
TAB_NAME_OVERRIDE = os.getenv("TEMPLATE_NAME", "").strip()

_sheet = None

def get_sheet():
    global _sheet
    if _sheet is not None:
        return _sheet

    gc = gspread.authorize(Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES))
    spreadsheet = gc.open_by_key(SHEET_ID) if SHEET_ID else gc.open(SHEET_NAME)
    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    # Resolve active campaign tab name
    tab_name = TAB_NAME_OVERRIDE
    if not tab_name:
        try:
            config = spreadsheet.worksheet("Config")
            tab_name = (config.acell("B1").value or "").strip()
            print(f"📋 Active campaign from Config tab: {tab_name}")
        except Exception as e:
            print(f"⚠️ Could not read Config tab: {e}")
            tab_name = "DefaultCampaign"

    if tab_name not in existing_tabs:
        _sheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=6)
        _sheet.append_row(["name", "phone_number", "message", "date", "time", "status"])
        print(f"✅ Created new tab: {tab_name}")
    else:
        _sheet = spreadsheet.worksheet(tab_name)
        print(f"✅ Connected to tab: {tab_name}")

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

    UPDATE_KEYWORDS = ["update", "change", "edit", "rename", "correct", "fix my name", "wrong name"]
    DETAILS_KEYWORDS = ["details", "detail", "when", "where", "what time", "location", "address", "show", "play", "event", "info", "information", "ticket", "tickets", "schedule"]

    if msg_upper in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "OPTOUT", "OPT OUT", "HELP"]:
        status = "UNSUBSCRIBED"
        command_type = "STOP"
        reply_text = (
            "You have successfully unsubscribed from Heaven's Roar updates. "
            "We're sorry to see you go! 🙏\n\n"
            "If you ever change your mind, feel free to reach out to us directly."
        )
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

    elif any(kw in incoming_msg.lower() for kw in UPDATE_KEYWORDS):
        status = "UPDATE_REQUEST"
        command_type = "UPDATE"
        reply_text = (
            "Thank you for letting us know! 😊\n\n"
            "We'll update our records shortly. "
            "If you need to make any specific changes, please reply with your updated details and we'll take care of it."
        )

    elif any(kw in incoming_msg.lower() for kw in DETAILS_KEYWORDS):
        status = "DETAILS_REQUESTED"
        command_type = "DETAILS"
        reply_text = (
            "Thank you for your interest in Heaven's Roar! 🎭\n\n"
            "Full event details will be shared in the next phase. "
            "Stay tuned — we'll be in touch soon with everything you need to know! 🌟"
        )

    else:
        status = "ACTIVE"
        command_type = "MESSAGE"
        reply_text = (
            "Thank you for your message! 🙏\n\n"
            "Our team will be in touch. "
            "If you have questions about the event, reply *details*. "
            "To unsubscribe, reply *STOP*."
        )

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