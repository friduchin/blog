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

import random
import hmac
import string
import hashlib

secret = 'q3F@k8X?'


def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())


def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val


def make_salt(len=5):
    return ''.join(random.choice(string.letters) for i in xrange(len))


def make_pwd_hash(name, pwd, salt=None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pwd + salt).hexdigest()
    return '%s|%s' % (salt, h)


def valid_pwd(name, pwd, pwd_hash):
    salt = pwd_hash.split('|')[0]
    return pwd_hash == make_pwd_hash(name, pwd, salt)
