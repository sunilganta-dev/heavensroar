from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import csv
import os

app = Flask(__name__)

CSV_FILE = "whatsapp_responses.csv"

#CSV file exists with headers
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

@app.route("/", methods=["GET"])
def home():
    return "Heaven's Roar Webhook is running!", 200

@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    timestamp = datetime.utcnow().isoformat()

    incoming_msg = request.values.get("Body", "").strip()
    from_number = request.values.get("From", "")
    device_info = request.headers.get("User-Agent", "Unknown")

    message_upper = incoming_msg.upper()

    # ✅ Detect STOP / UNSUBSCRIBE
    if message_upper in ["STOP", "UNSUBSCRIBE", "CANCEL", "END"]:
        command_type = "STOP"
        status = "UNSUBSCRIBED"
        reply = "✅ You have been unsubscribed successfully."
    else:
        command_type = "MESSAGE"
        status = "ACTIVE"
        reply = f"✅ Message received: {incoming_msg}"

    # ✅ Save everything to CSV
    with open(CSV_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([
            timestamp,
            from_number,
            incoming_msg,
            command_type,
            device_info,
            status
        ])

    resp = MessagingResponse()
    resp.message(reply)

    return str(resp)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)

    
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
