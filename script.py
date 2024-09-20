import requests
import time
import schedule
import os

# API endpoint and parameters
base_url = "https://www.apple.com/ca/shop/fulfillment-messages?pl=true&mts.0=regular&mts.1=compact&cppart=UNLOCKED/WW&parts.0=MYWJ3VC/A&parts.1=MYWH3VC/A&location=V6Z2M9"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}

partMapping = {
    "MYWJ3VC/A": "Desert Titanium",
    "MYWH3VC/A": "White Titanium"
}

# Telegram bot config
bot_token = os.getenv('BOT_TOKEN')
chat_id = os.getenv('CHAT_ID')


validStores = ["pacificcentre@apple.com"]

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

def check_reservation():
    try:
        response = requests.get(base_url, headers=headers)
        response.raise_for_status()
        data = response.json()
        
        stores = data["body"]["content"]["pickupMessage"]["stores"]

        res = []

        for store in stores:
            if store["storeEmail"] in validStores:
                iterable = store["partsAvailability"]
                for key in iterable:
                    if iterable[key]["pickupDisplay"] != 'available':
                        res.append({"color": partMapping[key], "store": store["storeEmail"]})
                
            
        if len(res) > 0:
            print("FOOOUND")
            message = []
            message.append("Found iPhones!")
            for item in res:
                formatted_string = f"- {item['color']} --> {item['store']}"
                message.append(formatted_string)
            output_string = "\n".join(message)
            send_telegram_message(output_string)
        else:
            print("x")

    except Exception as e:
        print(f"An error occurred: {e}")

check_reservation()