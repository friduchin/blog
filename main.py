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
import random
import string
import hashlib

from google.appengine.ext import db

template_dir = os.path.join(os.path.dirname(__file__), 'templates')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir),
								autoescape = True)

def make_salt():
	return ''.join(random.choice(string.letters) for i in range(5))

def make_pwd_hash(name, pwd, salt = None):
	if not salt:
		salt = make_salt()
	h = hashlib.sha256(name + pwd + salt).hexdigest()
	return (h, salt)

def valid_cookie(cookie):
		(id, hash) = cookie.split("|")
		user = User.get_by_id(long(id))
		if user:
			return hash == User.get_by_id(long(id)).pwd_hash

def valid_pwd(name, pwd):
	users = db.GqlQuery("SELECT * FROM User WHERE name = '%s'" % name)
	if users:
		salt = users[0].salt
		if make_pwd_hash(name, pwd, salt)[0] == users[0].pwd_hash:
			return users[0].key().id()

class Post(db.Model):
	subject = db.StringProperty(required = True)
	content = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)

class User(db.Model):
	name = db.StringProperty(required = True)
	pwd_hash = db.StringProperty(required = True)
	salt = db.StringProperty(required = True)

class Handler(webapp2.RequestHandler):
	def write(self, *a, **kw):
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params):
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw):
		self.write(self.render_str(template, **kw))

class MainPage(Handler):
	def get(self):
		posts = db.GqlQuery("SELECT * FROM Post ORDER BY created DESC")
		self.render("main.html", posts=posts)

class SignUp(Handler):
	def render_signup(self, username="", email="", error="", v_error=""):
		self.render("signup.html", username=username, email=email, error=error, v_error=v_error)

	def get(self):
		self.render_signup()

	def post(self):
		username = self.request.get("username")
		password = self.request.get("password")
		verify = self.request.get("verify")
		email = self.request.get("email")

		if username and password and verify:
			if password == verify:
				pwd = make_pwd_hash(username, password)
				u = User(name = username, pwd_hash = pwd[0], salt = pwd[1])
				u.put()
				user_id = u.key().id()
				cookie = '%s|%s' % (user_id, pwd[0])
				self.response.headers.add_header("Set-Cookie", "user_id=%s; Path=/" % cookie)
				self.redirect("/welcome")
			else:
				v_error = "Passwords didn't match"
				self.render_signup(username, email, "", v_error)
		else:
			error = "Please, enter username, password and verify password"
			self.render_signup(username, email, error)

class LogIn(Handler):
	def render_login(self, username="", error=""):
		self.render("login.html", username=username, error=error)

	def get(self):
		self.render_login()

	def post(self):
		username = self.request.get("username")
		password = self.request.get("password")
		if username and password:
			id = valid_pwd(username, password)
			if id:
				cookie = '%s|%s' % (str(id), str(User.get_by_id(id).pwd_hash))
				self.response.headers.add_header("Set-Cookie", "user_id=%s; Path=/" % cookie)
				self.redirect("/welcome")
			else:
				self.render_login(username, "Invaid login")
		else:
			self.render_login(username, "Please, enter both username and password")

class Welcome(Handler):

	def get(self):
		cookie = self.request.cookies.get("user_id")
		if valid_cookie(cookie):
			id = cookie.split("|")[0]
			username = User.get_by_id(long(id)).name
			self.write("Hello, %s!" % username)
		else:
			self.redirect("/signup")

class NewPost(Handler):
	def render_new(self, subject="", content="", error=""):
		self.render("newpost.html", subject=subject, content=content, error=error)

	def get(self):
		self.render_new()

	def post(self):
		subject = self.request.get("subject")
		content = self.request.get("content")

		if subject and content:
			p = Post(subject = subject, content = content)
			p.put()
			path = "/" + str(p.key().id())

			self.redirect(path)
		else:
			error = "Please, enter both a subject and some content!"
			self.render_new(subject, content, error)

class AddedPost(Handler):
	def get(self, id):
		post = Post.get_by_id(long(id))
		self.render("post.html", post=post)

app = webapp2.WSGIApplication([
	('/', MainPage),
	('/newpost', NewPost),
	(r'/(\d+)', AddedPost),
	('/signup', SignUp),
	('/login', LogIn),
	('/welcome', Welcome)
	],
	debug=True)
