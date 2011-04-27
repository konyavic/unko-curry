#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

import simplejson as json

import config
import apikey

from urllib import urlopen, urlencode
from xml.dom import minidom

if __name__ == '__main__':
    # for console debug and tuning

    from messages import SPECIAL
    from messages import BANNED

    special_list = [s[0] for s in SPECIAL]
    
    def is_special(word):
        if word in special_list:
            print 'hit special list: %s' % word
            return True
        else:
            return False

    def is_banned(word):
        if word in BANNED:
            print 'hit banned list: %s' % word
            return True
        else:
            return False
else:
    from effects import Special
    from effects import Banned

    def is_special(word):
        if Special.get_by_key_name(word):
            return True
        else:
            return False

    def is_banned(word):
        if Banned.get_by_key_name(word):
            return True
        else:
            return False

def analyze(text, count):
    text = remove_entities(text)
    ks_list = get_yahoo_ks(text)
    ma_list = get_yahoo_ma(text)

    result = []
    for keyphrase in ks_list:
        if is_special(keyphrase) and not keyphrase in result:
            result.append(keyphrase)
            if len(result) >= count:
                break

        start = len(keyphrase) - 1
        end = 0
        for word in ma_list:
            pos = keyphrase.find(word)
            if pos >= 0:
                start = pos if pos < start else start
                end = pos + len(word) if end < (pos + len(word)) else end

        word = keyphrase[start:end]
        if (end - start) > 0 and not word in result:
            result.append(word)

        if len(result) >= count:
            break

    return result

def remove_entities(text):
    '''remove ids, lists, links'''

    text = re.sub('#[^ ]*', '', text)
    text = re.sub('@[^ ]*', '', text)
    text = re.sub('http[^ ]*', '', text)
    return text

def get_yahoo_ks(text):
    query = [ 
            ('appid', apikey.YAHOO_ID),
            ('output', 'json'),
            ('sentence', text)
            ]

    try:
        result = json.load(
                urlopen(
                    config.YAHOO_KS_URL + urlencode(query)
                    )
                )
        keys = result.keys()
        keys.sort(key=lambda x:result[x], reverse=True)
        processed = []
        for key in keys:
            processed += key.split()

        return processed
    
    except:
        return []

def get_yahoo_ma(text):
    query = [ 
            ('appid', apikey.YAHOO_ID),
            ('results', 'uniq'),
            ('uniq_filter', '9'),
            ('response', 'surface'),
            ('sentence', text)
            ]

    try:
        result = urlopen(
                config.YAHOO_MA_URL + urlencode(query)
                ).read()
        dom = minidom.parseString(result)
        words = dom.getElementsByTagName('surface')
        processed = []
        for w in [w.lastChild.nodeValue for w in words]:
            if is_banned(w):
                continue

            processed.append(w)

        return processed

    except:
        return []


if __name__ == '__main__':
    text = raw_input()
    text = remove_entities(text)
    print text

    ret = get_yahoo_ks(text)
    print '-- KS result --'
    for r in ret:
        print r

    ret = get_yahoo_ma(text)
    print '-- MA result --'
    for r in ret:
        print r
    
    print '-- analyzed --'
    result = analyze(text, 10)
    for r in result:
        print r
