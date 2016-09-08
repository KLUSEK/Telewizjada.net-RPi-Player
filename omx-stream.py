#!/usr/bin/env python
# -*- coding: utf-8 -*-

print 'Loading stream player...'

import curses
import os
import sys
import subprocess
import time
import shutil
import signal
import urllib, urllib2, httplib, cookielib, socket, json
from xml.etree import ElementTree


### CONFIGURATION ###


# Streamlist auto-refresh rate (in seconds)
REFRESH_RATE = 60
HOST_URL = 'http://www.telewizjada.net'
COOKIE_JAR = os.path.dirname(sys.argv[0]) + '/cookie.cookie'
CLIENT_UA = 'Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/48.0.2564.109 Safari/537.36'

### END OF CONFIGURATION


class Lang:
    SERVER_STATUS = 'Server status'
    SERVER_ONLINE = 'Online'
    SERVER_OFFLINE = 'Offline'
    SERVER_NOSTREAMS = 'Unable to get stream list from the server. Wait for refresh ...'
    SERVER_PLAYERROR = 'Error while initiating playing accured. Wait for refresh ...'
    
    APP_EXIT = 'Exit'
    APP_REFRESH = 'Refresh'
    APP_NAVIGATE = 'Navigate'
    APP_PLAY = 'Play'
    
    APP_TITLE = 'Stream list'
    APP_ERROR = 'ERROR'
    APP_INFO = 'INFO'
    APP_PLAY_STARTING = 'Please wait. Stream source loading ...'
    SYSTEM_REBOOT = 'REBOOT SYSTEM'
    
##### END OF Lang Class


class Network:        
    def getJsonFromExtendedAPI(self, url, post_data=None, save_cookie=False, load_cookie=False, cookieFile=None, jsonLoadsResult=False):
        result_json = None
        customOpeners = []
        cj = cookielib.LWPCookieJar()

        def urlOpen(req, customOpeners):
            if len(customOpeners) > 0:
                opener = urllib2.build_opener(*customOpeners)
                response = opener.open(req, timeout=4)
            else:
                response = urllib2.urlopen(req, timeout=4)
            return response

        try:
            if cookieFile is not None:
                customOpeners.append(urllib2.HTTPCookieProcessor(cj))
                if load_cookie == True:
                    cj.load(cookieFile, ignore_discard=True)

            headers = {'User-Agent': CLIENT_UA}
            data = urllib.urlencode(post_data)
            reqUrl = urllib2.Request(url, data, headers)

            failedCounter = 0
            while failedCounter < 50:
                try:
                    raw_json = urlOpen(reqUrl, customOpeners)
                    result_json = raw_json.read()
                    if jsonLoadsResult == True:
                        result_json = json.loads(result_json)
                    break
                except (httplib.IncompleteRead, socket.timeout) as ex:
                    failedCounter += 1
                    time.sleep(.050)

            if cookieFile is not None and save_cookie == True:
                cj.save(cookieFile, ignore_discard=True)

        except (urllib2.URLError, NameError, ValueError, httplib.BadStatusLine) as ex:
            return False

        return result_json
    
    def getCookieItem(self, cookiefile, item):
        ret = ''
        if os.path.isfile(cookiefile):
            cj = cookielib.LWPCookieJar()
            cj.load(cookiefile, ignore_discard=True)
            for cookie in cj:
                if cookie.name == item:
                    ret = cookie.value
        return ret


##### END OF Network Class

