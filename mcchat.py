#!/usr/bin/env python2

# Usage: mcchat.py HOST[:PORT] USERNAME PASSWORD [AUTH_SERVER]
#
# Joins the Minecraft server given by HOST[:PORT] as USERNAME, and relays
# chat messages between the game and standard input/output.
#
# AUTH_SERVER, if specified, is the hostname of an authentication server
# running Mineshafter Squared (http://www.mineshaftersquared.com/) or
# equivalent; otherwise, Minecraft's official authentication server is used.

from __future__ import print_function

import sys
import time
import os.path
import threading
import traceback

from McClient.networking.NetworkHelper import NetworkHelper
from McClient.networking.Connection import Connection
from McClient.networking.Session import Session
from McClient.networking.Receiver import Receiver
from McClient.networking.Sender import Sender
from McClient.Events import EventManager
from McClient import Utils

from MC2Session import MC2Session

DEFAULT_PORT = 25565

if len(sys.argv) not in (4, 5):
    print('Usage: %s HOST[:PORT] USERNAME PASSWORD [AUTH_SERVER]'
        % os.path.basename(sys.argv[0]), file=sys.stderr)
    sys.exit(1)

address, username, password = sys.argv[1:4]
address = address.rsplit(':', 1)
host, port = address if len(address) == 2 else (address[0], DEFAULT_PORT)
auth_server = sys.argv[4] if len(sys.argv) > 4 else None

global_lock = threading.Lock()
position_and_look = None
#health = None

def with_global_lock(func):
    def decorated(*args, **kwds):
        with global_lock: func(*args, **kwds)
    return decorated
NetworkHelper.respondFD = with_global_lock(NetworkHelper.respondFD)
NetworkHelper.respondFC = with_global_lock(NetworkHelper.respondFC)
NetworkHelper.respond00 = with_global_lock(NetworkHelper.respond00)


class Client(object):

#    @staticmethod
#    def got_event(name, *args, **kwds):
#        event = connection.eventmanager[name]
#        for alias, aevent in connection.eventmanager.aliases.iteritems():
#            if aevent() is event: name = alias
#        if name.startswith('sent_'):
#            if name not in ('sent_client_statuses',
#                            'sent_respawn'): return
#        elif name.startswith('recv_'):
#            if name not in ('recv_player',
#                            'recv_player_position',
#                            'recv_player_look',
#                            'recv_player_position_and_look',
#                            'recv_update_health',
#                            'recv_respawn'): return
#        print('@ %s %s %s' % (name, args, kwds), file=sys.stderr)

    @staticmethod
    def recv_login_request(*args, **kwds):
        print('Connected to server.')

    @staticmethod
    def recv_chat_message(message):
        print(message)

    @staticmethod
    def recv_player_position_and_look(**kwds):
        global position_and_look
        with global_lock: position_and_look = kwds

#    @staticmethod
#    def recv_update_health(**kwds):
#        global health
#        with global_lock: health = kwds

    @staticmethod
    def recv_client_disconnect(reason):
        print('Disconnected from server: %s' % reason)
        sys.exit()    


def run_send_position():
    while True:
        time.sleep(0.05)
        with global_lock:
            if position_and_look is None: continue
            connection.sender.send_player_position_and_look(**position_and_look)
send_position = threading.Thread(target=run_send_position, name='send_position')
send_position.daemon = True
send_position.start()


#def run_respawn():
#    while True:
#        time.sleep(1)
#        with global_lock:
#            if health is None: continue
#            if health['health'] > 1: continue
#        time.sleep(1)
#        with global_lock:
#            connection.sender.send_client_status(1)
#respawn = threading.Thread(target=run_respawn, name='respawn')
#respawn.daemon = True
#respawn.start()


def run_command(cmd):
    try: exec cmd
    except Exception: traceback.print_exc()

def run_read_stdin():
    while True:
        msg = raw_input().decode('utf8')
        with global_lock:
            if msg.startswith('!'):
                run_command(msg[1:])
                continue
            while len(msg) > 100:
                connection.sender.send_chat_message(msg[:97] + '...')
                msg = '...' + msg[97:]
            connection.sender.send_chat_message(msg)
read_stdin = threading.Thread(target=run_read_stdin, name='read_stdin')
read_stdin.daemon = True
read_stdin.start()


session = MC2Session(auth_server) if auth_server else Session()
session.connect(username, password)
connection = Connection(session, EventManager, Receiver, Sender)
connection.name = 'connection'
connection.eventmanager.apply(Client)
connection.connect(host, port)

try:
    while connection.is_alive():
        connection.join(0.1)
except KeyboardInterrupt:
    connection.disconnect()
    print('Disconnected from server.')