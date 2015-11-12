import urllib
import webapp2
import jinja2
import os

from google.appengine.api import users

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + "/templates"))


class MainPage(webapp2.RequestHandler):
    """ Front page for those logged in """

    def get(self):
        user = users.get_current_user()
        if user:  # signed in already
            template_values = {
                'user_mail': users.get_current_user().email(),
                'logout': users.create_logout_url(self.request.host_url),
            }
            template = jinja_environment.get_template('frontuser.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(self.request.host_url)


class WishList(webapp2.RequestHandler):
    """ Display form for getting wishlist items """

    def get(self):
        user = users.get_current_user()
        if user:  # signed in already
            template_values = {
                'user_mail': users.get_current_user().email(),
                'logout': users.create_logout_url(self.request.host_url),
            }
            template = jinja_environment.get_template('wishlist.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(self.request.host_url)


app = webapp2.WSGIApplication([('/giftbook', MainPage),
                               ('/wishlist', WishList)],
                              debug=True)
