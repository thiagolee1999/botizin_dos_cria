import requests
import time
import os


# API details
cookies = {
    '_gid': 'GA1.2.744608808.1732334755',
    '_ga': 'GA1.1.770228636.1731455462',
    '_ga_2EBVDX89EN': 'GS1.1.1732334754.3.1.1732336379.60.0.0',
    'AWSALB': 'cFNUaepDlnjKCHtn13VScsxjtBwn9p8Fkc6qQAlLlL/zTnxOdIUEHwDMJSCLrF4Pj/KUKw1wPeUWXaI3VF4s97xlMCXIKKgqq5p5hwpIbs4D4/if0RI+WCiO5uaf',
    'AWSALBCORS': 'cFNUaepDlnjKCHtn13VScsxjtBwn9p8Fkc6qQAlLlL/zTnxOdIUEHwDMJSCLrF4Pj/KUKw1wPeUWXaI3VF4s97xlMCXIKKgqq5p5hwpIbs4D4/if0RI+WCiO5uaf',
}

headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'cache-control': 'no-cache',
    'content-type': 'application/json',
    'cookie': '_gid=GA1.2.744608808.1732334755; _ga=GA1.1.770228636.1731455462; _ga_2EBVDX89EN=GS1.1.1732334754.3.1.1732336379.60.0.0; AWSALB=cFNUaepDlnjKCHtn13VScsxjtBwn9p8Fkc6qQAlLlL/zTnxOdIUEHwDMJSCLrF4Pj/KUKw1wPeUWXaI3VF4s97xlMCXIKKgqq5p5hwpIbs4D4/if0RI+WCiO5uaf; AWSALBCORS=cFNUaepDlnjKCHtn13VScsxjtBwn9p8Fkc6qQAlLlL/zTnxOdIUEHwDMJSCLrF4Pj/KUKw1wPeUWXaI3VF4s97xlMCXIKKgqq5p5hwpIbs4D4/if0RI+WCiO5uaf',
    'origin': 'https://www.comedycellar.com',
    'pragma': 'no-cache',
    'priority': 'u=1, i',
    'referer': 'https://www.comedycellar.com/reservations-newyork/',
    'sec-ch-ua': '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"macOS"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
    'x-code-localize': 'e74c9504db55305e7a59c748ef231000fc435bbea17d29f7acda3ae1ab405f45.MTczMjMzOTk3OS03Mi4yMS4xOTguNjY=',
    'x-page-creation': '1730748703',
}

json_data = {
    'date': '2024-11-22',
}

target_times = {"22:45:00", "23:00:00", "23:30:00", "00:55:00"}  # Add times you're interested in

# Telegram Bot Details (Replace with your values)
TELEGRAM_BOT_TOKEN = os.getenv('BOT_KEY')
TELEGRAM_CHAT_ID = os.getenv('CHAT_KEY')

# Helper function to send a Telegram message
def send_telegram_message(message):
    telegram_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message
    }
    try:
        response = requests.post(telegram_url, json=payload)
        if response.status_code == 200:
            print("Notification sent successfully.")
        else:
            print(f"Failed to send notification: {response.status_code}, {response.text}")
    except Exception as e:
        print(f"Error while sending notification: {e}")

# Main function to check reservation and notify
def check_reservation():
    while True:
        try:
            response = requests.post(
                'https://www.comedycellar.com/reservations/api/getShows',
                cookies=cookies,
                headers=headers,
                json=json_data,
            )
            response.raise_for_status()
            shows_data = response.json()
            shows = shows_data.get("data", {}).get("showInfo", {}).get("shows", [])

            # Check each show for a match with target times
            for show in shows:
                show_time = show.get("time")
                if show_time in target_times:
                    max_capacity = show.get("max", 0)
                    current_count = show.get("totalGuests", 0)
                    description = show.get("description")
                    
                    # Check if current count is less than max capacity
                    if current_count < max_capacity:
                        message = (
                            f"Reservation available for {description}!\n"
                            f"Max Capacity: {max_capacity}\n"
                            f"Current Guest Count: {current_count}"
                        )
                        send_telegram_message(message)
                    else:
                        print(f"No availability for {show_time}: {current_count}/{max_capacity}")
            else:
                print("No matching shows found.")
            
        except Exception as e:
            print(f"Error during reservation check: {e}")

        # Wait for 2 minutes before the next attempt
        time.sleep(120)

# Run the script
check_reservation()
