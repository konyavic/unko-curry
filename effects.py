#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib

from google.appengine.ext import db

from application import app

import config
from messages import EFFECTS
from messages import SPECIAL
from messages import BANNED

class Effect(db.Model):
    effect_string = db.StringProperty(required=True)

class Special(db.Model):
    # key name = material str
    effect_string = db.StringProperty()

class Banned(db.Model):
    # key name = banned words
    pass

@app.route('/init/load_effects')
def do_init_load_effects():
    batch = []
    for e in EFFECTS:
        batch.append(
                Effect(
                    effect_string=e
                    )
                )

    for s in SPECIAL:
        batch.append(
                Special(
                    key_name=s[0],
                    effect_string=s[1]
                    )
                )

    for b in BANNED:
        batch.append(
                Banned(
                    key_name=b,
                    )
                )

    db.put(batch)
    return 'ok'
