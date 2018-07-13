import os
import time
import json
import requests
import math
import logging
import dateutil.parser
from requests import Request, Session
from datetime import datetime
from slack_handler import post_to_slack

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

logger = logging.getLogger(__name__)

# CONSTANTS
SLACK_CHANNEL="#test-slack-bot-fifa"
PROXY = 'http://myproxy:3128'
USE_PROXY = False
PROXY_USERPWD = False
LOCALE = 'en-GB'
os.environ['TZ'] = 'UTC'
time.tzset()

language = {'en-GB': [
    'The match between',
    'is about to start',
    'Yellow card',
    'Red card',
    'Own goal',
    'Penalty',
    'GOOOOAL',
    'Missed penalty',
    'has started',
    'HALF TIME',
    'FULL TIME',
    'has resumed',
    'END OF 1ST ET',
    'END OF 2ND ET',
    'End of penalty shoot-out'
    ], 'pt-BR': [
    'A partida',
    'vai comecar',
    'Cartao amarelo',
    'Cartao vermelho',
    'Gol contra',
    'Penalti',
    'GOOOOOOOOLLL',
    'Penalti perdido',
    'comecou',
    'INTERVALO',
    'FIM DO SEGUNDO TEMPO',
    'recomecou',
    'Intervalo da prorrogacao',
    'Fim da prorrogacao',
    'Fim dos penaltis'
    ]}

# FIFA API 2018 CONSTANTS

ID_COMPETITION = 17
ID_SEASON = 254645
# Match Statuses
MATCH_STATUS_FINISHED = 0
MATCH_STATUS_NOT_STARTED = 1
MATCH_STATUS_LIVE = 3
MATCH_STATUS_PREMATCH = 12
# Event Types
EVENT_GOAL = 0
EVENT_YELLOW_CARD = 2
EVENT_STRAIGHT_RED = 3
EVENT_SECOND_YELLOW_CARD_RED = 4
EVENT_PERIOD_START = 7
EVENT_PERIOD_END = 8
EVENT_END_OF_GAME = 26
EVENT_OWN_GOAL = 34
EVENT_FREE_KICK_GOAL = 39
EVENT_PENALTY_GOAL = 41
EVENT_PENALTY_SAVED = 60
EVENT_PENALTY_CROSSBAR = 46
EVENT_PENALTY_MISSED = 65
EVENT_FOUL_PENALTY = 72
# Periods
PERIOD_1ST_HALF = 3
PERIOD_2ND_HALF = 5
PERIOD_1ST_ET = 7
PERIOD_2ND_ET = 9
PERIOD_PENALTY = 11

#URLS
FIFA_API_URL = "https://api.fifa.com/api/v1/"

DB_FILE = './worldCupDB.json'

DB = json.loads(open(DB_FILE).read())


# clean etag once in a while
if DB.get('etag') and len(DB['etag']) > 5:
    DB['etag'] = dict()


def save_to_json(file):
    with open(DB_FILE, 'w') as f:
        json.dump(file, f)


def microtime(get_as_float=False):
    """Return current Unix timestamp in microseconds."""
    if get_as_float:
        return time.time()
    else:
        x, y = math.modf(time.time())
        return f'{x} {y}'


def get_url(url, do_not_use_etag=False):

    proxies = dict()
    s = Session()
    req = Request('GET', url)
    prepped = s.prepare_request(req)
    # avoid hitting api limits
    if (not do_not_use_etag and DB.get('etag')) and url in DB['etag']:
        prepped.headers['If-None-Match'] = DB['etag'][url]

    if USE_PROXY:
        proxies['http'] = PROXY

    resp = s.send(prepped,
                  proxies=proxies,
                  timeout=10,
                  verify=False
                  )

    if resp.status_code == requests.codes.ok:
        if resp.headers.get('ETag'):
            DB['etag'][url] = resp.headers['Etag']
            # save etag
            save_to_json(DB)

        content = resp.text

        if len(content.strip()) == 0:
            return False
        return content
    else:
        logger.log(resp.status_code, resp.content)



def send_sms(text: str, attachment: str=None)->None:
    """

    :param text: Match update
    :param attachment: Update details
    :return: None
    """
    if attachment:
        text = text + " " + attachment
    resp = requests.post("http://localhost:5000/updates",
                         json={'message': text})

    if resp.status_code != 200:
        print(resp)


def get_all_matches():
    # A Foolish Consistency is the Hobgoblin of Little Minds
    return json.loads(get_url(f'{FIFA_API_URL}calendar/matches?idCompetition={ID_COMPETITION}&idSeason={ID_SEASON}&count=500&language={LOCALE}', True))


def get_player_alias(player_id):
    """
    Returns player name/nickname
    :param player_id: str
    :return:
    """
    resp = json.loads(get_url(f'{FIFA_API_URL}players/{player_id}', False))

    return resp["Alias"][0]["Description"]

# REPL starts here
"CAlling resp \n\n\n\n"

resp = get_all_matches()

matches = {}

if resp != 'null':
    matches = resp.get("Results")

