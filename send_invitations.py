import csv
import os
import json
import time
from twilio.rest import Client
from dotenv import load_dotenv

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
content_sid = "HX11b30a572704eb8bf70c5fc8e3042ed2"

if not account_sid or not auth_token or not whatsapp_from:
    raise ValueError("Missing TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, or TWILIO_WHATSAPP_FROM in environment.")

client = Client(account_sid, auth_token)

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
    name = row["Name"].strip()
    phone = row["PhoneNumber"].strip()
    to_number = normalize_phone(phone)

    payload = {
        "from_": whatsapp_from,
        "to": to_number,
        "content_sid": content_sid,
        "content_variables": json.dumps({
            "1": name
        })
    }

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