class Terminal:
    def __init__(self, screen):
        # Because I'd like to see some ÄÄĂłĹÄ (rather than garbage):
        # locale.setlocale(locale.LC_ALL, '')
        # code = locale.getpreferredencoding()
        
        global lang
        lang = Lang()

        self.network = Network()
        self.server_status = False

        self.screen = screen
        self.height, self.width = self.screen.getmaxyx()
        self.screen.nodelay(0)
        self.screen.keypad(0)
        curses.noecho()
        # curses.nocbreak()
        curses.curs_set(0)

        curses.start_color()

        self.cp = [] # color_pairs holder
        self.slist = None # sub-window to display stream list
        self.selected = 0
	
	sys.setrecursionlimit(1000000)

    def color(self, c):
        if c == 'default':
            return -1
        elif c == 'black':
            return curses.COLOR_BLACK
        elif c == 'red':
            return curses.COLOR_RED
        elif c == 'green':
            return curses.COLOR_GREEN
        elif c == 'yellow':
            return curses.COLOR_YELLOW
        elif c == 'blue':
            return curses.COLOR_BLUE
        elif c == 'magenta':
            return curses.COLOR_MAGENTA
        elif c == 'cyan':
            return curses.COLOR_CYAN
        elif c == 'white':
            return curses.COLOR_WHITE


    def get_cp(self, colors):
        p_number = None

        for i in range(0, len(self.cp)-1):
            if (self.cp[i][0] == colors[0] and self.cp[i][1] == colors[1]):
                p_number = i+1
                break

        if not p_number:
            curses.init_pair(len(self.cp)+1, self.color(colors[0]), self.color(colors[1]))
            self.cp.append(colors)
            p_number = len(self.cp)

        return curses.color_pair(p_number)


    def draw_streamlist(self, streamlist, selected=0):
        # default margin for new sub-window
        win_margin = [3, 5, 7, 5]
        win_padding = [3, 10, 3, 5]
        win_size = None
        win_list_size = None
        win_pos = None

        win_size = [min(self.height-win_margin[0]-win_margin[2], len(streamlist)+win_padding[0]+win_padding[2]), get_longest(streamlist)+win_padding[1]+win_padding[3]]
        win_list_size = win_size[0]-win_padding[0]-win_padding[2]

        # estimate the position of new window
        win_pos = [int(self.height/2 - win_size[0]/2), int(self.width/2 - win_size[1]/2)]

        newwin = self.screen.subwin(win_size[0], win_size[1], win_pos[0], win_pos[1])
        newwin.scrollok(True)
        newwin.bkgd(' ', self.get_cp(['red', 'white']))
        newwin.border()
        newwin.addstr(0, center(win_size[1], ' %s ' % lang.APP_TITLE), ' %s ' % lang.APP_TITLE.upper(), curses.A_REVERSE)

        ii = 0
        offset = min(max(selected-int(win_list_size/2), 0), len(streamlist)-win_list_size)

        # calculate the scrollbar position
        if (len(streamlist) > win_list_size):
            step_length = float(win_list_size) / float(len(streamlist)-win_list_size)

            newwin.addstr(int(win_padding[0]+step_length*offset-1), win_size[1]-1, ' ', curses.A_REVERSE)
            newwin.addstr(int(win_padding[0]+step_length*offset), win_size[1]-1, ' ', curses.A_REVERSE)

        for i in range(offset, min(offset+win_list_size, len(streamlist))):
            if i == selected:
                newwin.addstr(win_padding[0]+ii, win_padding[3], ' %s ' % streamlist[i]['title'], curses.A_REVERSE)
            else:
                newwin.addstr(win_padding[0]+ii, win_padding[3], ' %s ' % streamlist[i]['title'], self.get_cp(['black', 'white']))
            ii += 1

        return newwin

    def draw_status(self, status=False):
        padding = [15, 2]

        self.screen.addstr(padding[1], self.width-len(lang.SERVER_STATUS)-padding[0], '%s: ' % lang.SERVER_STATUS)
        if not status:
            self.screen.addstr(padding[1], self.width-padding[0]+2, ' %s ' % lang.SERVER_OFFLINE, self.get_cp(['white', 'red']))
        else:
            self.screen.addstr(padding[1], self.width-padding[0]+2, ' %s ' % lang.SERVER_ONLINE, self.get_cp(['black', 'green']))
            

    def draw_legend(self, items):
        padding = [4, 2]

        x = 0
        for i in items:
            self.screen.addstr(self.height-padding[1], x+padding[0], ' %s ' % i, curses.A_REVERSE)
            self.screen.addstr(self.height-padding[1], x+padding[0]+len(i)+3, items[i])
            x += 8+len(i)+len(items[i])

    def draw_remote_legend(self, items):
        padding = [4, 2]
        
        str_length = 0
        for i in items:
            str_length += 8+len(items[i])

        x = self.width-str_length-padding[0]
        for i in items:
            self.screen.addstr(self.height-padding[1], x+padding[0], '  ', self.get_cp(['white', i]))
            self.screen.addstr(self.height-padding[1], x+padding[0]+3, items[i])
            x += 8+len(items[i])
            
    def draw_popup(self, type, str):
        # default margin for new sub-window
        win_padding = [3, 3]
        win_size = None
        win_list_size = None
        win_pos = None

        # estimate the size of new window
        win_size = [win_padding[0]*2+1, len(str)+win_padding[1]*2]

        # estimate the position of new window
        win_pos = [int(self.height/2 - win_size[0]/2), int(self.width/2 - win_size[1]/2)]

        if type == 'info':
            title = lang.APP_INFO
        else:
            title = lang.APP_ERROR

        newwin = self.screen.subwin(win_size[0], win_size[1], win_pos[0], win_pos[1])
        newwin.scrollok(True)
        newwin.bkgd(' ', self.get_cp(['red', 'white']))
        newwin.border()
        newwin.addstr(0, center(win_size[1], ' %s ' % title), ' %s ' % title.upper(), curses.A_REVERSE)

        newwin.addstr(win_padding[0], win_padding[1], str)

    def select_prev(self, streamlist):
        if streamlist and len(streamlist) > 0 and self.selected > 0:
            self.selected -= 1
        
        self.slist = self.draw_streamlist(streamlist, self.selected)


    def select_next(self, streamlist):
        if streamlist and len(streamlist) > 0 and self.selected < len(streamlist)-1:
            self.selected += 1

        self.slist = self.draw_streamlist(streamlist, self.selected)

    def getStreamList(self):
        try:
            data = self.network.getJsonFromExtendedAPI('%s/get_channels.php' % HOST_URL, post_data={}, jsonLoadsResult=True)
            params = []
            for item in data['channels']:
                if item['online'] == 0:
                    continue