# Find live matches and update score
for match in matches:

    if match.get('MatchStatus') == MATCH_STATUS_LIVE and match.get("IdMatch") not in DB["live_matches"]:
        DB["live_matches"].append(match["IdMatch"])

        DB[match["IdMatch"]] = {
            'stage_id': match["IdStage"],
            'teamsById': {
                match["Home"]["IdTeam"]: match["Home"]["TeamName"][0]["Description"],
                match["Away"]["IdTeam"]: match["Away"]["TeamName"][0]["Description"]
            },
            "teamsByHomeAway": {
                'Home': match["Home"]["TeamName"][0]["Description"],
                'Away': match["Away"]["TeamName"][0]["Description"]
            },
            'last_update': microtime()
        }
        # send sms and save data
        send_sms(f'{language[LOCALE][0]} {match["Home"]["TeamName"][0]["Description"]} vs. \
        {match["Away"]["TeamName"][0]["Description"]} {language[LOCALE][1]}!')

    if match["IdMatch"] in DB["live_matches"]:
        # update score

        DB[match["IdMatch"]]["score"] = f'{match["Home"]["TeamName"][0]["Description"]} {match["Home"]["Score"]} - ' \
                                        f'{match["Away"]["Score"]} {match["Away"]["TeamName"][0]["Description"]} '
    # save to file to avoid loops
    save_to_json(DB)


live_matches = DB["live_matches"]
for live_match in live_matches:
    for key, value in DB[live_match].items():
        home_team_name = DB[live_match]['teamsByHomeAway']["Home"]
        away_team_name = DB[live_match]['teamsByHomeAway']["Away"]
        last_update_secs = DB[live_match]["last_update"].split(" ")[1]

        # retrieve match events
        response = json.loads(get_url(
            f'{FIFA_API_URL}timelines/{ID_COMPETITION}/{ID_SEASON}/{DB[live_match]["stage_id"]}/{live_match}?language={LOCALE}'))

        # in case of 304
        if response is None:
            continue
        events = response.get("Event")
        for event in events:
            event_type = event["Type"]
            period = event["Period"]
            event_timestamp = dateutil.parser.parse(event["Timestamp"])
            event_time_secs = time.mktime(event_timestamp.timetuple())

            if event_time_secs > float(last_update_secs):
                match_time = event["MatchMinute"]
                _teams_by_id = DB[live_match]['teamsById']
                for key, value in _teams_by_id.items():
                    if key == event["IdTeam"]:
                        event_team = value
                    else:
                        event_other_team = value
                event_player_alias = None
                score = f'{home_team_name} {event["HomeGoals"]} - {event["AwayGoals"]} {away_team_name}'
                subject = ''
                details = ''
                interesting_event = True

                if event_type == EVENT_PERIOD_START:
                    if period == PERIOD_1ST_HALF:
                        subject = f'{language[LOCALE][0]} {home_team_name} vs. {away_team_name} {language[LOCALE][8]}!'

                    elif period == PERIOD_2ND_HALF or period == PERIOD_1ST_ET or period == PERIOD_2ND_ET or period == PERIOD_PENALTY:
                        subject = f'{language[LOCALE][0]} {home_team_name} vs. {away_team_name} {language[LOCALE][11]}!'

                elif event_type == EVENT_PERIOD_END:
                    if period == PERIOD_1ST_HALF:
                        subject = f'{language[LOCALE][9]} {score}'
                        details = match_time
                    elif period == PERIOD_2ND_HALF:
                        subject = f'{language[LOCALE][10]} {score}'
                        details = match_time
                    elif period == PERIOD_1ST_ET:
                        subject = f'{language[LOCALE][12]} {score}'
                        details = match_time
                    elif period == PERIOD_2ND_ET:
                        subject = f'{language[LOCALE][13]} {score}'
                        details = match_time
                    elif period == PERIOD_PENALTY:
                        subject = f'{language[LOCALE][13]} {score} ({event["HomePenaltyGoals"]} - {event["AwayPenaltyGoals"]})'
                        details = match_time

                elif event_type == EVENT_GOAL or event_type == EVENT_FREE_KICK_GOAL or event_type == EVENT_PENALTY_GOAL:
                    event_player_alias = get_player_alias(event["IdPlayer"])
                    subject = f'{language[LOCALE][6]} {event_team}!!!'
                    details = f'{event_player_alias} ({match_time}) {score}'

                elif event_type == EVENT_OWN_GOAL:
                    event_player_alias = get_player_alias(event["IdPlayer"])
                    subject = f'{language[LOCALE][4]} {event_team}!!!'
                    details = f'{event_player_alias} ({match_time}) {score}'

                # cards

                elif event_type == EVENT_YELLOW_CARD:
                    event_player_alias = get_player_alias(event["IdPlayer"])
                    subject = f'{language[LOCALE][2]} {event_team}'
                    details = f'{event_player_alias} ({match_time})'

                elif event_type == EVENT_SECOND_YELLOW_CARD_RED or event_type == EVENT_STRAIGHT_RED:
                    event_player_alias = get_player_alias(event["IdPlayer"])
                    subject = f'{language[LOCALE][3]} {event_team}'
                    details = f'{event_player_alias} ({match_time})'

                elif event_type == EVENT_FOUL_PENALTY:
                    subject = f'{language[LOCALE][5]} {event_other_team}!!!'

                elif event_type == EVENT_PENALTY_MISSED or event_type == EVENT_PENALTY_SAVED:
                    event_player_alias = get_player_alias(event["IdPlayer"])
                    subject = f'{language_[LOCALE][7]} {event_team}!!!'
                    details = f'{event_player_alias} ({match_time})'

                elif event_type == EVENT_END_OF_GAME:
                    DB['live_matches'].remove(live_match)
                    del DB[live_match]
                    interesting_event = False

                else:
                    interesting_event = False
                    continue

                if interesting_event:
                    print("INTERESTING EVENT!", response)
                    send_sms(subject, details)
                    post_to_slack(SLACK_CHANNEL, subject, details)
                    DB[live_match]['last_update'] = microtime()
                if not DB["live_matches"]:
                    DB["live_matches"] = []

# print("saving to db", DB)
save_to_json(DB)





