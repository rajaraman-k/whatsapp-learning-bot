from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os

app = Flask(__name__)

# Google Sheets Setup
def get_sheet():
    try:
        # Get credentials from environment variable
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            return None
        
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        # Open sheet by ID
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}")
        return None

def get_user_total(sheet, phone):
    """Get total hours for a user"""
    try:
        # Find all rows for this user
        cell_list = sheet.findall(phone)
        total = 0
        for cell in cell_list:
            row = cell.row
            hours = sheet.cell(row, 2).value  # Column B (Hours)
            if hours:
                total += float(hours)
        return total
    except:
        return 0

def log_hours(sheet, phone, hours):
    """Log hours to Google Sheet"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        total = get_user_total(sheet, phone) + hours
        
        # Append new row
        sheet.append_row([phone, hours, date_str, total])
        return True, total
    except Exception as e:
        print(f"Error logging hours: {e}")
        return False, 0

def get_history(sheet, phone):
    """Get recent sessions for user"""
    try:
        records = sheet.get_all_records()
        user_records = [r for r in records if r.get('Phone Number') == phone]
        # Get last 5
        return user_records[-5:] if user_records else []
    except:
        return []

def reset_user(sheet, phone):
    """Reset hours for a user (mark as reset in sheet)"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        sheet.append_row([phone, 0, f"RESET - {date_str}", 0])
        return True
    except:
        return False

@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    
    resp = MessagingResponse()
    msg = resp.message()
    
    # Get Google Sheet
    sheet = get_sheet()
    
    if not sheet:
        msg.body("⚠️ Error connecting to database. Please try again later.")
        return str(resp)
    
    # Command handling
    if incoming_msg.startswith('log '):
        try:
            hours = float(incoming_msg.split('log ')[1])
            success, total = log_hours(sheet, from_number, hours)
            
            if success:
                msg.body(f"✅ Logged {hours} hours!\n\n📊 Total: {total}h")
            else:
                msg.body("❌ Error logging hours. Please try again.")
        except:
            msg.body("❌ Invalid format. Use: log 2.5")
    
    elif incoming_msg == 'total':
        total = get_user_total(sheet, from_number)
        msg.body(f"📚 Total learning hours: {total}h")
    
    elif incoming_msg == 'history':
        history = get_history(sheet, from_number)
        if history:
            lines = []
            for h in history:
                date = h.get('Date', '')
                hrs = h.get('Hours', 0)
                if 'RESET' not in date:
                    lines.append(f"{date}: {hrs}h")
            
            total = get_user_total(sheet, from_number)
            history_text = "\n".join(lines[-5:]) if lines else "No sessions yet"
            msg.body(f"📖 Recent sessions:\n{history_text}\n\n📊 Total: {total}h")
        else:
            msg.body("📖 No sessions logged yet!")
    
    elif incoming_msg == 'reset':
        if reset_user(sheet, from_number):
            msg.body("🔄 Hours reset to 0")
        else:
            msg.body("❌ Error resetting. Please try again.")
    
    elif incoming_msg == 'sheet':
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        msg.body(f"📊 View your data:\nhttps://docs.google.com/spreadsheets/d/{sheet_id}")
    
    else:
        msg.body("""📚 Learning Hours Tracker

Commands:
• log 2.5 - Log hours
• total - View total hours
• history - Recent sessions
• sheet - View Google Sheet
• reset - Reset hours

Example: log 3""")
    
    return str(resp)

@app.route('/')
def home():
    return "✅ WhatsApp Learning Bot with Google Sheets is running!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
