from fastapi import FastAPI, Request, Form
from pydantic import BaseModel
import httpx, json, os

app = FastAPI(title="Real-E-Station Bridge")

AI_API_KEY = os.getenv("AI_API_KEY")
TWILIO_SID = os.getenv("TWILIO_SID")
TWILIO_TOKEN = os.getenv("TWILIO_TOKEN")
APPS_SCRIPT_WEBHOOK = os.getenv("APPS_SCRIPT_WEBHOOK")

class DistressedProperty(BaseModel):
    property_address: str
    owner_name: str
    owner_phone: str
    equity_percent: float
    estimated_value: float

@app.post("/ingest-lead")
async def ingest_new_lead(lead: DistressedProperty):
    message = f"Hi {lead.owner_name}, I was looking at your property at {lead.property_address}. Are you open to a cash offer this week?"
    async with httpx.AsyncClient() as client:
        await client.post(
            f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_SID}/Messages.json",
            auth=(TWILIO_SID, TWILIO_TOKEN),
            data={"To": lead.owner_phone, "From": "+1234567890", "Body": message}
        )
    return {"status": "outreach_initiated", "lead": lead.property_address}

@app.post("/sms-webhook")
async def handle_incoming_sms(From: str = Form(...), Body: str = Form(...)):
    return {"status": "handled"}
