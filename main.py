#!/usr/bin/python

from __future__ import print_function
import httplib2
import os
import signal
import subprocess
import time

from apiclient import discovery
from oauth2client import client
from oauth2client import tools
from oauth2client.file import Storage

import datetime
import pytz
import dateutil.parser
import threading

try:
    import argparse
    flags = argparse.ArgumentParser(parents=[tools.argparser]).parse_args()
except ImportError:
    flags = None

# If modifying these scopes, delete your previously saved credentials
# at ~/.credentials/calendar-python-quickstart.json
SCOPES = 'https://www.googleapis.com/auth/calendar'
CLIENT_SECRET_FILE = 'client_secret.json'
APPLICATION_NAME = 'Google Calendar API Python Quickstart'
PIPE_PATH = './pipe'

start = None
end = None
count = 0
inBed = False
oldInBed = False

def get_credentials():
    """Gets valid user credentials from storage.

    If nothing has been stored, or if the stored credentials are invalid,
    the OAuth2 flow is completed to obtain the new credentials.

    Returns:
        Credentials, the obtained credential.
    """
    home_dir = os.path.expanduser('~')
    credential_dir = os.path.join(home_dir, '.credentials')
    if not os.path.exists(credential_dir):
        os.makedirs(credential_dir)
    credential_path = os.path.join(credential_dir,
                                   'calendar-python-quickstart.json')

    store = Storage(credential_path)
    credentials = store.get()
    if not credentials or credentials.invalid:
        flow = client.flow_from_clientsecrets(CLIENT_SECRET_FILE, SCOPES)
        flow.user_agent = APPLICATION_NAME
        if flags:
            credentials = tools.run_flow(flow, store, flags)
        else: # Needed only for compatibility with Python 2.6
            credentials = tools.run(flow, store)
        print('Storing credentials to ' + credential_path)
    return credentials

def getAlarmId(service):
    print('Getting the List of Calendar')
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == 'Alarm':
                return calendar_list_entry['id']
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break

def getFirstAlarm(service):
    alarmId = getAlarmId(service)
    now = datetime.datetime.utcnow().isoformat() + 'Z' # 'Z' indicates UTC time
    eventsResult = service.events().list(
        calendarId=alarmId, timeMin=now, maxResults=1, singleEvents=True,
        orderBy='startTime').execute()
    events = eventsResult.get('items', [])

    if not events:
        return None
    for event in events:
        start = event['start'].get('dateTime', event['start'].get('date'))
        end = event['end'].get('dateTime', event['end'].get('date'))
        return (dateutil.parser.parse(start), dateutil.parser.parse(end))


def insertEvent(service):
    alarmId = getAlarmId(service)

    event = {
    'summary': 'My Event',
    'location': 'UCSD',
    'description': 'My test event',
    'start': {
        'dateTime': '2017-02-28T09:00:00-07:00',
        'timeZone': 'America/Los_Angeles',
        },
    'end': {
        'dateTime': '2017-02-28T17:00:00-07:00',
        'timeZone': 'America/Los_Angeles',
        },
    'recurrence': [
        'RRULE:FREQ=DAILY;COUNT=1'
        ],
    'attendees': [
        ],
    'reminders': {
        'useDefault': True
        },
    }

    event = service.events().insert(calendarId=alarmId, body=event).execute()
    print('Event created: %s' % (event.get('htmlLink')))

def getService():
    credentials = get_credentials()
    http = credentials.authorize(httplib2.Http())
    service = discovery.build('calendar', 'v3', http=http)
    return service

def pollCalendar(service):
    global start
    global end
    while True:
        start, end = getFirstAlarm(service)
        time.sleep(30)

def lightControl():
    global oldInBed
    if oldInBed != inBed:
        if inBed:
            print("light off")
            subprocess.call(["codesend", "283964"])
        else:
            print("light on")
            subprocess.call(["codesend", "283955"])
    oldInBed = inBed

def sendIR():
    global inBed
    while True:
        local_count = count
        subprocess.call(["irsend", "SEND_ONCE", "tank", "KEY_0"])
        print('sending IR signal')
        time.sleep(0.5)
        if count == local_count:
            print('blocked')
            inBed = True
        else:
            print('open')
            inBed = False
        lightControl()

def receiveIR():
    global count
    while True:
        with open(PIPE_PATH, 'r') as pipe:
            while True:
                s = pipe.read()
                if len(s) == 0:
                    print('pipe closed')
                    break
                count = count + 1

def main():
    """Shows basic usage of the Google Calendar API.

    Creates a Google Calendar API service object and outputs a list of the next
    10 events on the user's calendar.
    """
    service = getService()

    IRThread = threading.Thread(target = sendIR, args = ())
    IRThread.daemon = True
    IRThread.start()

    IRReadThread = threading.Thread(target = receiveIR, args = ())
    IRReadThread.daemon = True
    IRReadThread.start()

    calendarThread = threading.Thread(target = pollCalendar, args = (service,))
    calendarThread.daemon = True
    calendarThread.start()

    while True:
        now = datetime.datetime.utcnow().replace(tzinfo=pytz.utc)
        if start:
            print(start, end)
            if start < now:
                print('alarm!!!')
            else:
                print('nothing...')
        time.sleep(5)

if __name__ == '__main__':
    main()
