from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import csv
import os

import gspread
from google.oauth2.service_account import Credentials

app = Flask(__name__)

# GOOGLE SHEETS CONFIG

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

CREDS_FILE = "google_credentials.json"  # Must exist in project root
SHEET_NAME = "HeavensRoar WhatsApp Logs"  # Your sheet name

creds = Credentials.from_service_account_file(CREDS_FILE, scopes=SCOPES)
client = gspread.authorize(creds)
sheet = client.open(SHEET_NAME).sheet1

# LOCAL CSV BACKUP FILE

CSV_FILE = "whatsapp_responses.csv"

if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            "timestamp",
            "date",
            "from_number",
            "message",
            "status"
        ])

# ROUTES

@app.route("/", methods=["GET"])
def home():
    return "Heaven's Roar Webhook is running!", 200


@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200


@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    timestamp = datetime.utcnow().isoformat()
    date_today = datetime.utcnow().strftime("%Y-%m-%d")

    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")

    message_upper = incoming_msg.upper()

    # Detect STOP
    if message_upper in ["STOP", "UNSUBSCRIBE", "CANCEL", "END"]:
        status = "UNSUBSCRIBED"
        reply = "✅ You have been unsubscribed successfully."
    else:
        status = "ACTIVE"
        reply = f"✅ Message received: {incoming_msg}"

    # SAVE TO GOOGLE SHEET

    sheet.append_row([
        timestamp,
        date_today,
        from_number,
        incoming_msg,
        status
    ])


    # SAVE TO LOCAL CSV BACKUP

    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            date_today,
            from_number,
            incoming_msg,
            status
        ])

    # SEND REPLY TO USER
 
    resp = MessagingResponse()
    resp.message(reply)

    return str(resp)


# RENDER PRODUCTION RUN

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
