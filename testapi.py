#!/usr/bin/env python
# -*- coding: utf-8 -*-

import apikey
import simplejson as json
from urllib import urlopen, urlencode
from xml.dom import minidom

text = raw_input()

query1 = [ 
        ('appid', apikey.YAHOO_ID),
        ('output', 'json'),
        ('sentence', text)
        ]

result = json.load(
        urlopen(
            'http://jlp.yahooapis.jp/KeyphraseService/V1/extract?' + urlencode(query1)
            )
        )
print '-- Keyphrase --'
for k, v in result.iteritems():
    print k, v

query2 = [ 
        ('appid', apikey.YAHOO_ID),
        ('results', 'uniq'),
        ('uniq_filter', '9'),
        ('response', 'surface'),
        ('sentence', text)
        ]

result = urlopen(
        'http://jlp.yahooapis.jp/MAService/V1/parse?' + urlencode(query2)
        ).read()
dom = minidom.parseString(result)

print '-- MA --'
words = dom.getElementsByTagName('surface')
for w in words:
    text = w.lastChild.nodeValue
    print text

'''
query3 = [ 
        ('appid', apikey.YAHOO_ID),
        ('sentence', text)
        ]

result = urlopen(
        'http://jlp.yahooapis.jp/DAService/V1/parse?' + urlencode(query2)
        ).read()
dom = minidom.parseString(result)

print '-- DA --'
words = dom.getElementsByTagName('Surface')
features = dom.getElementsByTagName('Feature')
for i in range(0, len(words)):
    text = words[i].lastChild.nodeValue
    feature = features[i].lastChild.nodeValue
    print text, feature
    '''
