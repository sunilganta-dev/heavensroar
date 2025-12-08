from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import csv
import os
import gspread
from oauth2client.service_account import ServiceAccountCredentials

app = Flask(__name__)

# GOOGLE SHEETS SETUP


SCOPE = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
]

CREDS = ServiceAccountCredentials.from_json_keyfile_name(
    "/etc/secrets/google_credentials.json", SCOPE
)

gc = gspread.authorize(CREDS)

# Open your Google Sheet
SHEET = gc.open("HeavensRoar WhatsApp Logs").sheet1


# CSV SETUP (DETAILED LOG)


CSV_FILE = "whatsapp_responses.csv"

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "from_number",
            "message_body",
            "command_type",
            "device",
            "status"
        ])


# CLEAN CSV SETUP (MATCHES GOOGLE SHEET FORMAT)


CLEAN_CSV = "whatsapp_clean_log.csv"

if not os.path.exists(CLEAN_CSV):
    with open(CLEAN_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "name",
            "phone_number",
            "message",
            "date",
            "time",
            "status"
        ])


# ROUTES

@app.route("/", methods=["GET"])
def home():
    return "Heaven's Roar WhatsApp Webhook is running!", 200


@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200

# MAIN WHATSAPP WEBHOOK

@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():

    # ---- Extract timestamp fields ----
    now = datetime.utcnow()
    date_only = now.strftime("%Y-%m-%d")
    time_only = now.strftime("%H:%M:%S")
    timestamp_iso = now.isoformat()

    # ---- Incoming message data ----
    incoming_msg = request.values.get("Body", "").strip()
    from_number_raw = request.values.get("From", "")
    profile_name = request.values.get("ProfileName", "Unknown")

    # Clean phone number: remove 'whatsapp:'
    phone_number = from_number_raw.replace("whatsapp:", "")

    device_info = request.headers.get("User-Agent", "Unknown Device")
    msg_upper = incoming_msg.upper()

    # ---- STOP / UNSUBSCRIBE logic ----
    if msg_upper in ["STOP", "UNSUBSCRIBE", "CANCEL", "END"]:
        command_type = "STOP"
        status = "UNSUBSCRIBED"
        reply_text = "⚠️ You have been unsubscribed from further notifications."
    else:
        command_type = "MESSAGE"
        status = "ACTIVE"
        reply_text = f"📩 Message received: {incoming_msg}"

    # SAVE TO DETAILED CSV
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp_iso,
            phone_number,
            incoming_msg,
            command_type,
            device_info,
            status
        ])

    # SAVE TO CLEAN CSV (matches Sheet)

    with open(CLEAN_CSV, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            profile_name,
            phone_number,
            incoming_msg,
            date_only,
            time_only,
            status
        ])

    # SAVE TO GOOGLE SHEETS
    try:
        SHEET.append_row([
            profile_name,
            phone_number,
            incoming_msg,
            date_only,
            time_only,
            status
        ])
        print("✔ Logged to Google Sheets:", incoming_msg)

    except Exception as e:
        print("❌ GOOGLE SHEETS ERROR:", e)

    # SEND WHATSAPP AUTO-REPLY
    resp = MessagingResponse()
    resp.message(reply_text)

    return str(resp)

# RENDER RUN

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
