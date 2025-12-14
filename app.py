from flask import Flask, request
from twilio.twiml.messaging_response import MessagingResponse
from datetime import datetime, timedelta
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import json
import os
from collections import defaultdict

app = Flask(__name__)

# Google Sheets Setup
def get_sheet():
    try:
        creds_json = os.environ.get('GOOGLE_CREDENTIALS_JSON')
        if not creds_json:
            return None
        
        creds_dict = json.loads(creds_json)
        scope = ['https://spreadsheets.google.com/feeds',
                 'https://www.googleapis.com/auth/drive']
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, scope)
        client = gspread.authorize(creds)
        
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        sheet = client.open_by_key(sheet_id).sheet1
        return sheet
    except Exception as e:
        print(f"Error connecting to Google Sheets: {e}")
        return None

def get_user_records(sheet, phone):
    """Get all records for a user (excluding resets)"""
    try:
        records = sheet.get_all_records()
        user_records = []
        for r in records:
            if r.get('Phone Number') == phone:
                date_str = r.get('Date', '')
                if 'RESET' not in date_str:
                    user_records.append(r)
        return user_records
    except:
        return []

def parse_date(date_str):
    """Parse date string to datetime object"""
    try:
        return datetime.strptime(date_str, '%Y-%m-%d %H:%M')
    except:
        return None

def get_today_hours(sheet, phone):
    """Get hours logged today"""
    records = get_user_records(sheet, phone)
    today = datetime.now().date()
    total = 0
    
    for r in records:
        date_str = r.get('Date', '')
        dt = parse_date(date_str)
        if dt and dt.date() == today:
            total += float(r.get('Hours', 0))
    
    return total

def get_week_hours(sheet, phone):
    """Get hours logged this week (Monday-Sunday)"""
    records = get_user_records(sheet, phone)
    today = datetime.now()
    
    # Get Monday of current week
    monday = today - timedelta(days=today.weekday())
    monday = monday.replace(hour=0, minute=0, second=0, microsecond=0)
    
    total = 0
    for r in records:
        date_str = r.get('Date', '')
        dt = parse_date(date_str)
        if dt and dt >= monday:
            total += float(r.get('Hours', 0))
    
    return total

def get_all_time_total(sheet, phone):
    """Get all-time total hours"""
    records = get_user_records(sheet, phone)
    return sum(float(r.get('Hours', 0)) for r in records)

def get_daily_breakdown(sheet, phone, days=7):
    """Get daily breakdown for last N days"""
    records = get_user_records(sheet, phone)
    today = datetime.now().date()
    
    daily_hours = defaultdict(float)
    
    for r in records:
        date_str = r.get('Date', '')
        dt = parse_date(date_str)
        if dt:
            date = dt.date()
            days_ago = (today - date).days
            if days_ago < days:
                daily_hours[date] += float(r.get('Hours', 0))
    
    return daily_hours

def log_hours(sheet, phone, hours):
    """Log hours to Google Sheet"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        
        # Append new row (removed total column as we calculate dynamically)
        sheet.append_row([phone, hours, date_str])
        
        # Get updated totals
        today_total = get_today_hours(sheet, phone)
        week_total = get_week_hours(sheet, phone)
        all_time = get_all_time_total(sheet, phone)
        
        return True, today_total, week_total, all_time
    except Exception as e:
        print(f"Error logging hours: {e}")
        return False, 0, 0, 0

def reset_user(sheet, phone):
    """Reset hours for a user"""
    try:
        date_str = datetime.now().strftime('%Y-%m-%d %H:%M')
        sheet.append_row([phone, 0, f"RESET - {date_str}"])
        return True
    except:
        return False

@app.route('/whatsapp', methods=['POST'])
def whatsapp_bot():
    incoming_msg = request.values.get('Body', '').strip().lower()
    from_number = request.values.get('From', '')
    
    resp = MessagingResponse()
    msg = resp.message()
    
    sheet = get_sheet()
    
    if not sheet:
        msg.body("⚠️ Error connecting to database. Please try again later.")
        return str(resp)
    
    # Command handling
    if incoming_msg.startswith('log '):
        try:
            hours = float(incoming_msg.split('log ')[1])
            success, today, week, all_time = log_hours(sheet, from_number, hours)
            
            if success:
                msg.body(f"✅ Logged {hours} hours!\n\n📅 Today: {today}h\n📊 This week: {week}h\n🎯 All-time: {all_time}h")
            else:
                msg.body("❌ Error logging hours. Please try again.")
        except:
            msg.body("❌ Invalid format. Use: log 2.5")
    
    elif incoming_msg == 'today':
        today = get_today_hours(sheet, from_number)
        msg.body(f"📅 Today's hours: {today}h")
    
    elif incoming_msg == 'week':
        week = get_week_hours(sheet, from_number)
        msg.body(f"📊 This week's hours: {week}h")
    
    elif incoming_msg == 'total':
        all_time = get_all_time_total(sheet, from_number)
        msg.body(f"🎯 All-time total: {all_time}h")
    
    elif incoming_msg == 'stats':
        today = get_today_hours(sheet, from_number)
        week = get_week_hours(sheet, from_number)
        all_time = get_all_time_total(sheet, from_number)
        
        msg.body(f"""📊 Your Statistics

📅 Today: {today}h
📆 This week: {week}h
🎯 All-time: {all_time}h""")
    
    elif incoming_msg == 'daily':
        daily = get_daily_breakdown(sheet, from_number, 7)
        
        if daily:
            lines = []
            for i in range(6, -1, -1):
                date = (datetime.now() - timedelta(days=i)).date()
                hours = daily.get(date, 0)
                day_name = date.strftime('%a')
                if hours > 0:
                    lines.append(f"{day_name} {date.strftime('%m/%d')}: {hours}h")
                else:
                    lines.append(f"{day_name} {date.strftime('%m/%d')}: -")
            
            breakdown = "\n".join(lines)
            week_total = get_week_hours(sheet, from_number)
            msg.body(f"📅 Last 7 Days:\n\n{breakdown}\n\n📊 Week total: {week_total}h")
        else:
            msg.body("📅 No data for the last 7 days")
    
    elif incoming_msg == 'history':
        records = get_user_records(sheet, from_number)[-5:]
        if records:
            lines = []
            for r in records:
                date = r.get('Date', '')
                hrs = r.get('Hours', 0)
                lines.append(f"{date}: {hrs}h")
            
            history_text = "\n".join(lines)
            msg.body(f"📖 Recent sessions:\n{history_text}")
        else:
            msg.body("📖 No sessions logged yet!")
    
    elif incoming_msg == 'reset':
        if reset_user(sheet, from_number):
            msg.body("🔄 All hours reset to 0")
        else:
            msg.body("❌ Error resetting. Please try again.")
    
    elif incoming_msg == 'sheet':
        sheet_id = os.environ.get('GOOGLE_SHEET_ID')
        msg.body(f"📊 View your data:\nhttps://docs.google.com/spreadsheets/d/{sheet_id}")
    
    else:
        msg.body("""📚 Learning Hours Tracker

Commands:
• log 2.5 - Log hours
• today - Today's hours
• week - This week's hours
• total - All-time total
• stats - Full statistics
• daily - Last 7 days breakdown
• history - Recent sessions
• reset - Reset all data

Example: log 3""")
    
    return str(resp)

@app.route('/')
def home():
    return "✅ WhatsApp Learning Bot with Daily/Weekly Tracking!"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
