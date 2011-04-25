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

        # exclude bot itself
        for tweet in batch:
            user = tweet.GetUser()
            if user.GetId() != config.MY_ID:
                friends_batch.append(tweet)

        # analyze and get the material
        while len(friends_batch) > 0:
            tweet = choice(friends_batch)
            user = tweet.GetUser()
            material = analyze(tweet.GetText())
            if material and not check_dup(user.GetScreenName(), material):
                return (user, material)
            else:
                friends_batch.remove(tweet)

    return None

def check_dup(username, material):
    result = db.GqlQuery('SELECT * FROM History WHERE username=:1 AND material=:2', 
            username, material)
    if result.count() > 0:
        logging.debug('duplicated user %s and material %s in history', (username, material))
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
    logging.debug('analyzed and  got %s' % repr(result))
    return choice(result.keys())


@app.route('/fetch_and_post_material')
def do_fetch_and_post_material():
    result = fetch_material()
    if result:
        user, material = result
        try:
            status = api.PostUpdate(u'@%s はうんこカレーに「%s」を入れた' % (user.GetScreenName(), material))
            logging.debug('posted %s' % status.GetText())
            return status.GetText()
        except twitter.TwitterError, e:
            logging.debug('duplicated user and material %s', (user.GetScreenName(), material))
            return 'duplicated: user @%s with material %s' % (user.GetScreenName(), material)
        finally:
            History(username=user.GetScreenName(), material=material).put()
    else:
        logging.debug('material not found')
        return 'material not found'

def is_admin_user():
    if users.get_current_user() != admin_user:
        return False
    else:
        return True

if __name__ == '__main__':
    app.run()
