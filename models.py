# Copyright 2016 Google Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

from google.appengine.ext import db
from secure import *


class Post(db.Model):
    subject = db.StringProperty(required=True)
    content = db.TextProperty(required=True)
    creator = db.IntegerProperty(required=True)
    created = db.DateTimeProperty(auto_now_add=True)


class User(db.Model):
    name = db.StringProperty(required=True)
    pwd_hash = db.StringProperty(required=True)
    email = db.StringProperty()

    @classmethod
    def by_id(cls, uid):
        return cls.get_by_id(uid)

    @classmethod
    def by_name(cls, name):
        u = cls.all().filter('name =', name).get()
        return u

    @classmethod
    def valid_login(cls, name, pw):
        u = cls.by_name(name)
        if u and valid_pwd(name, pw, u.pwd_hash):
            return u


class Likes(db.Model):
    user = db.IntegerProperty(required=True)


class Comment(db.Model):
    author = db.ReferenceProperty(User, required=True)
    content = db.TextProperty(required=True)
