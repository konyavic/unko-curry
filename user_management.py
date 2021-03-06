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
    last_fetch = db.DateTimeProperty(auto_now_add=True)
    curry_count = db.IntegerProperty(default=0)
    curry_material = db.StringProperty(default="")
    spicy = db.FloatProperty(default=1.0)
    kal = db.IntegerProperty(default=0)
    color = db.ListProperty(int, default=[128, 128, 0])
    price = db.IntegerProperty(default=0)
    state_string = db.StringProperty(default="")

class UserLink(db.Model):
    sender = db.ReferenceProperty(CurryUser, collection_name='sender')
    receiver = db.ReferenceProperty(CurryUser, collection_name='receiver')
    timestamp = db.DateTimeProperty()

@app.route('/cron/update_users/<force>')
def do_cron_update_users(force):
    # update bot
    bot = CurryUser.get_by_key_name(config.MY_NAME)
    if not bot:
        CurryUser(key_name=config.MY_NAME).put()

    taskqueue.add(
            url=('/task/update_friends/%s/-1' % config.MY_NAME),
            queue_name='update-links-queue'
            )

    # update friends
    taskqueue.add(
            url=('/task/update_users/%s/-1' % force),
            queue_name='update-users-queue'
            )
    logging.info('update users: start')
    return 'ok'

@app.route('/task/update_users/<force>/<cursor>', methods=['GET', 'POST'])
def do_task_update_users(force, cursor):
    force = bool(int(force))
    cursor = int(cursor)
    friend_list, data = api._GetFriends(cursor=cursor)
    batch = []
    for friend in friend_list:
        username = friend.GetScreenName()
        isnew = not CurryUser.get_by_key_name(username)
        if force or isnew:
            batch.append(CurryUser(key_name=username))
            taskqueue.add(
                url=('/task/update_links/%s/%d' % (username, (isnew and not force))),
                queue_name='update-links-queue'
                )

    db.put(batch)
    logging.debug('added %d users from %d friends of bot' % (len(batch), len(friend_list)))
    logging.debug('next cursor=%d' % data['next_cursor'])

    if int(data['next_cursor']) != 0:
        taskqueue.add(
                url=('/task/update_users/%d/%d' % (force, int(data['next_cursor']))),
                queue_name='update-users-queue'
                )
    else:
        logging.info('update users: done')

    return 'ok'

@app.route('/task/update_links/<username>/<isnew>', methods=['GET', 'POST'])
def do_task_update_links(username, isnew):
    user = api.GetUser(user=username)
    isnew = bool(int(isnew))

    if user.GetFriendsCount() < config.LINK_THREASHOLD:
        taskqueue.add(
                url=('/task/update_friends/%s/-1' % username),
                queue_name='update-links-queue'
                )
        logging.info("update links (friends) for user '%s': start" % username)
    else:
        logging.info("refused updating for user '%s'" % username)

    if isnew and user.GetFollowersCount() < config.LINK_THREASHOLD:
        taskqueue.add(
                url=('/task/update_followers/%s/-1' % username),
                queue_name='update-links-queue'
                )
        logging.info("update links (followers) for user '%s': start" % username)
    else:
        logging.info("refused updating for user '%s'" % username)

    return 'ok'

@app.route('/task/update_friends/<username>/<cursor>', methods=['GET', 'POST'])
def do_task_update_friends(username, cursor):
    cursor = int(cursor)
    user = CurryUser.get_by_key_name(username)
    if not user:
        logging.error("no such user '%s'" % username)
        return 'bad'

    friend_list, data = api._GetFriends(user=username, cursor=cursor)
    batch = []
    for friend in friend_list:
        sender_name = friend.GetScreenName()
        sender = CurryUser.get_by_key_name(sender_name)
        if not sender:
            continue

        link = (UserLink
                .all()
                .filter('sender = ', sender)
                .filter('receiver = ', user)
                .fetch(limit=1)
                )

        if not link:
            batch.append(UserLink(sender=sender, receiver=user))

    db.put(batch)
    logging.debug('updated %d friends from %d friends of %s' % (len(batch), len(friend_list), username))
    logging.debug('next cursor=%d' % data['next_cursor'])

    if int(data['next_cursor']) != 0:
        taskqueue.add(
                url=('/task/update_friends/%s/%d' % (username, int(data['next_cursor']))),
                queue_name='update-links-queue'
                )
    else:
        logging.info("update links (friends) for user '%s': done" % username)

    return 'ok'

@app.route('/task/update_followers/<username>/<cursor>', methods=['GET', 'POST'])
def do_task_update_followers(username, cursor):
    cursor = int(cursor)
    user = CurryUser.get_by_key_name(username)
    if not user:
        logging.error("no such user '%s'" % username)
        return 'bad'

    follower_list, data = api._GetFollowers(screen_name=username, cursor=cursor)
    batch = []
    for follower in follower_list:
        receiver_name = follower.GetScreenName()
        receiver = CurryUser.get_by_key_name(receiver_name)
        if not receiver:
            continue

        link = (UserLink
                .all()
                .filter('sender = ', user)
                .filter('receiver = ', receiver)
                .fetch(limit=1)
                )

        if not link:
            batch.append(UserLink(sender=user, receiver=receiver))

    db.put(batch)
    logging.debug('updated %d followers from %d followers of %s' % (len(batch), len(follower_list), username))
    logging.debug('next cursor=%d' % data['next_cursor'])

    if int(data['next_cursor']) != 0:
        taskqueue.add(
                url=('/task/update_followers/%s/%d' % (username, int(data['next_cursor']))),
                queue_name='update-links-queue'
                )
    else:
        logging.info("update links (followers) for user '%s': done" % username)

    return 'ok'
