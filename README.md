# Heaven’s Roar WhatsApp Webhook

This project is a **Flask-based WhatsApp webhook** built using **Twilio’s WhatsApp API**.  
It receives incoming WhatsApp messages, automatically replies, and **logs all responses into a CSV file** with timestamp, sender number, message body, and status.

The project is **fully deployed on Render (production-ready)** and monitored using a `/healthz` endpoint.

---

## Features

- Receives WhatsApp messages via Twilio
- Auto-replies to every incoming message
- Logs messages into a CSV file
- Tracks:
  - Timestamp
  - Sender Number
  - Message Body
  - Message Status (received)
- Supports STOP / UNSUBSCRIBE messages
- Health monitoring endpoint (`/healthz`)
- Deployed on Render using **Gunicorn**
- Environment variable security using `.env`

---

## Live Deployment

deployed and running here: https://heavensroar-jfm-webhook.onrender.com



## Github Repo: 
git clone https://github.com/sunilganta-dev/heavensroar

## Create virtual environment:

python -m venv venv

source venv/bin/activate

pip install -r requirements.txt

pip install flask twilio gspread oauth2client gunicorn

## Install dependencies:
pip install -r requirements.txt

## Run the webhook locally:
python webhook.py
