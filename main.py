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

import os
import random
import hmac
import string
import hashlib

import jinja2
import webapp2

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
                                autoescape = True)

secret = 'q3F@k8X?'

def make_secure_val(val):
    return '%s|%s' % (val, hmac.new(secret, val).hexdigest())

def check_secure_val(secure_val):
    val = secure_val.split('|')[0]
    if secure_val == make_secure_val(val):
        return val

def make_salt(len = 5):
    return ''.join(random.choice(string.letters) for i in xrange(len))

def make_pwd_hash(name, pwd, salt = None):
    if not salt:
        salt = make_salt()
    h = hashlib.sha256(name + pwd + salt).hexdigest()
    return '%s|%s' % (salt, h)

def valid_cookie(cookie):
    (id, hash) = cookie.split('|')
    user = User.get_by_id(long(id))
    if user:
        return hash == User.get_by_id(long(id)).pwd_hash

def valid_pwd(name, pwd, pwd_hash):
    salt = pwd_hash.split('|')[0]
    return pwd_hash == make_pwd_hash(name, pwd, salt)

class Post(db.Model):
    subject = db.StringProperty(required = True)
    content = db.TextProperty(required = True)
    creator = db.IntegerProperty(required = True)
    created = db.DateTimeProperty(auto_now_add = True)

class User(db.Model):
    name = db.StringProperty(required = True)
    pwd_hash = db.StringProperty(required = True)
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

class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, **kw))

    def set_secure_cookie(self, name, val):
        cookie_val = make_secure_val(val)
        self.response.headers.add_header(
            'Set-Cookie',
            '%s=%s; Path=/' % (name, cookie_val))

    def read_secure_cookie(self, name):
        cookie_val = self.request.cookies.get(name)
        return cookie_val and check_secure_val(cookie_val)

    def login(self, user):
        self.set_secure_cookie('user_id', str(user.key().id()))

    def logout(self):
        self.response.headers.add_header('Set-Cookie', 'user_id=; Path=/')

    def initialize(self, *a, **kw):
        webapp2.RequestHandler.initialize(self, *a, **kw)
        uid = self.read_secure_cookie('user_id')
        self.user = uid and User.by_id(int(uid))

class MainPage(Handler):
    def get(self):
        posts = db.GqlQuery('SELECT * FROM Post ORDER BY created DESC')
        self.render('main.html', posts=posts)

class SignUp(Handler):
    def render_signup(self, username='', email='', error=''):
         self.render(
            'signup.html',
            username = username,
            email = email,
            error = error)

    def get(self):
        self.render_signup()

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        if username and password and verify:
            #make sure the user doesn't already exist
            u = User.by_name(username)
            if u:
                self.render_signup(error = ('That user already exists. Please,'
                    ' choose another username'))
            elif password == verify:
                pwd_hash = make_pwd_hash(username, password)
                u = User(name = username, pwd_hash = pwd_hash, email = email)
                u.put()
                self.login(u)
                self.redirect('/welcome')
            else:
                self.render_signup(username, email, "Passwords didn't match")
        else:
            self.render_signup(
                username,
                email,
                'Please, enter username, password and verify password')

class LogIn(Handler):
    def render_login(self, username='', error=''):
        self.render('login.html', username=username, error=error)

    def get(self):
        self.render_login()

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')

        if username and password:
            u = User.valid_login(username, password)
            if u:
                self.login(u)
                self.redirect('/welcome')
            else:
                self.render_login(username, 'Invaid login')
        else:
            self.render_login(
                username,
                'Please, enter both username and password')

class LogOut(Handler):
    def get(self):
        self.logout()
        self.redirect('/signup')

class Welcome(Handler):
    def get(self):
        if self.user:
            self.write('Hello, %s!' % self.user.name)
        else:
            self.redirect('/signup')

class NewPost(Handler):
    def render_new(self, subject='', content='', error=''):
        self.render('new-post.html', subject=subject, content=content, error=error)

    def get(self):
        if self.user:
            self.render_new()
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = self.request.get('content')
        creator = self.user.key().id()

        if subject and content:
            p = Post(subject = subject, content = content, creator = creator)
            p.put()
            path = '/' + str(p.key().id())

            self.redirect(path)
        else:
            error = 'Please, enter both a subject and some content!'
            self.render_new(subject, content, error)

class PostPage(Handler):
    def get(self, id):
        post = Post.get_by_id(int(id))
        if not post:
            self.error(404)
            return
        self.render('post.html', post=post)

class DeletePost(Handler):
    def get(self, id):
        post = Post.get_by_id(int(id))
        if not self.user:
            self.redirect("/login")
        elif not self.user.key().id() == post.creator:
            self.write('You are not allowed to delete this post')
        else:
            self.render('delete-post.html', post_id=id)

    def post(self, id):
        post = Post.get_by_id(int(id))
        post.delete()

class EditPost(Handler):
    def get(self, id):
        post = Post.get_by_id(int(id))
        if not self.user:
            self.redirect("/login")
        elif not self.user.key().id() == post.creator:
            self.write('You are not allowed to edit this post')
        else:
            subject = post.subject
            content = post.content
            self.render(
                'edit-post.html',
                subject=subject,
                content=content,
                post_id=id)

    def post(self, id):
        if not self.user:
            self.redirect('/blog')

        subject = self.request.get('subject')
        content = self.request.get('content')

        if subject and content:
            p = Post.get_by_id(int(id))
            p.subject = subject
            p.content = content
            p.put()
            self.redirect('/%s' % id)
        else:
            error = 'Please, enter both a subject and some content!'
            self.render(
                'edit-post.html',
                subject=subject,
                content=content,
                error=error,
                id=id)

app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/newpost', NewPost),
    ('/([0-9]+)', PostPage),
    ('/signup', SignUp),
    ('/login', LogIn),
    ('/logout', LogOut),
    ('/welcome', Welcome),
    ('/([0-9]+)/delete', DeletePost),
    ('/([0-9]+)/edit', EditPost)
    ],
    debug=True)
