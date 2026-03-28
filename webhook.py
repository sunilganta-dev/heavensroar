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

# Set TEMPLATE_NAME env var on Render to pin a specific tab; otherwise uses the latest campaign tab
TAB_NAME_OVERRIDE = os.getenv("TEMPLATE_NAME", "").strip()

# Tabs that are permanent and must never be treated as campaign tabs
SYSTEM_TABS = {
    "Reply History", "ReadReceipts", "UnnamedContacts",
    "Config", "Sheet1", "— Ready for next campaign —"
}

_status_sheet = None
_history_sheet = None


def get_spreadsheet():
    gc = gspread.authorize(Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES))
    return gc.open_by_key(SHEET_ID) if SHEET_ID else gc.open(SHEET_NAME)


def get_sheet():
    """Returns the reply tab for the current campaign (named '<template> reply').
    Always re-checks the latest campaign tab — no restart or env update needed for new templates.
    """
    spreadsheet = get_spreadsheet()
    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    base_tab = TAB_NAME_OVERRIDE
    if not base_tab:
        campaign_tabs = [ws.title for ws in spreadsheet.worksheets()
                         if ws.title not in SYSTEM_TABS and not ws.title.endswith(" reply")]
        base_tab = campaign_tabs[-1] if campaign_tabs else "DefaultCampaign"
        print(f"📋 Auto-selected campaign tab: {base_tab}")

    tab_name = f"{base_tab} reply"

    if tab_name not in existing_tabs:
        sheet = spreadsheet.add_worksheet(title=tab_name, rows=1000, cols=6)
        sheet.append_row(["Name", "Phone Number", "Message", "Date", "Time", "Status"])
        sheet.freeze(rows=1)
        print(f"✅ Created reply tab: {tab_name}")
    else:
        sheet = spreadsheet.worksheet(tab_name)
        print(f"✅ Connected to reply tab: {tab_name}")

    return sheet


def get_history_sheet():
    """Returns the permanent Reply History tab — never deleted, logs every reply ever received."""
    global _history_sheet
    if _history_sheet is not None:
        return _history_sheet

    spreadsheet = get_spreadsheet()
    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    if "Reply History" not in existing_tabs:
        _history_sheet = spreadsheet.add_worksheet(title="Reply History", rows=5000, cols=6)
        _history_sheet.append_row([
            "Name / WhatsApp ID", "Phone Number", "Message", "Date", "Time (24hr)", "Type"
        ])
        _history_sheet.freeze(rows=1)
        print("✅ Created permanent Reply History tab")
    else:
        _history_sheet = spreadsheet.worksheet("Reply History")
        print("✅ Connected to Reply History tab")

    return _history_sheet


def get_status_sheet():
    global _status_sheet
    if _status_sheet is not None:
        return _status_sheet

    spreadsheet = get_spreadsheet()
    existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

    if "ReadReceipts" not in existing_tabs:
        _status_sheet = spreadsheet.add_worksheet(title="ReadReceipts", rows=5000, cols=5)
        _status_sheet.append_row(["Message SID", "To Number", "Status", "Timestamp (24hr)", "Campaign"])
        _status_sheet.freeze(rows=1)
        print("✅ Created ReadReceipts tab")
    else:
        _status_sheet = spreadsheet.worksheet("ReadReceipts")
        print("✅ Connected to ReadReceipts tab")

    return _status_sheet


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

@app.route("/status-callback", methods=["POST"])
def status_callback():
    message_sid = request.values.get("MessageSid", "")
    message_status = request.values.get("MessageStatus", "")
    to_number = request.values.get("To", "").replace("whatsapp:", "").strip()
    timestamp = datetime.now(timezone.utc).isoformat()

    print(f"📬 Status update: {to_number} → {message_status} ({message_sid})")

    # Only log meaningful statuses
    if message_status in ["delivered", "read", "failed", "undelivered"]:
        try:
            get_status_sheet().append_row([
                message_sid, to_number, message_status, timestamp, TAB_NAME_OVERRIDE or "auto"
            ])
            print(f"✅ Logged status: {to_number} | {message_status}")
        except Exception as e:
            print(f"❌ Status log error: {e}")

    return "", 204


@app.route("/", methods=["GET"])
def home():
    return "Heaven's Roar Webhook is running!", 200


@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200


