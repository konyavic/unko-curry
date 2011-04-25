#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import twitter

import apikey
import config

from google.appengine.ext import db

from application import app

api = twitter.Api(
        consumer_key = apikey.CONSUMER_KEY, 
        consumer_secret = apikey.CONSUMER_SECRET,
        access_token_key = apikey.ACCESS_TOKEN_KEY, 
        access_token_secret = apikey.ACCESS_TOKEN_SECRET,
        cache = None
        )

class CurryUser(db.Model):
    username = db.StringProperty(required=True)

class SendList(db.Model):
    sender = db.ReferenceProperty(CurryUser, collection_name='sender')
    receiver = db.ReferenceProperty(CurryUser, collection_name='receiver')

@app.route('/update_users')
def do_update_users():
    friend_list = api.GetFriends()
    updated = []
    for friend in friend_list:
        username = friend.GetScreenName()
        result = db.GqlQuery('SELECT * FROM CurryUser WHERE username=:1', username)
        if result.count() <= 0:
            updated.append(CurryUser(username=username))

    db.put(updated)
    return "updated curry user"

@app.route('/update_send_list')
def do_update_send_list():
    for user in CurryUser.all():
        update_friends(user)
        update_followers(user)

    return 'updated send list'

def update_friends(user):
    friend_list = api.GetFriends(user=user.username)
    updated = []
    for friend in friend_list:
        sender_name = friend.GetScreenName()
        sender = CurryUser.all().filter("username = ", sender_name)
        if sender.count() <= 0:
            continue

        result = db.GqlQuery('SELECT * FROM SendList WHERE sender=:1 AND receiver=:2', sender[0], user)
        if result.count() <= 0:
            updated.append(SendList(sender=sender[0], receiver=user))

    db.put(updated)
    logging.debug('updated friends of %s' % user.username)
    return

def update_followers(user):
    follower_list = api.GetFollowers(screen_name=user.username)
    updated = []
    for follower in follower_list:
        receiver_name = follower.GetScreenName()
        receiver = CurryUser.all().filter("username = ", receiver_name)
        if receiver.count() <= 0:
            continue

        result = db.GqlQuery('SELECT * FROM SendList WHERE sender=:1 AND receiver=:2', user, receiver[0])
        if result.count() <= 0:
            updated.append(SendList(sender=user, receiver=receiver[0]))

    db.put(updated)
    logging.debug('updated followers of %s' % user.username)
    return
