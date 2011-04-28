#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib

from google.appengine.ext import db

from application import app

import config
import color

from messages import SPECIAL
from messages import BANNED

class Special(db.Model):
    # key name = material str
    spicy = db.FloatProperty(required=True)
    kal = db.IntegerProperty(required=True)
    color = db.ListProperty(int, required=True)
    price = db.IntegerProperty(required=True)
    effect_string = db.StringProperty()
    state_string = db.StringProperty()

class Banned(db.Model):
    # key name = banned words
    pass

@app.route('/init/load_effects')
def do_init_load_effects():
    batch = []

    for s in SPECIAL:
        batch.append(
                Special(
                    key_name=s[0],
                    spicy=s[1],
                    kal=s[2],
                    color=list(s[3])[:3],
                    price=s[4],
                    effect_string=s[5],
                    state_string=s[6]
                    )
                )

    for b in BANNED:
        batch.append(Banned(key_name=b))

    db.put(batch)
    return 'ok'

def generate_effect(material):
    return

def display_effect(curry):
    if curry.spicy > 500:
        spicy = u"修羅"
    elif curry.spicy > 400:
        spicy = u"地獄"
    elif curry.spicy > 300:
        spicy = u"激辛"
    elif curry.spicy > 200:
        spicy = u"大辛"
    elif curry.spicy > 100:
        spicy = u"中辛"
    elif curry.spicy > 10:
        spicy = u"辛口"
    else:
        spicy = u"甘口"

    key = curry.color[0] * 0x10000 + curry.color[1] * 0x100 + curry.color[2]
    color_name = color.get_color(key)

    return u"辛さは %s、色は %s、カロリーは %s kcal、値段は %d 円です。" % (
            spicy, color_name, curry.kal, curry.price)
