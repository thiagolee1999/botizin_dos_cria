import requests
import time
import os
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables from .env file if it exists (for local development)
# This won't override existing environment variables, so GitHub Actions will still work
load_dotenv()

# API endpoint and parameters
endpoint = "https://services.ontario.ca/appointment-booking/api/availableDays"
headers = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Content-Type": "application/json",
    "Origin": "https://www.ontario.ca",
    "Referer": "https://www.ontario.ca/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36"
}

payload = {
    "locationCode": "918",
    "startDate": "2025-12-01",
    "numberOfDays": "40",
    "purposeCodeList": "M21,M68"
}

# Target date threshold - notify if any dates are before this
TARGET_DATE = "2025-12-15"
target_date = datetime.strptime(TARGET_DATE, "%Y-%m-%d")

# Telegram bot config
bot_token = os.getenv('BOT_KEY')
chat_id = os.getenv('CHAT_KEY')

def send_telegram_message(message):
    """Sends a message to your Telegram chat."""
    telegram_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }
    try:
        response = requests.post(telegram_url, data=payload)
        response.raise_for_status()
        print("Telegram message sent!")
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def check_appointments():
    try:
        response = requests.post(endpoint, headers=headers, json=payload)
        
        # Better error handling to see what's happening
        if response.status_code != 200:
            print(f"Error: Status code {response.status_code}")
            print(f"Response: {response.text}")
            return
        
        response.raise_for_status()
        available_dates = response.json()
        
        # Check if response is a list of dates
        if not isinstance(available_dates, list):
            print(f"Unexpected response format: {available_dates}")
            return
        
        # Filter dates that are before the target date
        early_dates = []
        for date_str in available_dates:
            try:
                date_obj = datetime.strptime(date_str, "%Y-%m-%d")
                if date_obj < target_date:
                    early_dates.append(date_str)
            except ValueError:
                print(f"Invalid date format: {date_str}")
                continue
        
        if early_dates:
            # Sort dates for better readability
            early_dates.sort()
            message = "🎉 Early appointment dates available!\n\n"
            message += f"Available dates before {TARGET_DATE}:\n"
            for date in early_dates:
                message += f"📅 {date}\n"
            message += "\nBook your appointment at: https://www.ontario.ca/page/book-appointment"
            print(f"Found {len(early_dates)} early dates!")
            send_telegram_message(message)
        else:
            print(f"Checked {len(available_dates)} dates - none before {TARGET_DATE}")
            if available_dates:
                print(f"Earliest available date: {min(available_dates)}")
            else:
                print("No dates available at all")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    print("Starting Ontario appointment checker...")
    
    while True:
        check_appointments()
        time.sleep(120)  # Wait 2 minutes (120 seconds) before next check

