#!/usr/bin/env python2.7

from __future__ import print_function

import sys
import time
import os.path
import threading
import traceback
import socket
import argparse

from McClient.networking.NetworkHelper import NetworkHelper
from McClient.networking.Connection import Connection
from McClient.networking.Receiver import BaseReceiver
from McClient.networking.Receiver import Receiver
from McClient.networking.Sender import Sender
from McClient.networking.Exceptions import HandlerError
from McClient.Events import EventManager
from McClient import Utils

from McClient.networking.Session import OfflineSession
from McClient.networking.Session import Session
from MC2Session import MC2Session

from minecraft_query import MinecraftQuery

#==============================================================================#
DEFAULT_PORT = 25565

#==============================================================================#
def with_global_lock(func):
    def decorated(*args, **kwds):
        with global_lock: func(*args, **kwds)
    return decorated
NetworkHelper.respondFD = with_global_lock(NetworkHelper.respondFD)
NetworkHelper.respondFC = with_global_lock(NetworkHelper.respondFC)
NetworkHelper.respond00 = with_global_lock(NetworkHelper.respond00)

def fprint(*args, **kwds):
    print(*args, **kwds)
    kwds.get('file', sys.stdout).flush()

def eprint(*args, **kwds):
    fprint(*args, file=sys.stderr, **kwds)

def run_command(cmd):
    try: exec cmd
    except Exception: traceback.print_exc()
    for f in sys.stdout, sys.stderr: f.flush()

query_pending = set()
def query(key):
    query_pending.add(str(key))
    global_cond.notifyAll()        

#==============================================================================#
arg_parser = argparse.ArgumentParser()

arg_parser.add_argument(
    'address', metavar='host[:port]',
    help='The Minecraft server to connect to.')

arg_parser.add_argument(
    'username',
    help='Username to connect as.')

arg_parser.add_argument(
    'password', nargs='?',
    help='Password to authenticate with, if any.')

arg_parser.add_argument(
    'auth_server', nargs='?',
    help='A custom (Mineshafter Squared) authentication server.')

arg_parser.add_argument(
    '--protocol', metavar='VERSION', type=int,
    help='The protocol version to report to the Minecraft server.')

args = arg_parser.parse_args()

#==============================================================================#
address = args.address.rsplit(':', 1)
if len(address) == 2:
    host, port = address[0], int(address[1])
else:
    host, port = address[0], DEFAULT_PORT

global_lock = threading.Lock()
global_cond = threading.Condition(global_lock)
position_and_look = None
connection = None
players = set()
connected = False

if args.protocol is not None:
    Sender.protocol_version = args.protocol

#==============================================================================#
class Client(object):
    @staticmethod
    def recv_login_request(*args, **kwds):
        global connected
        with global_lock:
            connected = True
            fprint('Connected to server.')

    @staticmethod
    def recv_chat_message(message):
        with global_lock:
            fprint(message.encode('utf8'))

    @staticmethod
    def recv_player_position_and_look(**kwds):
        global position_and_look
        with global_lock: position_and_look = kwds

    @staticmethod
    def recv_client_disconnect(reason):
        global connected
        with global_lock:
            connected = False
            fprint('Disconnected from server: %s' % reason,
                file=sys.stdout if connected else sys.stderr)
        sys.exit()    

    @staticmethod
    def recv_player_list_item(player_name, online, ping):
        with global_lock:
            if online: players.add(player_name)
            else: players.remove(player_name)

#==============================================================================#
def run_send_position():
    while True:
        time.sleep(0.05)
        with global_lock:
            if position_and_look is None: continue
            connection.sender.send_player_position_and_look(**position_and_look)
send_position = threading.Thread(target=run_send_position, name='send_position')
send_position.daemon = True
send_position.start()

#==============================================================================#
@with_global_lock
def run_query():
    while True:
        while not query_pending: global_cond.wait()
        pending = query_pending.copy()
        query_pending.clear()
        for key in pending: fprint('!query pending %s' % key)
        global_lock.release()
        try:
            status = MinecraftQuery(host, port, timeout=1, retries=5).get_rules()
            global_lock.acquire()
            for key in pending:
                if key in status:
                    val = status[key]
                    if type(val) is list: val = ' '.join(val)
                    fprint('!query success %s %s' % (key, val))
                else:
                    fprint('!query failure %s no such key' % key)
        except socket.timeout as e:
            global_lock.acquire()
            for key in pending: fprint('!query failure %s %s' % (key, str(e)))
query_server = threading.Thread(target=run_query, name='query_server')
query_server.daemon = True
query_server.start()

session = (OfflineSession() if args.password is None
           else Session() if args.auth_server is None
           else MC2Session(args.auth_server))     
session.connect(args.username, args.password)

connection = Connection(session, EventManager, Receiver, Sender)
connection.name = 'connection'
connection.eventmanager.apply(Client)
connection.connect(host, port)

#==============================================================================#
def run_read_stdin():
    while True:
        msg = raw_input().decode('utf8')
        with global_lock:
            if msg.startswith('?'):
                run_command(msg[1:])
                continue
            while len(msg) > 100:
                connection.sender.send_chat_message(msg[:97] + '...')
                msg = '...' + msg[97:]
            if msg: connection.sender.send_chat_message(msg)
read_stdin = threading.Thread(target=run_read_stdin, name='read_stdin')
read_stdin.daemon = True
read_stdin.start()

#==============================================================================#
try:
    while connection.is_alive():
        connection.join(0.1)
except KeyboardInterrupt:
    connection.disconnect()

with global_lock:
    if connected: 
        fprint('Disconnected from server.')
