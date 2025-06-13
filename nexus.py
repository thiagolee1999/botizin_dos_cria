import requests
import time
import os
from datetime import datetime, timedelta

# API endpoint and parameters
base_url = "https://ttp.cbp.dhs.gov/schedulerapi/slots/asLocations?minimum=1&limit=5&serviceName=NEXUS"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}

# Telegram bot config
bot_token = os.getenv('BOT_KEY')
chat_id = os.getenv('CHAT_KEY')

# Blaine, WA location ID (you may need to adjust this based on the actual ID from the API)
BLAINE_LOCATION_ID = [5020,16764,5021]  # This is a placeholder, you'll need to verify the correct ID

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
        print("found appointments: ", message)
    except Exception as e:
        print(f"Failed to send Telegram message: {e}")

def check_nexus_appointments():
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        locations = response.json()
        
        # Find Blaine location
        blaine_location = None
        location_id = ""
        for location in locations:
            if location["id"] in BLAINE_LOCATION_ID:
                blaine_location = location
                location_id = location["id"]
                break
        
        if not blaine_location:
            print("Blaine location not found in the response")
            return

        # Check if the location is operational
        if not blaine_location.get("operational", False):
            print("Blaine location is not operational")
            return

        # Get available slots
        slots_url = f"https://ttp.cbp.dhs.gov/schedulerapi/slots?orderBy=soonest&limit=10&locationId={location_id}&minimum=1"
        slots_response = requests.get(slots_url, headers=headers)
        slots_response.raise_for_status()
        available_slots = slots_response.json()

        if available_slots:
            message = "🎉 NEXUS appointments available in Blaine, WA!\n\n"
            for slot in available_slots:
                start_time = datetime.fromisoformat(slot["startTimestamp"].replace("Z", "+00:00"))
                message += f"📅 {start_time.strftime('%Y-%m-%d %I:%M %p')}\n"
            
            message += "\nBook your appointment at: https://ttp.cbp.dhs.gov/"
            print("Found available appointments!")
            send_telegram_message(message)
        else:
            print("No available appointments found")

    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    check_nexus_appointments() 