def log_profile_name_to_sheet(phone_number, profile_name):
    """Log WhatsApp display name for unnamed contacts to an UnnamedContacts tab."""
    try:
        gc = gspread.authorize(Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES))
        spreadsheet = gc.open_by_key(SHEET_ID) if SHEET_ID else gc.open(SHEET_NAME)
        existing_tabs = [ws.title for ws in spreadsheet.worksheets()]

        if "UnnamedContacts" not in existing_tabs:
            tab = spreadsheet.add_worksheet(title="UnnamedContacts", rows=500, cols=3)
            tab.append_row(["PhoneNumber", "WhatsAppName", "CapturedAt"])
        else:
            tab = spreadsheet.worksheet("UnnamedContacts")

        # Avoid duplicates
        records = tab.get_all_values()
        existing_phones = {r[0] for r in records[1:]}
        if phone_number not in existing_phones:
            tab.append_row([phone_number, profile_name, datetime.now(timezone.utc).isoformat()])
            print(f"📝 Captured profile name: {profile_name} ({phone_number})")
    except Exception as e:
        print(f"⚠️  Could not log profile name: {e}")


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

    # ── Auto-capture WhatsApp display name for unnamed contacts ───────────────
    # Load contacts to check if this number already has a name
    try:
        known_names = {}
        with open("contacts.csv", "r", encoding="latin-1") as cf:
            for row in csv.DictReader(cf):
                p = row.get("Phone", row.get("PhoneNumber", "")).strip().lstrip("+")
                known_names[p] = row.get("Name", "").strip()

        clean_phone = phone_number.lstrip("+")
        raw_profile = request.values.get("ProfileName", "").strip()

        if raw_profile and known_names.get(clean_phone, "") == "":
            log_profile_name_to_sheet(phone_number, raw_profile)
    except Exception as e:
        print(f"⚠️  Profile capture error: {e}")

    # =========================
    # DECISION LOGIC
    # =========================

    UPDATE_KEYWORDS = ["update", "change", "edit", "rename", "correct", "fix my name", "wrong name"]
    DETAILS_KEYWORDS = ["details", "detail", "when", "where", "what time", "location", "address", "show", "play", "event", "info", "information", "ticket", "tickets", "schedule"]
    TRANSPORT_KEYWORDS = ["transport", "transportation", "ride", "pickup", "pick up", "pick-up", "drop", "drop off", "dropoff", "bus", "car", "drive", "driving", "lift", "commute"]

    if msg_upper in ["STOP", "UNSUBSCRIBE", "CANCEL", "END", "QUIT", "OPTOUT", "OPT OUT"]:
        status = "UNSUBSCRIBED"
        command_type = "STOP"
        reply_text = (
            "You have successfully unsubscribed from Heaven's Roar updates. "
            "We're sorry to see you go! 🙏\n\n"
            "If you ever change your mind, feel free to reach out to us directly."
        )
        add_unsubscribed_number(phone_number)

    elif msg_upper == "HELP":
        status = "HELP_REQUEST"
        command_type = "HELP"
        reply_text = (
            "We're here to help! 😊\n\n"
            "What is your question? For existing event or any general query, please go ahead and ask."
        )

    elif any(kw in incoming_msg.lower() for kw in TRANSPORT_KEYWORDS):
        status = "TRANSPORT_REQUEST"
        command_type = "TRANSPORT"
        reply_text = (
            "We'd love to help with transportation! 🚗\n\n"
            "Please share your full address and contact details and our team will get back to you shortly."
        )

    elif button_payload == "Easter_celeb":
        status = "RSVP_CONFIRMED"
        command_type = "RSVP_YES"
        reply_text = (
            "Thank you for confirming! 🌸\n\n"
            "*Cost of Love — A Powerful Easter Drama*\n"
            "📅 March 28, 2026\n"
            "⏰ 6:00 PM\n"
            "📍 951 Westside Ave, Jersey City, NJ\n\n"
            "📞 Contact: +1 (201) 234-1948 | +1 (551) 998-7011\n\n"
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
            "*Cost of Love — A Powerful Easter Drama*\n"
            "📅 March 28, 2026\n"
            "⏰ 6:00 PM\n"
            "📍 951 Westside Ave, Jersey City, NJ\n\n"
            "📞 Contact: +1 (201) 234-1948 | +1 (551) 998-7011\n\n"
            "We look forward to seeing you there! 🙏"
        )

    else:
        status = "ACTIVE"
        command_type = "MESSAGE"
        reply_text = (
            "Thank you for your message! 🙏\n\n"
            "Our team will be in touch. "
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

    # Log to current campaign tab
    try:
        get_sheet().append_row([
            profile_name, phone_number, incoming_msg, date_only, time_only, status
        ])
        print(f"✅ Logged to campaign tab: {profile_name} | {phone_number} | {status}")
    except Exception as e:
        print("❌ Campaign sheet error:", e)

    # Log to permanent Reply History tab (never deleted)
    try:
        get_history_sheet().append_row([
            profile_name, phone_number, incoming_msg, date_only, time_only, command_type
        ])
        print(f"📜 Logged to Reply History: {profile_name} | {command_type}")
    except Exception as e:
        print("❌ Reply History sheet error:", e)

    # =========================
    # AUTO REPLY
    # =========================

    resp = MessagingResponse()
    resp.message(reply_text)
    return str(resp)


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)