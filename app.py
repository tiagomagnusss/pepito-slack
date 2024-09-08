from flask import Flask, request, redirect, render_template
from slack_sdk import WebClient
from slack_sdk.oauth import AuthorizeUrlGenerator, RedirectUriPageRenderer
from slack_sdk.oauth.installation_store import FileInstallationStore
from slack_sdk.oauth.state_store import FileOAuthStateStore
import os
from dotenv import load_dotenv
import threading
from main import run_bot

load_dotenv()

app = Flask(__name__)

client_id = os.environ["SLACK_CLIENT_ID"]
client_secret = os.environ["SLACK_CLIENT_SECRET"]
scopes = ["chat:write", "chat:write.customize", "channels:read", "files:write"]
user_scopes = []

installation_store = FileInstallationStore(base_dir="./data")
oauth_state_store = FileOAuthStateStore(expiration_seconds=600, base_dir="./data")

authorize_url_generator = AuthorizeUrlGenerator(
    client_id=client_id,
    scopes=scopes,
    user_scopes=user_scopes,
)

@app.route("/slack/install", methods=["GET"])
def oauth_start():
    state = oauth_state_store.issue()
    url = authorize_url_generator.generate(state)
    return redirect(url)

@app.route("/slack/oauth_redirect", methods=["GET"])
def oauth_callback():
    code = request.args.get("code")
    state = request.args.get("state")
    if state is None or not oauth_state_store.consume(state):
        return "Invalid state", 400

    client = WebClient()
    oauth_response = client.oauth_v2_access(
        client_id=client_id,
        client_secret=client_secret,
        code=code,
    )
    
    installation_store.save(oauth_response)
    
    # Get the bot token and team ID
    bot_token = oauth_response["access_token"]
    team_id = oauth_response["team"]["id"]
    
    # Use the bot token to get the list of channels
    bot_client = WebClient(token=bot_token)
    channels = bot_client.conversations_list(types="public_channel,private_channel")
    
    # Render a template with a form to select the channel
    return render_template("select_channel.html", channels=channels["channels"], team_id=team_id)

@app.route("/slack/select_channel", methods=["POST"])
def select_channel():
    channel_id = request.form.get("channel_id")
    team_id = request.form.get("team_id")
    
    # Update the installation with the selected channel
    installation = installation_store.find_installation(team_id=team_id)
    installation["channel_id"] = channel_id
    installation_store.save(installation)
    
    # Start the bot for this installation
    threading.Thread(target=run_bot, args=(installation,), daemon=True).start()
    
    return "Installation successful! The bot will post updates to the selected channel."

if __name__ == "__main__":
    # Start bots for all existing installations
    for installation in installation_store.find_all():
        if "channel_id" in installation:
            threading.Thread(target=run_bot, args=(installation,), daemon=True).start()
    
    app.run(port=3000)