#                params.append({'title': item['displayName'].encode('utf-8'), 'url': item['url'].encode('utf-8'), 'cid': item['id']})
                params.append({'title': item['displayName'].encode('utf-8'), 'cid': item['id']})

            return sorted(params, key=lambda a: a['title'].lower())
        except Exception, e:
            return False

    def main(self, info=False, error=False, msg='', isPlaying=None, player_pid=None):
        self.screen.border()
        self.draw_legend({'E': lang.APP_EXIT, 'ARROWS': lang.APP_NAVIGATE, 'ENTER': lang.APP_PLAY})
        self.draw_remote_legend({'red': lang.SYSTEM_REBOOT})

        # Get list of available streams
        streamList = self.getStreamList()

        if info:
            self.draw_popup('info', msg)
#            time.sleep(20)
#            self.screen.clear()
#            self.main()
        elif error:
            error = True
            self.draw_popup('error', msg)
            time.sleep(10)
            self.screen.clear()
            self.main()
            return 0
        elif not streamList or len(streamList) == 0:
            error = True
            self.draw_popup('error', lang.SERVER_NOSTREAMS)
            time.sleep(10)
            self.screen.clear()
            self.main()
            return 0
        else:
            # Sub-window to display stream list
            self.slist = self.draw_streamlist(streamList, self.selected)

        self.draw_status(streamList)

        timestamp = int(time.time())

        while True:
            now = int(time.time())
            key = self.screen.getch()

            if key == 65 and not isPlaying and not error: # UP pressed
                self.screen.touchwin()
                self.slist.clear()
                self.select_prev(streamList)

            elif key == 66 and not isPlaying and not error: # DOWN
                self.screen.touchwin()
                self.slist.clear()
                self.select_next(streamList)

            elif key == ord('r') and not isPlaying:
                self.screen.clear()
                self.main()
                break

            elif key == curses.KEY_RESIZE: # Window resize pseudo-key
                self.height, self.width = self.screen.getmaxyx()
                self.screen.clear()
                self.main()
                break

            elif key == ord('e') and not isPlaying:
                self.screen.clear()
                curses.endwin()
                break
                
            elif key == ord('p'):
                self.screen.clear()
                curses.endwin()
                subprocess.Popen('sudo systemctl reboot', shell=True)
                break

            
            # Player control begins
            
            elif key == 10 and not isPlaying and not error: # ENTER
                isPlaying = True
                self.screen.clear()

                pid = play(streamList[self.selected])

                if not pid:
                    self.main(error=True, msg=lang.SERVER_PLAYERROR)
                else:
                    self.main(info=True, msg=lang.APP_PLAY_STARTING, isPlaying=True, player_pid=pid)
                break


            elif key == ord('c') and isPlaying:
                isPlaying = False
                omxpid = getProcessPID('omxplayer.bin')
                if omxpid:
