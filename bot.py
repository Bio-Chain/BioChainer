#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import json
import re
import threading
import traceback
from time import sleep

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    import queue
except ImportError:
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError
    import Queue as queue


BOT_TOKEN = 'insert bot token here'
END_NAME = 'insert endpoint here'
CODING = 'utf-8'

# TODO add webhook support
class ChainBot:

    def __init__(self, token):
        self.token          = token
        self.baseurl        = 'https://api.telegram.org/bot%s' % token
        self.last_update    = 0
        self.updates        = queue.Queue()
        self.raw_chain      = {}
        self.current_chain  = []

    def _get(self, method, query=None, headers={}):
        if query:
            req = Request('%s/%s?%s' % (self.baseurl, method, urlencode(query)), headers=headers)
        else:
            req = Request('%s/%s' % (self.baseurl, method), headers=headers)
        return json.loads(urlopen(req).read().decode(CODING))

    def _pollUpdates(self):
        updates = self._get('getUpdates', {'offset': self.last_update})
        if not updates['ok'] or not updates['result']:
            return
        self.last_update = updates['result'][-1]['update_id'] + 1
        for update in updates['result']:
            self.updates.put(update)

    def getUpdate(self):
        while self.updates.qsize() == 0:
            self._pollUpdates()
        return self.updates.get()

    def pinMessage(self, message):
        res = self._get('pinMessage', {'chat_id': message['username'],
                                       'message_id': message['message_id'],
                                       'disable_notification': 'True'})
        return res

    def getPinned(self, chat_id):
        res = self.getChat(chat_id)
        if res['type'] not in ('supergroup', 'channel'):
            return
        return res['pinned_message']

    def getChat(self, chat_id):
        res = self._get('getChat', {'chat_id': chat_id})
        if 'result' not in res:
            return res
        return res['result']

    def getMe(self):
        res = self._get('getMe')
        if 'result' not in res:
            return res
        return res['result']

    def sendMessage(self, chat_id, text):
        res = self._get('sendMessage', {'chat_id': chat_id, 'text': text, 'markdown': 'HTML'})
        if 'result' not in res:
            return res
        return res['result']

    def updateSelf(self):
        self.me = self.getMe()

    def isCommand(self, message):
        if 'entities' in message:
            return message['entities'][0]['offset'] == 0 and message['entities'][0]['type'] == 'bot_command'

    def isMessage(self, update):
        return 'message' in update

    def getCommand(self, text):
        cmd = re.match(r'^/(\w+)@?(\w+)? ?(.*)$', text)
        if cmd:
            if cmd.group(3) is None:
                return cmd.group(1), cmd.group(2), []
            return cmd.group(1), cmd.group(2), cmd.group(3).split()

    def getAts(self, username):
        req = Request('https://t.me/%s' % username)
        data = urlopen(req).read().decode(CODING)
        parsed = re.search(r'<meta property="og:description" content="(.*?)">', data, re.S)
        if not parsed:
            return
        is_private = re.findall(r'<a class="tgme_action_button_new" href="tg://resolve\?domain=.*?">Send Message</a>', data)
        return is_private != [], re.findall(r'@(\w+)', parsed.group(0))

    def updateChain(self, username, end=END_NAME):
        chain_users = {}
        u_is_private, u_users = self.getAts(username)
        if not u_is_private:
            return
        stack = [(username, u_users)]
        while True:
            print('STACK:', stack, len(stack))
            print('CHAIN:', chain_users)
            if len(stack) == 0:
                break
            current, users = stack.pop()
            if current not in chain_users:
                chain_users[current] = []
            for user in users:
                if user.lower().endswith('bot'):
                    continue
                if user in chain_users or user == end:
                    chain_users[current].append(user)
                    continue
                is_private, s_users = self.getAts(user)
                if not is_private:
                    continue
                chain_users[current].append(user)
                stack.append((user, s_users))
        return chain_users

    def getChainRange(self, start, end=END_NAME, sub_chain=[]):
        # print(sub_chain)
        # print(start)
        if start not in self.raw_chain or start in sub_chain or start == end:
            return sub_chain[:]
        sub_chain.append(start)
        longest = sub_chain[:]
        for user in self.raw_chain[start]:
            temp = self.getChainRange(user, end, sub_chain[:])
            if len(temp) > len(longest):
                longest = temp[:]
        return longest

    def stringChain(self):
        if self.raw_chain is None or self.current_chain is None:
            return
        lon = len(self.current_chain)
        return 'Chain Length is %d\n#Chain%d\n' % (lon, lon) + b' \xe2\x86\x92 '.decode(CODING).join(self.current_chain)

    def buildChain(self, username, end=END_NAME):
        self.raw_chain = self.updateChain(username, end)
        # Never forget: persistent name on chain if [] is not passed from here
        # Not sure if it is a python bug or not
        self.current_chain = self.getChainRange(username, end, [])
        print(self.current_chain)

def main():
    bot = ChainBot(BOT_TOKEN)

    bot.updateSelf()
    print('Updated')

    while True:
        update = bot.getUpdate()
        print(update)
        if bot.isMessage(update):
            message = update['message']
            if bot.isCommand(message):
                cmd, target, args = bot.getCommand(message['text'])
                chat_id = message['chat']['id']
                print(cmd, target, args)
                if target not in (None, bot.me['username']):
                    continue
                if cmd == 'update':
                    if len(args) == 0:
                        bot.sendMessage(chat_id, 'Please specify a target user')
                        continue
                    bot.sendMessage(chat_id, 'Building chain...\nPlease wait')
                    bot.buildChain(args[0])
                    bot.sendMessage(chat_id, bot.stringChain())
                if cmd == 'current':
                    bot.sendMessage(chat_id, bot.stringChain())

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
