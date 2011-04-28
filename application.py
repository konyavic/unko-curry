#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import twitter
import simplejson as json

import apikey
import config

from urllib import urlopen, urlencode
from random import shuffle, random, choice

from datetime import datetime

from flask import Flask
from flask import request
from google.appengine.ext import db
from google.appengine.api import taskqueue

app = Flask(__name__)

import user_management
from user_management import CurryUser
from user_management import UserLink

from analyzer import analyze

import effects
from effects import Special

# TODO: should be placed in a proper scope
logging.getLogger().setLevel(logging.DEBUG)

api = twitter.Api(
        consumer_key = apikey.CONSUMER_KEY, 
        consumer_secret = apikey.CONSUMER_SECRET,
        access_token_key = apikey.ACCESS_TOKEN_KEY, 
        access_token_secret = apikey.ACCESS_TOKEN_SECRET,
        cache = None
        )

class History(db.Model):
    # key name = tweet id 
    timestamp = db.DateTimeProperty(auto_now_add=True)

def is_duplicated(tweet):
    if History.get_by_key_name(str(tweet.id)):
        return True
    else:
        return False

@app.route('/cron/fetch_and_post')
def do_fetch_and_post():
    user = (CurryUser.all()
            .order('last_fetch')
            .fetch(limit=1)
            )[0]

    if user.key().name() == config.MY_NAME:
        # skip bot itself
        user.last_fetch = datetime.now()
        user.put()
        return 'ok'

    logging.info("fetching for user '%s'" % user.key().name())

    taskqueue.add(
            queue_name='fetch-queue',
            url='/task/fetch_material/%s/0' % user.key().name(), 
            )

    user.last_fetch = datetime.now()
    user.put()
    return 'ok'

@app.route('/task/fetch_material/<username>/<force_top>', methods=['GET', 'POST'])
def do_task_fetch_material(username, force_top):
    user = CurryUser.get_by_key_name(username)
    force_top = bool(int(force_top))

    if not user:
        logging.error("no such user '%s'" % username)
        return 'bad'

    tweet_list = api.GetUserTimeline(screen_name=username, count=config.FETCH_COUNT)

    tweet = None
    material_list = None
    success = False
    if force_top:
        tweet_list = tweet_list[0:1]
    else:
        shuffle(tweet_list)

    #
    # select material
    #
    for tweet in tweet_list:
        # check history
        if not force_top and is_duplicated(tweet):
            continue

        text = tweet.GetText().encode('utf-8')
        material_list = analyze(
                text,
                count=config.TWEET_MATERIAL_MAX
                )

        if len(material_list) > 0:
            # found material
            success = True
            break

    if success:
        # record to history
        # TODO: trim history chronically
        History(
                key_name=str(tweet.id),
                timestamp=datetime.now()
                ).put()
    else:
        logging.info("material not found for user '%s'" % username)
        return 'bad'

    #
    # select receivers
    #
    link_list = (UserLink
            .all()
            .filter('sender = ', user)
            .order('timestamp')
            .fetch(limit=config.RECEIVER_MAX)
            )

    for link in link_list:
        # randomize material per receiver
        shuffle(material_list)
        count = 1 + int(random() * len(material_list))
        receive_material = material_list[:count]

        taskqueue.add(
                queue_name='post-queue',
                url='/task/post_material/%s/%s' % (username, link.receiver.key().name()), 
                params={'material': receive_material}
                )

        link.timestamp=datetime.now()
        logging.debug("sending from user '%s' to '%s' with material '%s'" % 
                (username, link.receiver.key().name(), repr(receive_material)))
    # update timestamp
    db.put(link_list)

    # send to karei_bot if no receivers
    if len(link_list) == 0:
        shuffle(material_list)
        count = 1 + int(random() * len(material_list))
        receive_material = material_list[:count]

        taskqueue.add(
                queue_name='post-queue',
                url='/task/post_material/%s/%s' % (username, config.MY_NAME), 
                params={'material': receive_material}
                )

        logging.debug("sending from user '%s' to '%s' with material '%s'" % 
                (username, config.MY_NAME, repr(receive_material)))

    return 'ok'

