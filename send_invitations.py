import csv
import os
from twilio.rest import Client
from dotenv import load_dotenv
import time

load_dotenv()

account_sid = os.getenv("TWILIO_ACCOUNT_SID")
auth_token = os.getenv("TWILIO_AUTH_TOKEN")
whatsapp_from = os.getenv("TWILIO_WHATSAPP_FROM")
content_sid = "HXcb2e78e107879d490aa65bcc1917d1e1"

client = Client(account_sid, auth_token)

print("🔐 Using SID:", account_sid)
print("📤 Using FROM:", whatsapp_from)

# SAVE RESULTS HERE

results_file = "send_results.csv"
with open(results_file, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow([
        "Name",
        "PhoneNumber",
        "MessageSID",
        "Status",
        "Error_Code",
        "Error_Message"
    ])

print("\n📌 Loading contacts...")

# Clean header function
def clean_header(h):
    return (
        h.replace("\ufeff","")
         .replace("ï»¿", "")
         .replace("ï»", "")
         .replace("»¿", "")
         .strip()
    )

# Load CSV
with open("contacts.csv", "r", encoding="latin-1") as f:
    reader = csv.DictReader(f)
    reader.fieldnames = [clean_header(n) for n in reader.fieldnames]
    rows = list(reader)

print(f"📌 Found {len(rows)} contacts")

# SEND + DELIVERY CHECKING
for row in rows:
    name = row["Name"].strip()
    phone = row["PhoneNumber"].strip()

    print(f"\n📨 Sending to {name} ({phone}) ...")

    try:
        msg = client.messages.create(
            from_=whatsapp_from,
            to=f"whatsapp:+{phone}",
            content_sid=content_sid,
            content_variables=f'{{"1":"{name}"}}'
        )


        # Wait for Twilio to update status
        time.sleep(3)
        msg_check = client.messages(msg.sid).fetch()

        status = msg_check.status
        e_code = msg_check.error_code
        e_msg = msg_check.error_message

        print(f"➡️ Status: {status} | Error: {e_code}")

        # Save result
        with open(results_file, "a", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                name,
                phone,
                msg.sid,
                status,
                e_code,
                e_msg
            ])

    except Exception as e:
        print("❌ Fatal Error:", e)

print("\n🎉 DONE — All messages processed.")
print("📁 Results saved to send_results.csv")
