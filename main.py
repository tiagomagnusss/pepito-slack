import os
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
from slack_sdk import WebClient
from sseclient import SSEClient
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.errors import SlackApiError

load_dotenv()

installation_store = FileInstallationStore(base_dir="./data")

pepito_api_url = "https://pepito-api.onrender.com/api/v1/events"

from slack_sdk.errors import SlackApiError

def post_to_slack(installation, message, image_url):
    try:
        client = WebClient(token=installation["bot_token"])
        
        # Download the image
        response = requests.get(image_url)
        if response.status_code == 200:
            # Upload the image to Slack
            file_upload = client.files_upload(
                channels=installation["channel_id"],
                file=response.content,
                filename="pepito_image.jpg",
                initial_comment=message
            )
            
            if not file_upload["ok"]:
                print(f"Error uploading file: {file_upload['error']}")
        else:
            print(f"Error downloading image: {response.status_code}")
            # If image download fails, send text message only
            client.chat_postMessage(channel=installation["channel_id"], text=message)
    except SlackApiError as e:
        print(f"Error posting to Slack: {e}")

def format_message(data):
    event_type = data.get('event')
    if event_type == 'pepito':
        action = 'entered' if data['type'] == 'in' else 'left'
        timestamp = datetime.fromtimestamp(data['time']).strftime('%Y-%m-%d %H:%M:%S')
        return f"Pepito is {data['type']} at {timestamp}\nImage: {data['img']}"
    elif event_type == 'heartbeat':
        return None
    else:
        return f"Unknown event: {data}"

def process_event(event, installation):
    try:
        data = json.loads(event.data)
        message = format_message(data)
        if message and 'img' in data:
            post_to_slack(installation, message, data['img'])
    except json.JSONDecodeError:
        print(f"Error decoding JSON: {event.data}")
    except KeyError as e:
        print(f"Missing key in event data: {e}")

def run_bot(installation):
    print(f"Starting Pepito Slack bot for installation {installation['team_id']}...")
    try:
        response = requests.get(pepito_api_url, stream=True)
        client = SSEClient(response)
        for event in client.events():
            process_event(event, installation)
    except requests.RequestException as e:
        print(f"Error connecting to Pepito API: {e}")
    except Exception as e:
        print(f"Unexpected error: {e}")
