# -*- coding: utf-8 -*-

import twitter
import simplejson as json
import apikey

from urllib import urlopen, urlencode
from random import choice
from flask import Flask
from google.appengine.ext import db

app = Flask(__name__)

api = twitter.Api(
        consumer_key = apikey.CONSUMER_KEY, 
        consumer_secret = apikey.CONSUMER_SECRET,
        access_token_key = apikey.ACCESS_TOKEN_KEY, 
        access_token_secret = apikey.ACCESS_TOKEN_SECRET,
        cache = None
        )

@app.route('/post_update')
def post_update():
    post = choice(list(open('messages.txt')))
    api.PostUpdate(post)
    return post

FETCH_COUNT = 20
FETCH_RETRY_MAX = 2
MY_ID = 285389975

@app.route('/fetch_material')
def _fetch_material():
    result = fetch_material()
    if result:
        user, material = result
        return u'@%s はうんこカレーに「%s」を入れた' % (user.GetScreenName(), material)
    else:
        return 'material not found'

def fetch_material():
    for retry in range(0, FETCH_RETRY_MAX):
        batch = api.GetFriendsTimeline(count=FETCH_COUNT)
        for tweet in batch:
            user = tweet.GetUser()
            if user.GetId() == MY_ID:
                continue

            material = analyze(tweet.GetText())
            if material:
               return (user, material)

    return None

def get_query(sentence):
    return [ 
            ('appid', apikey.YAHOO_ID),
            ('output', 'json'),
            ('sentence', sentence)
            ]

YAHOO_MA_URL = 'http://jlp.yahooapis.jp/KeyphraseService/V1/extract'

def analyze(text):
    result = json.load(
            urlopen(
                YAHOO_MA_URL + '?' + urlencode(get_query(text.encode('utf-8')))
                )
            )
    return choice(result.keys())


@app.route('/fetch_and_post_material')
def fetch_and_post_material():
    result = fetch_material()
    if result:
        user, material = result
        try:
            status = api.PostUpdate(u'@%s はうんこカレーに「%s」を入れた' % (user.GetScreenName(), material))
            return status.GetText()
        except twitter.TwitterError, e:
            return 'duplicated'
    else:
        return 'material not found'

class DummyData(db.Model):
    name = db.StringProperty(required=True)

@app.route('/post_data')
def post_data():
    data = DummyData(name='testtest')
    data.put()
    return 'ok'

@app.route('/get_data')
def get_data():
    result = db.GqlQuery('SELECT * FROM DummyData')
    return repr(result.count())

if __name__ == '__main__':
    app.run()
