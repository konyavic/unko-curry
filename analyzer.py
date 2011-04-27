#!/usr/bin/env python
# -*- coding: utf-8 -*-

import re

import simplejson as json

import config
import apikey

from urllib import urlopen, urlencode
from xml.dom import minidom

def analyze(text, count):
    text = remove_entities(text)
    ks_list = get_yahoo_ks(text)
    ma_list = get_yahoo_ma(text)

    result = []
    for keyphrase in ks_list:
        #TODO: output any word in special list if it is contained in this keyphrase
        start = len(keyphrase) - 1
        end = 0
        for word in ma_list:
            pos = keyphrase.find(word)
            if pos >= 0:
                start = pos if pos < start else start
                end = pos + len(word) if end < (pos + len(word)) else end

        if (end - start) > 0:
            #TODO: do not output keyphrase in black list
            result.append(keyphrase[start:end])

        if len(result) > count:
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
        return keys
    
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
        return [w.lastChild.nodeValue for w in words]

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
    result = analyze(text, config.TWEET_MATERIAL_MAX)
    for r in result:
        print r
