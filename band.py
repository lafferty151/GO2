#
# band class for Gig-o-Matic 2 
#
# Aaron Oppenheimer
# 24 August 2013
#

from google.appengine.ext import ndb
from requestmodel import *
import webapp2_extras.appengine.auth.models

import webapp2
from jinja2env import jinja_environment as je
from debug import *

import member
import goemail
import assoc

def band_key(band_name='band_key'):
    """Constructs a Datastore key for a Guestbook entity with guestbook_name."""
    return ndb.Key('Band', band_name)

#
# class for band
#
class Band(ndb.Model):
    """ Models a gig-o-matic band """
    name = ndb.StringProperty()
    lower_name = ndb.ComputedProperty(lambda self: self.name.lower())
    website = ndb.TextProperty()
    description = ndb.TextProperty()
    sections = ndb.KeyProperty( repeated=True ) # instrumental sections
    created = ndb.DateTimeProperty(auto_now_add=True)
    time_zone_correction = ndb.IntegerProperty(default=0)

def new_band(name):
    """ Make and return a new band """
    the_band = Band(parent=band_key(), name=name)
    the_band.put()
    debug_print('new_band: added new band: {0}'.format(name))
    return the_band
        
def get_band_from_name(band_name):
    """ Return a Band object by name"""
    bands_query = Band.query(Band.name==band_name, ancestor=band_key())
    band = bands_query.fetch(1)
    debug_print('get_band_from_name: found {0} bands for name {1}'.format(len(band),band_name))
    if len(band)==1:
        return band[0]
    else:
        return None
        
def get_band_from_key(key):
    """ Return band objects by key"""
    return key.get()

def get_band_from_id(id):
    """ Return band object by id"""
    debug_print('get_band_from_id looking for id {0}'.format(id))
    return Band.get_by_id(int(id), parent=band_key()) # todo more efficient if we use the band because it's the parent?
    
def get_all_bands():
    """ Return all objects"""
    bands_query = Band.query(ancestor=band_key()).order(Band.lower_name)
    all_bands = bands_query.fetch()
    debug_print('get_all_bands: found {0} bands'.format(len(all_bands)))
    return all_bands

def get_section_keys_of_band_key(the_band_key):
    return the_band_key.get().sections

def get_member_keys_of_band_key_by_section_key(the_band_key):
    the_info=[]
    section_keys=get_section_keys_of_band_key(the_band_key)
    for a_section_key in section_keys:
        the_member_keys=assoc.get_member_keys_for_band_key_for_section_key(the_band_key, a_section_key)
        the_info.append([a_section_key,the_member_keys])

    no_section_members=assoc.get_member_keys_of_band_key_no_section(the_band_key)
    if no_section_members:
        the_info.append([None,no_section_members])

    return the_info
    
def new_section_for_band(the_band, the_section_name):
    the_section = Section(parent=the_band.key, name=the_section_name)
    the_section.put()
    debug_print('new section {0} for band {1}'.format(the_section_name, the_band.name))
    if the_band.sections:
        if the_section not in the_band.sections:
            the_band.sections.append(the_section.key)
    else:
        the_band.sections=[the_section.key]
    the_band.put()
    return the_section

def delete_section_key(the_section_key):
    #todo make sure the section is empty before deleting it

    # get the parent band's list of sections and delete ourselves
    the_band=the_section_key.parent().get()
    if the_section_key in the_band.sections:
        i=the_band.sections.index(the_section_key)
        the_band.sections.pop(i)
        the_band.put()
    the_section_key.delete()

#
# class for section
#
class Section(ndb.Model):
    """ Models an instrument section in a band """
    name = ndb.StringProperty()

#
#
# Handlers
#
#

class InfoPage(BaseHandler):
    """ class to produce the band info page """

    @user_required
    def get(self):    
        """ make the band info page """
        self._make_page(the_user=self.user)

    def _make_page(self,the_user):
        """ produce the info page """
        
        # find the band we're interested in
        band_key_str=self.request.get("bk", None)
        if band_key_str is None:
            self.response.write('no band key passed in!')
            return # todo figure out what to do if there's no ID passed in

        the_band_key=ndb.Key(urlsafe=band_key_str)
        the_band=the_band_key.get()

        if the_band is None:
            self.response.write('did not find a band!')
            return # todo figure out what to do if we didn't find it
            
        the_user_is_associated = assoc.get_associated_status_for_member_for_band_key(the_user, the_band_key)
        the_user_is_confirmed = assoc.get_confirmed_status_for_member_for_band_key(the_user, the_band_key)
        the_user_admin_status = assoc.get_admin_status_for_member_for_band_key(the_user, the_band_key)   

        if the_user_admin_status or member.member_is_superuser(the_user):
            the_pending = assoc.get_pending_members_from_band_key(the_band_key)
        else:
            the_pending = []

        template_args = {
            'title' : 'Band Info',
            'the_band' : the_band,
            'the_user_is_associated' : the_user_is_associated,
            'the_user_is_confirmed' : the_user_is_confirmed,
            'the_user_is_band_admin' : the_user_admin_status,
            'the_pending_members' : the_pending,
        }
        self.render_template('band_info.html', template_args)

        # todo make sure the admin is really there
        
