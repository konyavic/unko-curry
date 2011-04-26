#!/usr/bin/env python
# -*- coding: utf-8 -*-

import logging

import twitter

import apikey
import config

from google.appengine.ext import db
from google.appengine.api import taskqueue

from application import app

api = twitter.Api(
        consumer_key = apikey.CONSUMER_KEY, 
        consumer_secret = apikey.CONSUMER_SECRET,
        access_token_key = apikey.ACCESS_TOKEN_KEY, 
        access_token_secret = apikey.ACCESS_TOKEN_SECRET,
        cache = None
        )

class CurryUser(db.Model):
    last_update = db.DateTimeProperty(auto_now_add=True)
    last_fetch = db.DateTimeProperty(auto_now_add=True)

class UserLink(db.Model):
    sender = db.ReferenceProperty(CurryUser, collection_name='sender')
    receiver = db.ReferenceProperty(CurryUser, collection_name='receiver')

@app.route('/update_users')
def do_update_users():
    taskqueue.add(
            url=('/task/update_users/-1'),
            queue_name='update-users-queue'
            )
    logging.info('update users: start')
    return 'ok'

@app.route('/task/update_users/<int:cursor>', methods=['GET', 'POST'])
def do_task_update_users(cursor):
    friend_list, data = api._GetFriends(cursor=cursor)
    batch = []
    for friend in friend_list:
        username = friend.GetScreenName()
        if not CurryUser.get_by_key_name(username):
            batch.append(CurryUser(key_name=username))
            # TODO: should also dispatch a task to update the send list

    db.put(batch)
    logging.debug('added %d users from %d friends of bot' % (len(batch), len(friend_list)))
    logging.debug('next cursor=%d' % data['next_cursor'])

    if int(data['next_cursor']) != 0:
        taskqueue.add(
                url=('/task/update_users/%d' % int(data['next_cursor'])),
                queue_name='update-users-queue'
                )
    else:
        logging.info('update users: done')

    return 'ok'

@app.route('/update_links/<username>')
def do_update_links_with_username(username):
    user = CurryUser.get_by_key_name(username)
    if not user:
        logging.error("no such user '%s'" % username)
        return 'bad'

    cursor = -1
    while cursor != 0:
        cursor = update_friends(user, cursor)

    return 'ok'

@app.route('/task/update_friends/<user>/<int:cursor>', methods=['GET', 'POST'])
def do_task_update_friends(user, cursor):
    username = user.key().name()
    friend_list, data = api._GetFriends(user=username, cursor=cursor)
    batch = []
    for friend in friend_list:
        sender_name = friend.GetScreenName()
        sender = CurryUser.get_by_key_name(sender_name)
        if not sender:
            continue

        link = (UserLink
                .all()
                .filter('sender = ', sender_name)
                .filter('receiver = ', username)
                .fetch(limit=1)
                )
        if not link:
            batch.append(UserLink(sender=sender, receiver=user))

    db.put(batch)
    logging.debug('updated %d friends from %d friends of %s' % (len(batch), len(friend_list), username))
    logging.debug('next cursor=%d' % data['next_cursor'])
    return data['next_cursor']

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
