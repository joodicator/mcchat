from McClient.networking.Exceptions import *
from McClient.networking.Session import *
import urllib
import urllib2

class MC2Session(BaseSession):
    __LOGIN_HEADER = {"Content-Type": "application/x-www-form-urlencoded"}
    VERSION = 13

    def __init__(self, auth):
        self.__LOGIN_URL = 'http://%s/game/getversion.php?proxy=2.9' % auth
        self.__JOIN_URL = 'http://%s/game/joinserver.php' % auth

    def connect(self, username, password):
        """Connects minecraft.net and gets a session id."""
        data = urllib.urlencode({"user": username,
                                 "password": password,
                                 "version": self.VERSION})

        req = urllib2.Request(self.__LOGIN_URL, data, self.__LOGIN_HEADER)
        opener = urllib2.build_opener()
        try:
            response = opener.open(req, None, 10).read()
        except urllib2.URLError as e:
            raise SessionError('Authentication failed: %s' % e)

        if ':' not in response:
            raise SessionError('Authentication failed: %s' % response)
        
        response = response.split(":")

        self.online = True

        self.game_version = response[0]
        # field #1 is deprecated, always!
        self.username = response[2]
        self.sessionID = response[3]

    def joinserver(self, serverID):
        url = self.__JOIN_URL + "?user=%s&sessionId=%s&serverId=%s" \
            % (self.username, self.sessionID, serverID)

        response = urllib2.urlopen(url).read()

        if response != "OK":
            raise SessionError("Authentication failed: %s" % response)

        return True
