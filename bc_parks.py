import requests
import time

# API endpoint and parameters
base_url = "https://jd7n1axqh0.execute-api.ca-central-1.amazonaws.com/api/reservation?facility=Rubble+Creek&park=0007"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
}
desired_date = "2024-09-15"

bot_token = os.getenv('BOT_KEY')
chat_id = os.getenv('GROUP_KEY')

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
        
        if desired_date in data:
            capacity_info = data[desired_date]["DAY"]["capacity"]
            print(f"Checking {desired_date}: Capacity - {capacity_info}")
            
            if capacity_info != "Full":
                message = f"VAGOUUUUU! CORRE PRA https://reserve.bcparks.ca/dayuse/registration"
                print(message)
                send_telegram_message(message)
            else:
                print(f"Capacity for {desired_date} is still full.")
        else:
            print(f"No data available for {desired_date}.")

    except Exception as e:
        print(f"An error occurred: {e}")


# Run the script continuously in the background
check_reservation()
