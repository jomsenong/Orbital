# This is a more complex version of the Giftbook app. It adds a recommendation list where each recommended item
# is an item that appeared in some user's wish list together with an item in the current user's wish list.
# The recommendation data structure is shared among all users, so needs to be updated more carefully if
# correctness is important. Because we maintain pairs in the data structure, scalability may become more of
# a challenge if there are many users. Compared to the basic version of Giftbook, some basic input validation
# and error handling is done in this version.
# This version is reasonable as a Gemini project with the following additional features over the basic version
# - Does some input validation and error handling
# - Uses transaction for correctness in updating shared data structures
# - Uses some Twitter Bootstrap facilities to make it more responsive to different screen sizes and devices
# - Implements a recommendation list. This is not in the approved list, but is an interesting feature of
#   similar difficulty.

import urllib
import webapp2
import jinja2
import os
import datetime

from google.appengine.ext import ndb
from google.appengine.api import users
from urlparse import urlparse
from random import randint

# Global constants
MAX_REL_ITEMS = 24  # Total number of related item to display
MAX_REL_DISPLAY = 8  # Number of related item to display in one row

jinja_environment = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.dirname(__file__) + "/templates"), autoescape=True)

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


class PairLists(ndb.Model):
    # Stores all item and image urls that co-occurs with the key. The key is an item_url.
    item_image_pairs = ndb.PickleProperty(repeated=True)  # list of item image url pairs


class ItemUrlPair(ndb.Model):
    # Stores item_url pairs, normalized so that first url is smaller.
    url_pair = ndb.PickleProperty(indexed=True)


# Handlers
class MainPage(webapp2.RequestHandler):
    # Handler for the front page.

    def get(self):
        template = jinja_environment.get_template('front.html')
        self.response.out.write(template.render())


# Handler when logged in
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


