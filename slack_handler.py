import os
import time
import requests
from dotenv import load_dotenv, find_dotenv
from slackclient import SlackClient
from twilio.rest import Client

load_dotenv(find_dotenv())


SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_BOT_ID = os.getenv("SLACK_BOT_ID")

# constants
AT_BOT = f'<@{SLACK_BOT_ID}>'
BOT_COMMAND = "subscribe"
TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
# instantiate Twilio Client
CLIENT = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
# instantiate Slack Client
SLACK_CLIENT = SlackClient(SLACK_BOT_TOKEN)

def add_subscriber(phone_number: str):
    """
    Calls endpoint to add subscriber to SMS updates.
    If successful, returns success message. Returns error message otherwise.
    :param phone_number:
    :return:  str: text message
    """
    response = requests.post("http://localhost:5000/subscribe",
                             json={"number": phone_number})

    return response.json()["message"]


def handle_command(command: str, channel: str):
    """
    Receives commands directed at the world cup bot and determines if they
    are valid commands. If so, then acts on the commands. If not,
    returns back what it needs for clarification.
  """

    response = f'Not sure what you mean. To subscribe for SMS World Cup updates, use the *{BOT_COMMAND}* command ' \
               f'followed by your phone number (with area code), delimited by spaces. '
    if command.startswith(BOT_COMMAND):
        response = add_subscriber(command[len(BOT_COMMAND):].strip())
    post_to_slack(channel, response)


def post_to_slack(channel, body=None, attachment_text=None):
    SLACK_CLIENT.api_call("chat.postMessage", channel=channel,
                           text=body, attachments=[{"text": attachment_text}], as_user=True)


def parse_slack_output(slack_rtm_output):
    """
    The Slack Real Time Messaging API is a firehose of data, so
    this parsing function returns None unless a message is
    directed at the Bot, based on its ID.
  """
    output_list = slack_rtm_output
    if output_list and len(output_list) > 0:
        for output in output_list:
            if 'text' in output and AT_BOT in output['text']:
                # return text after the @ mention, whitespace removed - should be phone number
                return output['text'].split(AT_BOT)[1].strip(), output['channel']
        return


if __name__ == "__main__":
    READ_WEBSOCKET_DELAY = 1  # 1 second delay between reading from firehose
    if SLACK_CLIENT.rtm_connect():
        print("WorldCupBot connected and running!")
        while True:
            command, channel = parse_slack_output(SLACK_CLIENT.rtm_read()) or (None, None)
            if command and channel:
                handle_command(command, channel)
            time.sleep(READ_WEBSOCKET_DELAY)
    else:
        print("Connection failed.")
"""
[{'type': 'message', 'user': 'U9Z74BL9W', 'text': '<@UBJ2JR941> hi', 
'client_msg_id': '6907bb11-1929-4c47-9d68-4125b4ee58c4', 'team': 'T024FJ1MS', 
'channel': 'GB965ANC8', 'event_ts': '1530762983.000035', 'ts': '1530762983.000035'}]
"""