class EditPage(BaseHandler):

    @user_required
    def get(self):
        self.make_page(the_user=self.user)

    def make_page(self, the_user):

        if self.request.get("new",None) is not None:
            #  creating a new band
            # todo MAKE SURE I'M AN ADMIN
            the_band=None
            is_new=True
        else:
            is_new=False
            the_band_key=self.request.get("bk",'0')
            if the_band_key=='0':
                return
            else:
                the_band=ndb.Key(urlsafe=the_band_key).get()
                if the_band is None:
                    self.response.write('did not find a band!')
                    return # todo figure out what to do if we didn't find it

        template_args = {
            'title' : 'Band Edit',
            'the_band' : the_band,
            'newmember_is_active' : is_new,
            'is_new' : is_new
        }
        self.render_template('band_edit.html', template_args)
                    
    def post(self):
        """post handler - if we are edited by the template, handle it here and redirect back to info page"""

        the_user = self.user

        the_band_key=self.request.get("bk",'0')
        
        if the_band_key=='0':
            # it's a new band
            the_band=new_band('tmp')
        else:
            the_band=ndb.Key(urlsafe=the_band_key).get()
            
        if the_band is None:
            self.response.write('did not find a band!')
            return # todo figure out what to do if we didn't find it
       
        band_name=self.request.get("band_name",None)
        if band_name is not None and band_name != '':
            the_band.name=band_name
                
        the_band.website=self.request.get("band_website",None)

        the_band.description=self.request.get("band_description",None)
            
        band_tz=self.request.get("band_tz",None)
        if band_tz is not None and band_tz != '':
            the_band.time_zone_correction=int(band_tz)

        the_band.put()            

        return self.redirect('/band_info.html?bk={0}'.format(the_band.key.urlsafe()))
        
class BandGetMembers(BaseHandler):
    """ returns the members related to a band """                   

    def post(self):    
        """ return the members for a band """
        the_user = self.user

        the_band_key_str=self.request.get('bk','0')
        
        if the_band_key_str=='0':
            return # todo figure out what to do
            
        the_band_key = ndb.Key(urlsafe=the_band_key_str)

        assocs = assoc.get_assocs_of_band_key(the_band_key=the_band_key, confirmed_only=True)
        assoc_info=[]
        the_user_is_band_admin = False
        for a in assocs:
            assoc_info.append( {'name':a.member_name, 'is_confirmed':a.is_confirmed, 'is_band_admin':a.is_band_admin, 'member_key':a.member} )
            if a.member == the_user.key:
                the_user_is_band_admin = a.is_band_admin
                        
        template_args = {
            'the_band_key' : the_band_key,
            'the_assocs' : assoc_info,
            'the_user_is_band_admin' : the_user_is_band_admin,
        }
        self.render_template('band_members.html', template_args)

class BandGetSections(BaseHandler):
    """ returns the sections related to a band """                   

    def post(self):    
        """ return the sections for a band """
        the_user = self.user

        the_band_key_str=self.request.get('bk','0')
        
        if the_band_key_str=='0':
            return # todo figure out what to do
            
        the_band_key = ndb.Key(urlsafe=the_band_key_str)
        the_members_by_section = get_member_keys_of_band_key_by_section_key(the_band_key)

        the_user_is_band_admin = assoc.get_admin_status_for_member_for_band_key(the_user, the_band_key)
                
        template_args = {
            'the_members_by_section' : the_members_by_section,
            'the_user_is_band_admin' : the_user_is_band_admin
        }
        self.render_template('band_sections.html', template_args)

