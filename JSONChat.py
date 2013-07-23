import json
import re
import os.path
from itertools import *


class DecodeError(Exception):
    pass


def load_language(file):
    language = dict()
    for line in file:
        try: name, value = line.split('=', 1)
        except ValueError: continue
        language[name] = value.strip()
    return language

with open(os.path.join(os.path.dirname(__file__), './en_US.lang')) as file:
    language = load_language(file)


def decode_string(data):
    try: return decode_struct(json.loads(data))
    except DecodeError: return data

def decode_struct(data):
    if type(data) is str or type(data) is unicode:
        return data
    elif type(data) is list:
        return ''.join(decode_struct(part) for part in data)
    elif type(data) is dict:
        if 'text' in data:
            return decode_struct(data['text'])
        elif 'translate' in data and 'using' in data:
            using = [decode_struct(item) for item in data['using']]
            return translate(data['translate'], using)
    raise DecodeError

def translate(id, params):
    if id not in language: raise DecodeError
    format = re.sub(r'%(\d+)\$', r'%(\1)', language[id])
    try: return format % {str(i+1):p for (i,p) in izip(count(), params)}
    except TypeError: raise DecodeError