@app.route('/task/post_material/<sender_name>/<receiver_name>', methods=['POST'])
def do_task_post_material(sender_name, receiver_name):
    material_list = request.form.getlist('material')
    material_str_list = []
    for material in material_list:
        material_str_list.append(u'「%s」' % material)

    material_str = u'、'.join(material_str_list)
    logging.debug('constructed material string %s' % material_str)

    #
    # lookup special words
    #
    effect_list = []
    undefined_material_list = []
    for material in material_list:
        s = Special.get_by_key_name(material)
        if s:
            effect_list.append(s)
        else:
            undefined_material_list.append(material)

    effect_string = choice(effect_list).effect_string if effect_list else u"なにも おこらなかった"
    state_string = choice(effect_list).state_string if effect_list else ""

    # generate effects for undefined material
    for material in undefined_material_list:
        # added for the ease of processing but never updated to DB
        # TODO
        effect_list.append(
                Special(
                    key_name=material,
                    spicy=random() * 10,
                    kal=int(random() * 1000),
                    color=[
                        int(random() * 256),
                        int(random() * 256),
                        int(random() * 256)
                        ],
                    price=int(random() * 10000),
                    effect_string="",
                    state_string="",
                    )
                )

    #
    # post the tweet
    #
    try:
        status = api.PostUpdate(
                u'@%s は @%s の カレーに %sを 入れた。 %s' % (
                    sender_name, 
                    receiver_name, 
                    material_str,
                    effect_string
                    )
                )
        logging.debug("posted '%s'" % status.GetText())
    except twitter.TwitterError, e:
        logging.debug('duplicated user %s with material %s', (sender_name, material_list))

    #
    # update the curry
    #
    receiver = CurryUser.get_by_key_name(receiver_name)
    if receiver.curry_count > 0:
        receiver.curry_material += u'、' + material_str
    else:
        receiver.curry_material = material_str

    tmp_color = [0, 0, 0]
    for effect in effect_list:
        receiver.spicy *= effect.spicy
        receiver.kal += effect.kal
        receiver.price += effect.price
        tmp_color[0] += effect.color[0]
        tmp_color[1] += effect.color[1]
        tmp_color[2] += effect.color[2]

    total = receiver.curry_count + len(material_list)
    receiver.color = [
            int(float(receiver.color[0] * receiver.curry_count + tmp_color[0] * len(material_list))/total),
            int(float(receiver.color[1] * receiver.curry_count + tmp_color[1] * len(material_list))/total),
            int(float(receiver.color[2] * receiver.curry_count + tmp_color[2] * len(material_list))/total),
            ]
    receiver.curry_count = total
    if state_string:
        receiver.state_string = state_string

    receiver.put()

    # complete the curry if the material is enough
    if receiver.curry_count >= config.CURRY_MATERIAL_MAX:
        taskqueue.add(
                queue_name='post-queue',
                url='/task/post_curry/%s' % receiver_name, 
                )

    return 'ok'

@app.route('/task/post_curry/<username>', methods=['GET', 'POST'])
def do_task_post_curry(username):
    user = CurryUser.get_by_key_name(username)

    display_string = effects.display_effect(user)

    # post the tweet
    try:
        status = api.PostUpdate(
                u'@%s の カレーが できあがった！ 今日の材料は %s。%s %s' % (
                    username,
                    user.curry_material,
                    display_string,
                    user.state_string
                    )
                )
        user.curry_count = 0
        user.curry_material = ""
        #TODO: move to instance method
        user.spicy = 1.0
        user.price = 0
        user.kal = 0
        user.color = [128, 128, 0]
        user.state_string = ""
        user.put()
        logging.debug("posted '%s'" % status.GetText())
    except twitter.TwitterError, e:
        logging.debug('duplicated user %s with material %s', (username, material_list))
    
    return 'ok'

if __name__ == '__main__':
    app.run()
