#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import twitter
import simplejson as json

import apikey
import config

from urllib import urlopen, urlencode
from random import choice

from flask import Flask
from google.appengine.ext import db

from history import History

app = Flask(__name__)

# TODO: should be placed in a proper scope
logging.getLogger().setLevel(logging.DEBUG)

api = twitter.Api(
        consumer_key = apikey.CONSUMER_KEY, 
        consumer_secret = apikey.CONSUMER_SECRET,
        access_token_key = apikey.ACCESS_TOKEN_KEY, 
        access_token_secret = apikey.ACCESS_TOKEN_SECRET,
        cache = None
        )

def fetch_material():
    for retry in range(1, 1 + config.FETCH_RETRY_MAX):
        batch = api.GetFriendsTimeline(count=config.FETCH_COUNT, page=retry)
        friends_batch = []

        # exclude tweets from bot itself
        for tweet in batch:
            user = tweet.GetUser()
            if user.GetId() != config.MY_ID:
                friends_batch.append(tweet)

        # analyze and pick material
        while len(friends_batch) > 0:
            tweet = choice(friends_batch)
            username = tweet.GetUser().GetScreenName()

            material_list = analyze(tweet.GetText())
            tmp_list = list(material_list)
            
            for material in tmp_list:
                if is_duplicated(username, material):
                    material_list.remove(material)

            if len(material_list) > 0:
                return (username, material_list)        
            else:
                friends_batch.remove(tweet)

    return None

def is_duplicated(username, material):
    result = db.GqlQuery('SELECT * FROM History WHERE username=:1 AND material=:2', 
            username, material)
    if result.count() > 0:
        logging.debug('duplicated user %s with material %s' % (username, material))
        return True
    else:
        return False

def get_query(sentence):
    return [ 
            ('appid', apikey.YAHOO_ID),
            ('output', 'json'),
            ('sentence', sentence)
            ]

def analyze(text):
    result = json.load(
            urlopen(
                config.YAHOO_KS_URL + '?' + urlencode(get_query(text.encode('utf-8')))
                )
            )

    logging.debug('analyzed material %s' % repr(result))

    material_list = []
    for i in range(0, min(len(result), config.TWEET_MATERIAL_MAX)):
        key = choice(result.keys())
        logging.debug('choiced %s' % key)
        del result[key]
        if is_material(key):
            material_list.append(key)

    logging.debug('picked material %s' % repr(material_list))
        
    return material_list

def is_material(keyword):
    keyword = keyword.encode('utf-8')
    for c in keyword:
        if ord(c) > 128:
            return True

    return False

@app.route('/fetch_and_post_material')
def do_fetch_and_post_material():
    result = fetch_material()
    if result:
        username, material_list = result
        material_str_list = []
        for material in material_list:
            material_str_list.append(u'「%s」' % material)

        material_str = u'、'.join(material_str_list)
        logging.debug('constructed material string %s' % material_str)

        try:
            status = api.PostUpdate(u'@%s はうんこカレーに%sを入れた' % (username, material_str))
            logging.debug('posted %s' % status.GetText())
            return status.GetText()

        except twitter.TwitterError, e:
            logging.debug('duplicated user %s with material %s', (username, material))
            return 'this post is duplicated'
        
        finally:
            History(username=username, material=material).put()

    else:
        logging.debug('material not found')
        return 'material not found'

if __name__ == '__main__':
    app.run()
