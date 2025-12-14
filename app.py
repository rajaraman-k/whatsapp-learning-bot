from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import json
import os

app = Flask(__name__)

# Get credentials from environment variables
TWILIO_ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.environ.get('TWILIO_AUTH_TOKEN')

DATA_FILE = 'learning_hours.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=2)

@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    
    resp = MessagingResponse()
    msg = resp.message()
    
    data = load_data()
    
    if from_number not in data:
        data[from_number] = {'total_hours': 0, 'sessions': []}
    
    if incoming_msg.startswith('log '):
        try:
            hours = float(incoming_msg.split('log ')[1])
            data[from_number]['total_hours'] += hours
            data[from_number]['sessions'].append({
                'hours': hours,
                'date': datetime.now().strftime('%Y-%m-%d %H:%M')
            })
            save_data(data)
            msg.body(f"✅ Logged {hours} hours!\n\nTotal: {data[from_number]['total_hours']}h")
        except:
            msg.body("❌ Invalid format. Use: log 2.5")
    
    elif incoming_msg == 'total':
        msg.body(f"📚 Total: {data[from_number]['total_hours']}h")
    
    elif incoming_msg == 'history':
        sessions = data[from_number]['sessions'][-5:]
        if sessions:
            history = "\n".join([f"{s['date']}: {s['hours']}h" for s in sessions])
            msg.body(f"📖 Recent:\n{history}\n\nTotal: {data[from_number]['total_hours']}h")
        else:
            msg.body("No sessions yet!")
    
    elif incoming_msg == 'reset':
        data[from_number] = {'total_hours': 0, 'sessions': []}
        save_data(data)
        msg.body("🔄 Reset complete")
    
    else:
        msg.body("📚 Learning Hours Tracker\n\nCommands:\n• log 2.5 - Log hours\n• total - View total\n• history - Recent sessions\n• reset - Reset hours")
    
    return str(resp)

@app.route('/')
def home():
    return "✅ WhatsApp Learning Bot is running!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
