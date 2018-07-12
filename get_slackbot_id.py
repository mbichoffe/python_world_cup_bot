import os
from dotenv import load_dotenv, find_dotenv
from slackclient import SlackClient

load_dotenv(find_dotenv())

BOT_NAME = "pythonworldcupbot"

slack_client = SlackClient(os.getenv('SLACK_BOT_TOKEN'))


if __name__ == "__main__":
    api_call = slack_client.api_call("users.list")
    if api_call.get('ok'):
    # retrieve all users so we can find our bot
        users = api_call.get('members')
        for user in users:
            if 'name' in user and user.get('name') == BOT_NAME:
                print("Bot ID for '" + user['name'] + "' is " + user.get('id'))
    else:
        print("API Call failed")