#                    os.kill(omxpid, signal.SIGINT)
                    os.kill(omxpid, signal.SIGKILL)
  
                self.screen.clear()
                self.main()
		break

#            elif isPlaying and not player_pid is None and not os.path.exists('/proc/'+str(player_pid)): # proces juz nie istnieje
#                isPlaying = False
#		self.screen.clear()
#		self.main()
#                break

            elif not isPlaying and now-timestamp > REFRESH_RATE: # auto-odswiezanie
                self.screen.clear()
                self.main()
                break


##### END OF Terminal Class


def center(width, str):
    return int(width/2 - len(str)/2)


def get_longest(streamlist):
    results = []

    for i in range(0, len(streamlist)):
        results.append(len(streamlist[i]['title']))

    return int(max(results))


def play(item):
    # subprocess.Popen('killall omxpayer.bin', stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    # subprocess.Popen('clear', stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)

    network = Network()
    data = {'cid': item['cid']}
    output = network.getJsonFromExtendedAPI('%s/get_mainchannel.php' % HOST_URL, post_data=data, jsonLoadsResult=True)
    if output == False:
        return False

    data = {'url': output['url']}
    output = network.getJsonFromExtendedAPI('%s/set_cookie.php' % HOST_URL, post_data=data, cookieFile=COOKIE_JAR, save_cookie=True)
    if output == False:
        return False

    data = {'cid': item['cid']}
    output = network.getJsonFromExtendedAPI('%s/get_channel_url.php' % HOST_URL, post_data=data, cookieFile=COOKIE_JAR, load_cookie=True, jsonLoadsResult=True)
    if output == False:
        return False

    m3u8_url = output[u'url']
    msec = network.getCookieItem(COOKIE_JAR, 'msec')
    sessid = network.getCookieItem(COOKIE_JAR, 'sessid')

    proc = subprocess.Popen("livestreamer --http-cookies \"sessid=%s; msec=%s\" --http-headers \"User-Agent=%s; Referer=%s/live.php?cid=%s\" -Q --hls-segment-timeout 30 \"hlsvariant://%s\" best -np \"omxplayer -o hdmi --blank --live --timeout 30\"" % (sessid, msec, CLIENT_UA, HOST_URL, item['cid'], m3u8_url), stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)

    return proc.pid


def getProcessPID(name):
    p = subprocess.Popen(['ps', '-A'], stdout=subprocess.PIPE)
    out = p.communicate()

    for line in out[0].splitlines():
        if name in line:
            return int(line.split(None, 1)[0])
    return False


def main():
    # checking if omxplayer exists
    popen = subprocess.Popen('omxplayer', stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    if (not popen.stdout.read()):
        print 'You must install omxplayer to use this program.'
        return 0

    # checking if iconv exists
    popen = subprocess.Popen('livestreamer', stderr=subprocess.PIPE, stdout=subprocess.PIPE, shell=True)
    if (not popen.stdout.read()):
        print 'You must install livestreamer to use this program.'
        return 0

    terminal = Terminal(curses.initscr())
    terminal.main()


if __name__ == '__main__':
    main()