class NewSection(BaseHandler):
    """ makes a new section for a band """                   

    def post(self):    
        """ makes a new assoc for a member """
        
        print 'in new section handler'
        
        the_user = self.user
        
        the_section_name=self.request.get('section_name','0')
        the_band_key=self.request.get('bk','0')
        
        if the_section_name=='0' or the_band_key=='0':
            return # todo figure out what to do
            
        the_band=ndb.Key(urlsafe=the_band_key).get()
        
        new_section_for_band(the_band, the_section_name)

class DeleteSection(BaseHandler):
    """ makes a new section for a band """                   

    def post(self):    
        """ makes a new assoc for a member """
        
        print 'in new section handler'
        
        the_user = self.user
        
        the_section_key_url=self.request.get('sk','0')
        
        if the_section_key_url=='0':
            return # todo figure out what to do

        the_section_key=ndb.Key(urlsafe=the_section_key_url)
        
        delete_section_key(the_section_key)

class MoveSection(BaseHandler):
    """ move a section for a band """                   

    @user_required
    def post(self):    
        """ moves a section """
        
        the_user = self.user
        
        the_direction=self.request.get('dir','0')
        the_section_key=self.request.get('sk','0')
        
        the_section_key=ndb.Key(urlsafe=the_section_key)
        the_section=the_section_key.get()
        the_band=the_section_key.parent().get()
        
        band_sections = the_band.sections
        if the_section_key in band_sections:
            i = band_sections.index(the_section_key)
            band_sections.pop(i)
            if the_direction == '1':
                band_sections.insert(i-1, the_section_key)
            else:
                band_sections.insert(i+1, the_section_key)
        
            the_band.sections=band_sections
            the_band.put()
        else:
            print 'not in band'
        
class ConfirmMember(BaseHandler):
    """ move a member from pending to 'real' member """
    
    @user_required
    def get(self):
        """ handles the 'confirm member' button in the band info page """
        
        the_user = self.user

        # todo make sure we are a band admin        
        the_member_keyurl=self.request.get('mk','0')
        the_band_keyurl=self.request.get('bk','0')
        
        if the_member_keyurl=='0' or the_band_keyurl=='0':
            return # todo what to do?
            
        the_member_key=ndb.Key(urlsafe=the_member_keyurl)
        the_band_key=ndb.Key(urlsafe=the_band_keyurl)
                    
        the_member = the_member_key.get()
        assoc.confirm_member_for_band_key(the_member, the_band_key)

        the_band = the_band_key.get()
        goemail.send_band_accepted_email(the_member.email_address, the_band)

        return self.redirect('/band_info.html?bk={0}'.format(the_band_keyurl))
        
class AdminMember(BaseHandler):
    """ grant or revoke admin rights """
    
    @user_required
    def get(self):
        """ post handler - wants a member key and a band key, and a flag """
        
        # todo - make sure the user is a superuser or already an admin of this band

        the_member_keyurl=self.request.get('mk','0')
        the_band_keyurl=self.request.get('bk','0')
        the_do=self.request.get('do','')

        if the_member_keyurl=='0' or the_band_keyurl=='0':
            return # todo figure out what to do

        if the_do=='':
            return # todo figure out what to do

        the_member_key = ndb.Key(urlsafe=the_member_keyurl)
        the_band_key = ndb.Key(urlsafe=the_band_keyurl)
        assoc.set_admin_for_member_key_and_band_key(the_member_key, the_band_key, int(the_do))

        return self.redirect('/band_info.html?bk={0}'.format(the_band_keyurl))

class RemoveMember(BaseHandler):
    """ user quits band """
    
    @user_required
    def get(self):
        """ post handler - wants an ak """
        
        # todo - make sure the user is a superuser or already an admin of this band

        the_member_keyurl=self.request.get('mk','0')
        the_band_keyurl=self.request.get('bk','0')

        if the_member_keyurl=='0' or the_band_keyurl=='0':
            return # todo figure out what to do

        the_member_key = ndb.Key(urlsafe=the_member_keyurl)
        the_band_key = ndb.Key(urlsafe=the_band_keyurl)
        assoc.delete_association(the_member_key.get(), the_band_key)

        return self.redirect('/band_info.html?bk={0}'.format(the_band_keyurl))

class AdminPage(BaseHandler):
    """ Page for band administration """

    @user_required
    def get(self):    
        self._make_page(the_user=self.user)
            
    def _make_page(self,the_user):
    
        # todo make sure the user is a superuser
        
        the_bands = get_all_bands()
        
        template_args = {
            'title' : 'Band Admin',
            'the_bands' : the_bands,
        }
        self.render_template('band_admin.html', template_args)