# Handler for the Wish List page. This one is fairly complex as it shows the user's wish list
# as well as the recommended items that co-occurred in some user's wish list.
# The co-occurrence list poses scalability challenges if there are lots of users.
# The co-occurrence list is also shared among all users, so there are issues of it being updated
# at the same time by many users.
class WishList(webapp2.RequestHandler):
    # Getting and displaying wishlist and recommended items.

    # Update co-occurrence list with a item-image url pair. Should be atomic for correctness
    # but correctness may not be a priority for this application. If scalability suffers,
    # may reconsider whether correctness is necessary. Alternatively, storing the updates
    # and updating in a batch may be better -- instant update of recommendation list is not
    # crucial.
    @ndb.transactional
    def updatePairList(self, key_url, item_url, image_url):
        curr_key = ndb.Key('PairLists', key_url)
        curr_list = curr_key.get()
        if curr_list == None:
            curr_list = PairLists(id=key_url)
        curr_list.item_image_pairs.append([item_url, image_url])
        curr_list.put()

    # Processes curr_list and returns a list for display.
    # Permutes curr_list so that each time a different subset of items is shown.
    # Ensures that there are no repeated items and the items do not appear in
    # item_list, which is meant to be the user's own wish list.
    def permuteUnique(self, curr_list, item_list):

        # Extracts the item urls from item_list into a set
        item_url_set = set()
        for item in item_list:
            item_url_set.add(item.item_link)

        url_set = set()  # for making sure there are no repeated items
        pair_list = []  # construct a list to return

        for i in range(0, len(curr_list)):
            # Permutation part here
            swap_index = randint(i, len(curr_list) - 1)
            temp = curr_list[i]
            curr_list[i] = curr_list[swap_index]
            curr_list[swap_index] = temp

            # This part test for repeated item and check that it is not item_list
            if (curr_list[i][0] not in url_set) and (curr_list[i][0] not in item_url_set):
                url_set.add(curr_list[i][0])
                pair_list.append(curr_list[i])
        return pair_list

    # Displays the page
    def showAll(self, err='', item_url='', image_url='', desc=''):
        # Display the wishlist web page with possible error message err.

        user = users.get_current_user()
        if user:  # signed in already

            # Retrieve person
            parent_key = ndb.Key('Persons', users.get_current_user().email())

            # Retrieve items
            item_query = ndb.gql("SELECT * "
                                 "FROM Items "
                                 "WHERE ANCESTOR IS :1 "
                                 "ORDER BY date DESC",
                                 parent_key)

            # Retrieve co-occurrence list. When this list is long, may want a better method for
            # recommendation than co-occurrence list. How to do that?
            pair_list = []
            for item in item_query:
                pair_query = ndb.Key(PairLists, item.item_link).get()
                if pair_query != None:
                    for curr_pair in pair_query.item_image_pairs:
                        pair_list.append(curr_pair)
            pairs_unique = self.permuteUnique(pair_list, item_query)

            template_values = {
                'error': err,
                'item': item_url,
                'image': image_url,
                'desc': desc,
                'user_mail': users.get_current_user().email(),
                'logout': users.create_logout_url(self.request.host_url),
                'items': item_query,
                'pairlist': pairs_unique[0:MAX_REL_ITEMS],
                'numdisplay': MAX_REL_DISPLAY,
            }

            template = jinja_environment.get_template('wishlist.html')
            self.response.out.write(template.render(template_values))
        else:
            self.redirect(self.request.host_url)

    def get(self):
        self.showAll()

    # Does all the updates for person, items, and co-occurrences. Also does some input validation.
    def post(self):
        # Retrieve person
        parent = ndb.Key('Persons', users.get_current_user().email())
        person = parent.get()
        if person == None:
            person = Persons(id=users.get_current_user().email())
            person.next_item = 1

        item = Items(parent=parent, id=str(person.next_item))
        item.item_id = person.next_item

        # Get the parameters with some simple validation and error handling
        # You can see compare with the basic version by entering non-urls and urls longer than 500 chars in
        # the basic version.
        error = ''
        try:
            item.item_link = self.request.get('item_url')
            # Check that item link scheme is http or https
            if (urlparse(item.item_link).scheme != 'http') and (urlparse(item.item_link).scheme != 'https'):
                error = error + 'Error: Link must be http or https. '
        except Exception, e:
            error = error + 'Error: Problem with item url. ' + str(e) + '. '
        try:
            item.image_link = self.request.get('image_url')
            # Check that image link scheme is http or https
            if (urlparse(item.image_link).scheme != 'http') and (urlparse(item.image_link).scheme != 'https'):
                default_link = self.request.host_url + '/images/gift.jpg'
                error = error + 'Error: Image link must be http or https (use ' + default_link + ' for default image). '
        except Exception, e:
            error = error + 'Error: Problem with image url. ' + str(e) + '. '
        try:
            item.description = self.request.get('desc')
        except Exception, e:
            error = error + 'Error: Problem with item description. ' + str(e) + '. '

        # No error case
        if error == '':
            # Update co-occurrence lists
            # Retrieve items
            parent_key = ndb.Key('Persons', users.get_current_user().email())
            item_query = ndb.gql("SELECT * "
                                 "FROM Items "
                                 "WHERE ANCESTOR IS :1 "
                                 "ORDER BY date DESC",
                                 parent_key)
            for curr_item in item_query:
                # set the first item url to be the smaller one
                ordered_pair = [item.item_link, curr_item.item_link] if (item.item_link > curr_item.item_link) else [
                    curr_item.item_link, item.item_link]

                # Check whether the pair has been encountered before.
                # We make a simplifying assumption that the pair has not been encountered before if the
                # item url pair has not been encountered before. In reality the same item may have multiple
                # urls describing it. Handling this in an unstructured environment where users are allowed
                # to input any url to represent an item is not easy, and not attempted in this app.
                pair_count = ndb.gql("SELECT * FROM ItemUrlPair WHERE url_pair = :1 ", ordered_pair).count()
                # If not encountered before need to insert in the appropriate lists
                if pair_count == 0:
                    new_pair = ItemUrlPair()
                    new_pair.url_pair = ordered_pair
                    new_pair.put()
                    try:
                        self.updatePairList(item.item_link, curr_item.item_link, curr_item.image_link)
                    except:
                        logging.error("updatePairList error %s %s %s" % (
                        item.item_link, curr_item.item_link, curr_item.image_lin))
                    try:
                        self.updatePairList(curr_item.item_link, item.item_link, item.image_link)
                    except:
                        logging.error(
                            "updatePairList error %s %s %s" % (curr_item.item_link, item.item_link, item.image_link))
            # Update item and person
            item.put()
            person.next_item += 1
            person.put()
            self.showAll()
        else:
            # Display with error message
            self.showAll(error, item.item_link, item.image_link, item.description)


app = webapp2.WSGIApplication([('/', MainPage),
                               ('/giftbook', MainPageUser),
                               ('/wishlist', WishList),
                               ('/deleteitem', DeleteItem),
                               ('/search', Search),
                               ('/display', Display)],
                              debug=True)
