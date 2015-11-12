import urllib
import webapp2
import jinja2
import os
import datetime

from google.appengine.ext import ndb
from google.appengine.api import users

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + "/templates"))

# This part for the front page
class MainPage(webapp2.RequestHandler):
    # Handler for the front page.

    def get(self):
        template = jinja_environment.get_template('front.html')
        self.response.out.write(template.render())


class MainPageUser(webapp2.RequestHandler):
    # Front page for those logged in

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


# Datastore definitions
class Persons(ndb.Model):
    # Models a person. Key is the email.
    next_item = ndb.IntegerProperty()  # item_id for the next item


class Items(ndb.Model):
    # Models an item with item_link, image_link, description, and date. Key is item_id.
    item_id = ndb.IntegerProperty()
    item_link = ndb.StringProperty()
    image_link = ndb.StringProperty()
    description = ndb.TextProperty()
    date = ndb.DateTimeProperty(auto_now_add=True)


class WishList(webapp2.RequestHandler):
    """ Form for getting and displaying wishlist items. """

    def show(self):
        # Displays the page. Used by both get and post
        user = users.get_current_user()
        if user:  # signed in already

            # Retrieve person
            parent_key = ndb.Key('Persons', users.get_current_user().email())

            # Retrieve items
            query = ndb.gql("SELECT * "
                            "FROM Items "
                            "WHERE ANCESTOR IS :1 "
                            "ORDER BY date DESC",
                            parent_key)

            template_values = {
                'user_mail': users.get_current_user().email(),
                'logout': users.create_logout_url(self.request.host_url),
                'items': query,
            }

            template = jinja_environment.get_template('wishlist.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(self.request.host_url)

    def get(self):
        self.show()

    def post(self):
        # Retrieve person
        parent = ndb.Key('Persons', users.get_current_user().email())
        person = parent.get()
        if person == None:
            person = Persons(id=users.get_current_user().email())
            person.next_item = 1

        item = Items(parent=parent, id=str(person.next_item))
        item.item_id = person.next_item

        item.item_link = self.request.get('item_url')
        item.image_link = self.request.get('image_url')
        item.description = self.request.get('desc')

        # Only store an item if there is an image
        if item.image_link.rstrip() != '':
            person.next_item += 1
            person.put()
            item.put()
        self.show()

# For deleting an item from wish list
class DeleteItem(webapp2.RequestHandler):
    # Delete item specified by user

    def post(self):
        item = ndb.Key('Persons', users.get_current_user().email(), 'Items', self.request.get('itemid'))
        item.delete()
        self.redirect('/wishlist')


# Handler for the Search page
class Search(webapp2.RequestHandler):
    # Display search page

    def get(self):
        user = users.get_current_user()
        if user:  # signed in already
            template_values = {
                'user_mail': users.get_current_user().email(),
                'logout': users.create_logout_url(self.request.host_url),
            }
            template = jinja_environment.get_template('search.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(self.request.host_url)


# Handler for returning search result
class Display(webapp2.RequestHandler):
    # Displays search result

    def post(self):
        target = self.request.get('email').rstrip()
        # Retrieve person
        parent_key = ndb.Key('Persons', target)

        query = ndb.gql("SELECT * "
                        "FROM Items "
                        "WHERE ANCESTOR IS :1 "
                        "ORDER BY date DESC",
                        parent_key)

        template_values = {
            'user_mail': users.get_current_user().email(),
            'target_mail': target,
            'logout': users.create_logout_url(self.request.host_url),
            'items': query,
        }
        template = jinja_environment.get_template('display.html')
        self.response.out.write(template.render(template_values))


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/giftbook', MainPageUser),
                               ('/wishlist', WishList),
                               ('/deleteitem', DeleteItem),
                               ('/search', Search),
                               ('/display', Display)],
                              debug=True)

