#!/usr/bin/env python
# -*- coding: utf-8 -*-

import urllib

from google.appengine.ext import db

from application import app

import config
from messages import EFFECTS

class Effect(db.Model):
    # key name = hash(str)
    effect_string = db.StringProperty(required=True)

@app.route('/init/load_effects')
def do_init_load_effects():
    batch = []
    for e in EFFECTS:
        batch.append(
                Effect(
                    key_name=str(hash(e)),
                    effect_string=e
                    )
                )

    db.put(batch)
    return 'ok'
