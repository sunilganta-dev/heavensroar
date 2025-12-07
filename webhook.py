from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import csv
import os

app = Flask(__name__)

CSV_FILE = "whatsapp_responses.csv"

# Ensure file exists
if not os.path.exists(CSV_FILE):
    with open(CSV_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "from", "body", "status"])

@app.route("/", methods=["GET"])
def home():
    return "Heaven's Roar Webhook is running!", 200

@app.route("/healthz", methods=["GET"])
def health_check():
    return "OK", 200

@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    incoming_msg = request.values.get("Body", "")
    from_number = request.values.get("From", "")

    resp = MessagingResponse()
    reply = f"Received: {incoming_msg}"
    resp.message(reply)

    # Log into CSV
    with open(CSV_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            datetime.utcnow().isoformat(),
            from_number,
            incoming_msg,
            "received"
        ])

    return str(resp)
    
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
