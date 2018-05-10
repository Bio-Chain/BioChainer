#!/usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import print_function

import json
import re
import threading
import traceback

try:
    from urllib.parse import urlencode
    from urllib.request import urlopen, Request
    from urllib.error import HTTPError
    import queue
except ImportError:
    from urllib import urlencode
    from urllib2 import urlopen, Request, HTTPError
    import Queue as queue


CODING = 'utf-8'

# TODO add webhook support
class ChainBot:

    def __init__(self, config_name='config.json'):
        with open(config_name) as f:
            config = json.load(f)
        self.token          = config['bot_token']
        self.end_name       = config['end_name']
        self.baseurl        = 'https://api.telegram.org/bot%s' % self.token
        self.last_update    = 0
        self.updates        = queue.Queue()
        self.raw_chain      = {}
        self.current_chain  = []
        self.all_chains     = []

    def _get(self, method, query=None):
        header = {'Content-type': 'application/json'}
        req = Request('%s/%s' % (self.baseurl, method), json.dumps(query).encode(CODING) if query else None, header)
        try:
            data = json.loads(urlopen(req).read().decode(CODING))
        except HTTPError as e:
            print(e.read().decode(CODING))
            raise
        else:
            return data

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
        res = self._get('sendMessage', {'chat_id': chat_id, 'text': text})
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

    def updateChain(self, start, end=None):
        if end is None:
            end = self.end_name

        chain_users = {}
        u_is_private, u_users = self.getAts(start)
        if not u_is_private:
            return

        stack = [(start, u_users)]
        while True:
            print('STACK:', stack, len(stack))
            print('CHAIN:', chain_users)

            if len(stack) == 0:
                break

            current, users = stack.pop()

            for user in users:
                if current not in chain_users:
                    chain_users[current] = []

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

    def getChainRange(self, start, end=None, sub_chain=[], all_chains=False, upper_path=[]):
        if end is None:
            end = self.end_name

        if start not in self.raw_chain:
            return sub_chain[:]

        if all_chains:
            if start in upper_path:
                sub_chain.append(start)
                sub_chain.append('...')
                return sub_chain[:]
            upper_path.append(start)

        elif start in sub_chain or start == end:
            return sub_chain[:]

        sub_chain.append(start)
        longest = sub_chain[:]

        for user in self.raw_chain[start]:
            if all_chains:
                temp = self.getChainRange(user, end, sub_chain[:-1], all_chains, upper_path[:])
                if len(self.raw_chain[start]) == 1:
                    for item in temp:
                        longest.append(item)
                else:
                    longest.append([])
                    for item in temp:
                        longest[-1].append(item)

            else:
                temp = self.getChainRange(user, end, sub_chain[:])
                if len(temp) > len(longest):
                    longest = temp[:]

        return longest

    def stringChain(self):
        if self.raw_chain is None or self.current_chain is None:
            return
        lon = len(self.current_chain)
        return 'Chain Length is %d\n#Chain%d\n' % (lon, lon) + b' \xe2\x86\x92 '.decode(CODING).join(self.current_chain)

    def stringSubChains(self, chain_list=None, dpt=0):
        if not chain_list:
            return
        text = ''
        earrow = b'\xe2\x86\x91'.decode(CODING)
        rarrow = b'\xe2\x86\x92'.decode(CODING)
        sarrow = b'\xe2\x86\x93'.decode(CODING)
        has_sub = False
        sub_dpt = dpt
        for item in chain_list:
            if type(item) is list:
                has_sub = True
                sub_dpt = dpt
                text += sarrow + ' ' + str(dpt) + ' ' + sarrow + '\n'
                text += self.stringSubChains(item, dpt)
                continue
            text += '' + str(dpt) + ' ' + rarrow + ' ' + item + '\n'
            dpt += 1
        if has_sub:
            text += earrow + ' ' + str(sub_dpt) + ' ' + earrow + '\n'
        return text

    def buildChain(self, username, end=None):
        self.raw_chain = self.updateChain(username, end)
        # Never forget: persistent name on chain if [] is not passed from here
        # Not sure if it is a python bug or not
        self.current_chain = self.getChainRange(username, end, [])
        self.all_chains = self.getChainRange(username, end, [], True, [])

def main():
    bot = ChainBot()

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
                if cmd == 'allchainstest':
                    if len(args) == 0:
                        bot.sendMessage(chat_id, 'Please specify a target user')
                        continue
                    chain = bot.getChainRange(args[0], None, [], True, [])
                    print(chain)
                    text = 'Chain\n' + bot.stringSubChains(chain)
                    bot.sendMessage(chat_id, ''.join(text[:4096]))

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        pass
