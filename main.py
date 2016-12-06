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

import jinja2
import webapp2

from google.appengine.ext import db
from models import User, Post, Comment, Likes
from secure import *

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader=jinja2.FileSystemLoader(template_dir),
                               autoescape=True)


class Handler(webapp2.RequestHandler):
    def write(self, *a, **kw):
        self.response.out.write(*a, **kw)

    def render_str(self, template, **params):
        t = jinja_env.get_template(template)
        return t.render(params)

    def render(self, template, **kw):
        self.write(self.render_str(template, logged_in=self.user, **kw))

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
            username=username,
            email=email,
            error=error)

    def get(self):
        self.render_signup()

    def post(self):
        username = self.request.get('username')
        password = self.request.get('password')
        verify = self.request.get('verify')
        email = self.request.get('email')

        if username and password and verify:
            # make sure the user doesn't already exist
            u = User.by_name(username)
            if u:
                self.render_signup(error=('That user already exists. Please,'
                                          ' choose another username'))
            elif password == verify:
                pwd_hash = make_pwd_hash(username, password)
                u = User(name=username, pwd_hash=pwd_hash, email=email)
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
            self.render('welcome.html', user=self.user)
        else:
            self.redirect('/signup')


class NewPost(Handler):
    def render_new(self, subject='', content='', error=''):
        self.render(
            'new-post.html',
            subject=subject,
            content=content,
            error=error)

    def get(self):
        if self.user:
            self.render_new()
        else:
            self.redirect("/login")

    def post(self):
        if not self.user:
            return self.redirect('/login')

        subject = self.request.get('subject')
        content = self.request.get('content')
        creator = self.user.key().id()

        if subject and content:
            p = Post(subject=subject, content=content, creator=creator)
            p.put()
            path = '/' + str(p.key().id())

            self.redirect(path)
        else:
            error = 'Please, enter both a subject and some content!'
            self.render_new(subject, content, error)


class PostPage(Handler):
    def get(self, id):
        post = Post.get_by_id(int(id))
        comments = Comment.all().ancestor(post)
        if not post:
            self.error(404)
            return
        if self.user:
            user_id = self.user.key().id()
            if Likes.all().ancestor(post).filter('user =', user_id).get():
                vote = 'unlike'
            else:
                vote = 'like'
            self.render('post.html', post=post, vote=vote, comments=comments)
        else:
            self.render('post.html', post=post, comments=comments)

    def post(self, id):
        if not self.user:
            return self.redirect('/login')

        post = Post.get_by_id(int(id))
        user_id = self.user.key().id()
        if user_id == post.creator:
            self.write('You are not allowed to like your own post')
        else:
            l = Likes.all().ancestor(post).filter('user =', user_id).get()
            if l:
                l.delete()
            else:
                like = Likes(parent=post, user=user_id)
                like.put()
            self.redirect('/%s' % id)


class DeletePost(Handler):
    def get(self, id):
        post = Post.get_by_id(int(id))
        if not self.user:
            self.redirect("/login")
        elif not self.user.key().id() == post.creator:
            self.write('You are not allowed to delete this post')
        else:
            message = 'Are you sure you want to delete this post?'
            self.render(
                'delete.html',
                post_id=id,
                message=message,
                content=post.content)

    def post(self, id):
        post = Post.get_by_id(int(id))
        if (not self.user) or (not self.user.key().id() == post.creator):
            return self.redirect('/login')

        post.delete()
        self.write('Post deleted. <a href="/">To main page</a>')


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
                'new-post.html',
                subject=subject,
                content=content,
                post_id=id,
                edit=True)

    def post(self, id):
        post = Post.get_by_id(int(id))
        if (not self.user) or (not self.user.key().id() == post.creator):
            return self.redirect('/login')

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
                'new-post.html',
                subject=subject,
                content=content,
                error=error,
                id=id,
                edit=True)


class AddComment(Handler):
    def get(self, post_id):
        if not self.user:
            self.redirect("/login")
        else:
            self.render('comment.html')

    def post(self, post_id):
        if not self.user:
            return self.redirect('/login')

        content = self.request.get('content')

        if content:
            comment = Comment(
                parent=Post.get_by_id(int(post_id)),
                content=content,
                author=self.user)
            comment.put()
            self.redirect('/%s' % post_id)
        else:
            error = 'Please, enter some content!'
            self.render(
                'comment.html',
                content=content,
                error=error)


class EditComment(AddComment):
    def get(self, post_id, id):
        comment = Comment.get_by_id(int(id), Post.get_by_id(int(post_id)))
        if not self.user:
            self.redirect("/login")
        elif not self.user.key() == comment.author.key():
            self.write('You are not allowed to edit this comment')
        else:
            content = comment.content
            self.render(
                'comment.html',
                content=content,
                edit=True,
                post_id=post_id)

    def post(self, post_id, id):
        comment = Comment.get_by_id(int(id), Post.get_by_id(int(post_id)))
        if (not self.user) or (not self.user.key() == comment.author.key()):
            return self.redirect('/login')

        content = self.request.get('content')

        if content:
            c = Comment.get_by_id(int(id), Post.get_by_id(int(post_id)))
            c.content = content
            c.put()
            self.redirect('/%s' % post_id)
        else:
            error = 'Please, enter some content!'
            self.render(
                'comment.html',
                content=content,
                error=error,
                edit=True,
                post_id=post_id)


class DeleteComment(Handler):
    def get(self, post_id, id):
        comment = Comment.get_by_id(int(id), Post.get_by_id(int(post_id)))
        if not self.user:
            self.redirect("/login")
        elif not self.user.key() == comment.author.key():
            self.write('You are not allowed to delete this comment')
        else:
            message = 'Are you sure you want to delete this comment?'
            self.render(
                'delete.html',
                post_id=post_id,
                message=message,
                content=comment.content)

    def post(self, post_id, id):
        comment = Comment.get_by_id(int(id), Post.get_by_id(int(post_id)))
        if (not self.user) or (not self.user.key() == comment.author.key()):
            return self.redirect('/')

        comment.delete()
        self.redirect('/%s' % post_id)


app = webapp2.WSGIApplication([
    ('/', MainPage),
    ('/newpost', NewPost),
    ('/([0-9]+)', PostPage),
    ('/signup', SignUp),
    ('/login', LogIn),
    ('/logout', LogOut),
    ('/welcome', Welcome),
    ('/([0-9]+)/delete', DeletePost),
    ('/([0-9]+)/edit', EditPost),
    ('/([0-9]+)/comment', AddComment),
    ('/([0-9]+)/comment/([0-9]+)/edit', EditComment),
    ('/([0-9]+)/comment/([0-9]+)/delete', DeleteComment)
    ],
    debug=True)
