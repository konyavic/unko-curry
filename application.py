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
from flask import request
from google.appengine.ext import db
from google.appengine.api import taskqueue

from history import History

app = Flask(__name__)

import user_management
from user_management import CurryUser
from user_management import UserLink

# TODO: should be placed in a proper scope
logging.getLogger().setLevel(logging.DEBUG)

api = twitter.Api(
        consumer_key = apikey.CONSUMER_KEY, 
        consumer_secret = apikey.CONSUMER_SECRET,
        access_token_key = apikey.ACCESS_TOKEN_KEY, 
        access_token_secret = apikey.ACCESS_TOKEN_SECRET,
        cache = None
        )

#def fetch_material():
def _fetch_material():
    for retry in range(1, 1 + config.FETCH_RETRY_MAX):
        logging.debug('fetching tweets with count=%d, page=%d ...' % (config.FETCH_COUNT, retry))
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
        logging.debug('choosed %s' % key)
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

@app.route('/task/fetch_material/<username>', methods=['GET', 'POST'])
def do_task_fetch_material(username):
    user = CurryUser.get_by_key_name(username)
    if not user:
        logging.error("no such user '%s'" % username)
        return 'bad'

    tweet_list = api.GetUserTimeline(screen_name=username, count=config.FETCH_COUNT)
    while len(tweet_list) > 0:
        tweet = choice(tweet_list)
        material_list = analyze(tweet.GetText())
        if len(material_list) <= 0:
            continue

        break

        #TODO: check duplicity

    link_list = (UserLink
            .all()
            .filter('sender = ', user)
            .fetch(limit=config.RECEIVER_MAX)
            )

    for link in link_list:
        taskqueue.add(
                queue_name='post-queue',
                url='/task/post_material/%s/%s' % (username, link.receiver.key().name()), 
                params={'material': material_list}
                )
        logging.debug("send from user '%s' to '%s' with material '%s'" % 
                (username, link.receiver.key().name(), repr(material_list)))

    #TODO: send to karei_bot if no receivers

    return 'ok'

@app.route('/task/post_material/<sender_name>/<receiver_name>', methods=['POST'])
def do_task_post_material(sender_name, receiver_name):
    material_list = request.form.getlist('material')
    material_str_list = []
    for material in material_list:
        material_str_list.append(u'「%s」' % material)

    material_str = u'、'.join(material_str_list)
    logging.debug('constructed material string %s' % material_str)

    try:
        status = api.PostUpdate(u'@%s は @%s のカレーに%sを入れた' % (sender_name, receiver_name, material_str))
        logging.debug("posted '%s'" % status.GetText())
    except twitter.TwitterError, e:
        logging.debug('duplicated user %s with material %s', (username, material_list))

    return 'ok'

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

        receiver_list = get_receiver_list(username)
        update_history = []
        for receiver in receiver_list:
            try:
                status = api.PostUpdate(u'@%s は @%s のカレーに%sを入れた' % (username, receiver.username, material_str))
                logging.debug('posted %s' % status.GetText())
            except twitter.TwitterError, e:
                logging.debug('duplicated user %s with material %s', (username, repr(material_list)))
            finally:
                update_history.append(History(username=username, material=material))

        db.put(update_history)
        return 'posted'

    else:
        logging.debug('material not found')
        return 'material not found'

def get_receiver_list(username):
    user = CurryUser.all().filter('username = ', username)
    if user.count() <= 0:
        logging.error('no such user %s' % username)
        return []

    result = db.GqlQuery('SELECT * FROM SendList WHERE sender=:1', user[0])
    receiver_list = [r.receiver for r in result]
    logging.debug('receivers of %s: %s' % (username, receiver_list))
    return receiver_list

if __name__ == '__main__':
    app.run()
