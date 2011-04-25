#!/usr/bin/env python
# -*- coding: utf-8 -*-

from google.appengine.ext import db

class History(db.Model):
    username = db.StringProperty(required=True)
    material = db.StringProperty(required=True)
