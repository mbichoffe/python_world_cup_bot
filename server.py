import os
import csv
from dotenv import load_dotenv, find_dotenv
from flask import Flask
from flask import jsonify
from flask import request
from http import HTTPStatus
from twilio.rest import Client
import json

app = Flask(__name__)

load_dotenv(find_dotenv())

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
CLIENT = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
MESSAGING_SERVICE_SID = os.getenv("TWILIO_MESSAGING_SERVICE_SID")
SUBSCRIBERS_DB = './subscribers.csv'


@app.route('/subscribe', methods=['POST', 'DELETE'])
def subscribe():

    phone_number = request.get_json()["number"]
    if request.method == 'POST':
        if phone_number:
            is_valid = verify(phone_number)
            if is_valid:
                # TODO: get number from verify formatted
                add_subscriber(phone_number)
                resp = send_message(phone_number, "Welcome to the World Cup live updates!")
                if resp.status == "accepted":
                    # Return status code 200, with empty body
                    return jsonify({"message": "You are subscribed!"}), HTTPStatus.OK
                else:
                    return jsonify({"message": resp.msg}), HTTPStatus.BAD_REQUEST

        return jsonify({"message":"invalid number"}), 400



@app.route('/updates', methods=['POST'])
def send_updates():
    """
    Sends SMS to subscribers when an interesting event happens during a live match
    :return: None if successful, JSON with message error if it fails to send message
    """
    message_body = request.get_json()['message']
    subscribers_list = get_subscribers()
    resp = send_group_message(subscribers_list, message_body)

    if resp:
        return jsonify({"message": resp.msg}, status=HTTPStatus.BAD_REQUEST)
    else:
        return '', 200

# {'uri': '/Accounts/AC9ef0615fc878587fcd7a67aa97a03703/Messages.json', 'status': 400, 'msg': 'Unable to create record: A text message body or media urls must be specified.', 'code': 21619, 'method': 'POST'}

#### HELPER FUNCTIONS ####

def get_subscribers()->list:
    subscribers = []
    with open(SUBSCRIBERS_DB, 'r') as csvfile:
        reader_ = csv.reader(csvfile, delimiter=' ', quotechar='|')
        # skip header
        next(reader_, None)
        for row in reader_:
            if len(row):
                subscribers.append(row[0])
    return subscribers


def add_subscriber(number: str)->None:
    with open(SUBSCRIBERS_DB, 'a', newline='') as csv_file:
        # creating a csv writer object
        csv_writer = csv.writer(csv_file,  delimiter=' ', quotechar='|')
        # writing the fields
        csv_writer.writerow([number])
        csv_file.close()


def remove_subscriber(number):
    pass


def send_message(number:str, body:str=None)-> "twilio.rest.api.v2010.account.message.MessageInstance":
    message = CLIENT.messages.create(
        to=number,
        from_=MESSAGING_SERVICE_SID,
        body=body)
    return message


def send_group_message(numbers_list: list, body: str=None)->None or Exception:

    # option: use functools.partial
    for number in numbers_list:
        try:
            message = send_message(number, body)
        except Exception as e:
            print("\n\n\n\n", e.__dict__, "\n\n\n\n")
            return e


def verify(phone_number:str) -> bool:
    """
    Calls Twilio lookup API to verify if a number is valid
    :param phone_number:
    :return: True if number is a valid phone number, False otherwise
    """
    # option: use regex
    try:
        phone_number = CLIENT.lookups.phone_numbers(f'{phone_number}').fetch(
                        type='carrier')
        print(phone_number.phone_number)
        return True
    except Exception as e:
        return False


if __name__ == '__main__':
    app.run(debug=True)
