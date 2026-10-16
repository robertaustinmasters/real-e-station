from fastapi import FastAPI, Request, HTTPException
from pydantic import BaseModel
import httpx, json, os, uvicorn

app = FastAPI(title="Real-E-Station Telegram & Gemini Engine")

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") 
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
APPS_SCRIPT_WEBHOOK = os.getenv("APPS_SCRIPT_WEBHOOK")

class DistressedProperty(BaseModel):
    property_address: str
    owner_name: str
    owner_phone: str
    equity_percent: float
    estimated_value: float

@app.get("/")
async def health_check():
    return {"status": "online", "engine": "Telegram + Gemini Bridge"}

@app.post("/ingest-lead")
async def ingest_new_lead(lead: DistressedProperty):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise HTTPException(status_code=500, detail="Missing Telegram credentials.")

    caption = (
        f"?? *NEW DISTRESSED PROPERTY LEAD*\n\n"
        f"?? *Address:* {lead.property_address}\n"
        f"?? *Owner:* {lead.owner_name}\n"
        f"?? *Phone:* `{lead.owner_phone}`\n"
        f"?? *Equity:* {lead.equity_percent}%\n"
        f"?? *Est. Value:* ${lead.estimated_value:,.2f}\n\n"
        f"? _Reply to this message to simulate AI negotiation._"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient() as client:
        res = await client.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": caption, "parse_mode": "Markdown"})
        if res.status_code != 200:
            return {"status": "telegram_error", "details": res.json()}

    return {"status": "lead_dispatched_to_telegram", "lead": lead.property_address}

@app.post("/telegram-webhook")
async def handle_telegram_update(request: Request):
    data = await request.json()
    
    if "message" in data:
        chat_id = data["message"]["chat"]["id"]
        text = data["message"].get("text", "")

        if text:
            try:
                # 1. Analyze text using Gemini 1.5 Flash
                analysis = await analyze_intent_with_gemini(text)
                
                # 2. Format reply for Telegram
                bot_reply = (
                    f"?? *Gemini Analysis:*\n"
                    f"Motivated: {analysis.get('is_motivated')}\n"
                    f"Price: ${analysis.get('asking_price')}\n"
                    f"Condition: {analysis.get('condition')}\n\n"
                    f"?? *Suggested Reply:* {analysis.get('suggested_reply')}"
                )
                
                # 3. Route to Google Sheets CRM if motivated
                if analysis.get("is_motivated") and APPS_SCRIPT_WEBHOOK:
                    bot_reply += "\n\n? _Lead logged to Google Sheets CRM._"
                    async with httpx.AsyncClient() as client:
                        await client.post(APPS_SCRIPT_WEBHOOK, json={
                            "action": "log_and_match",
                            "phone": "Telegram_User", 
                            "analysis": analysis
                        })
                        
            except Exception as e:
                bot_reply = f"?? Gemini Processing Error: {str(e)}"
                
            # Send the result back to your Telegram chat
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
            async with httpx.AsyncClient() as client:
                await client.post(url, json={"chat_id": chat_id, "text": bot_reply, "parse_mode": "Markdown"})

    return {"status": "ok"}

async def analyze_intent_with_gemini(text: str):
    if not GEMINI_API_KEY:
        raise Exception("Missing Gemini API Key")
        
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={GEMINI_API_KEY}"
    
    prompt = f"""
    Analyze this message from a property seller: "{text}"
    Return ONLY a JSON object with these exact keys:
    - "is_motivated": boolean (true if they seem willing to sell/discuss)
    - "asking_price": integer or null (if mentioned)
    - "condition": string (any repairs mentioned, or "Unknown")
    - "suggested_reply": string (how to reply to push for a contract)
    """
    
    payload = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"response_mime_type": "application/json"}
    }
    
    async with httpx.AsyncClient(timeout=10.0) as client:
        res = await client.post(url, json=payload)
        data = res.json()
        raw_text = data['candidates'][0]['content']['parts'][0]['text']
        return json.loads(raw_text)

if __name__ == "__main__":
    port = int(os.getenv("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
