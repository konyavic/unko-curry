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
    last_receive = db.DateTimeProperty(auto_now_add=True)

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

@app.route('/task/update_users/<cursor>', methods=['GET', 'POST'])
def do_task_update_users(cursor):
    cursor = int(cursor)
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

@app.route('/task/update_links/<username>', methods=['GET', 'POST'])
def do_task_update_links(username):
    user = api.GetUser(user=username)

    if user.GetFriendsCount() < config.LINK_THREASHOLD:
        taskqueue.add(
                url=('/task/update_friends/%s/-1' % username),
                queue_name='update-links-queue'
                )
        logging.info("update links (friends) for user '%s': start" % username)
    else:
        logging.info("refused updating for user '%s'" % username)

    if user.GetFollowersCount() < config.LINK_THREASHOLD:
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
