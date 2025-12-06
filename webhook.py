from flask import Flask, request
import csv
from datetime import datetime
import os

app = Flask(__name__)

LOG_FILE = "whatsapp_responses.csv"

# Ensure CSV has a header the first time
if not os.path.exists(LOG_FILE):
    with open(LOG_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["timestamp", "from_number", "body", "status"])

@app.route("/whatsapp-webhook", methods=["POST"])
def whatsapp_webhook():
    from_number = request.form.get("From")
    body = (request.form.get("Body") or "").strip()

    print("\n📩 Incoming WhatsApp Message:")
    print("From:", from_number)
    print("Body:", body)

    # Decide status based on message body
    upper_body = body.upper().strip()
    status = "UNSUBSCRIBE" if upper_body == "STOP" else "REPLIED"

    # Append to CSV log
    with open(LOG_FILE, "a", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([datetime.utcnow().isoformat(), from_number, body, status])

    return "OK", 200



if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    print(f"🚀 Webhook running on port {port}")
    app.run(host="0.0.0.0", port=port)
