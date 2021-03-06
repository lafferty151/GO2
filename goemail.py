
import webapp2
from google.appengine.api import mail
from google.appengine.api import users
from google.appengine.api.taskqueue import taskqueue

import band
import gig
import member
import assoc
import logging
import re

import pickle

from webapp2_extras import i18n
from webapp2_extras import jinja2
from webapp2_extras.i18n import gettext as _

SENDER_EMAIL = 'gigomatic.superuser@gmail.com'

def validate_email(the_string):
    if re.match(r"^[_a-z0-9-]+(\.[_a-z0-9-]+)*@[a-z0-9-]+(\.[a-z0-9-]+)*(\.[a-z]{2,4})$",the_string.lower()):
        return True

def send_registration_email(the_email, the_url):

    if not mail.is_email_valid(the_email):
        return False
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_email
    message.subject = _('Welcome to Gig-o-Matic')
    message.body=_('welcome_msg_email').format(the_url)
    
    try:
        message.send()
    except:
        logging.error('failed to send email!')
        
    return True

def send_band_accepted_email(the_email, the_band):
    if not mail.is_email_valid(the_email):
        return False
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_email
    message.subject = _('Gig-o-Matic: Confirmed!')
    message.body = _('member_confirmed_email').format(the_band.name, the_band.key.urlsafe())

    try:
        message.send()
    except:
        logging.error('failed to send email!')
        
    return True
    
def send_forgot_email(the_email, the_url):

    if not mail.is_email_valid(the_email):
        logging.error("send_forgot_email invalid email: {0}".format(the_email))
        return False
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_email
    message.subject = _('Gig-o-Matic Password Reset')
    message.body = _('forgot_password_email').format(the_url)

    try:
        message.send()
    except:
        logging.error('failed to send email!')
        
    return True
    
##########
#
# send an email announcing a new gig
#
##########    
def send_newgig_email(the_member, the_gig, the_band, the_gig_url, is_edit=False, is_reminder=False, change_string=""):
 
    the_locale=the_member.preferences.locale
    the_email_address = the_member.email_address
    
    if not mail.is_email_valid(the_email_address):
        return False

    i18n.get_i18n().set_locale(the_locale)
        
    contact_key=the_gig.contact
    if contact_key:
        contact = contact_key.get()
        contact_name=contact.name
    else:
        contact = None
        contact_name="??"        

    # get the special URLs for "yes" and "no" answers
    the_yes_url, the_no_url, the_snooze_url = gig.get_confirm_urls(the_member, the_gig)
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    if contact is not None:
        message.reply_to = contact.email_address
    message.to = the_email_address
    if is_edit:
        title_string='{0} ({1})'.format(_('Gig Edit'),change_string)
    elif is_reminder:
        title_string='Gig Reminder:'
    else:
        title_string=_('New Gig:')
    message.subject = u'{0} {1}'.format(title_string, the_gig.title)
    the_date_string = "{0} ({1})".format(member.format_date_for_member(the_member, the_gig.date),
                                       member.format_date_for_member(the_member, the_gig.date, "day"))

    the_time_string = ""
    if the_gig.calltime:
        the_time_string = u'{0} ({1})'.format(the_gig.calltime, _('Call Time'))
    if the_gig.settime:
        if the_time_string:
            the_time_string = u'{0}, '.format(the_time_string)
        the_time_string = u'{0}{1} ({2})'.format(the_time_string,the_gig.settime, _('Set Time'))
    if the_gig.endtime:
        if the_time_string:
            the_time_string = u'{0}, '.format(the_time_string)
        the_time_string = u'{0}{1} ({2})'.format(the_time_string,the_gig.endtime, _('End Time'))
        
    the_status_string=[_('Unconfirmed'), _('Confirmed!'), _('Cancelled!')][the_gig.status]
        
    if is_edit:
        message.body=_('edited_gig_email').format(the_band.name, the_gig.title, the_date_string, the_time_string, contact_name, the_status_string, the_gig.details, the_gig_url, change_string)
    elif is_reminder:
        message.body=_('reminder_gig_email').format(the_band.name, the_gig.title, the_date_string, the_time_string, contact_name, the_status_string, the_gig.details, the_gig_url,"",the_yes_url,the_no_url,the_snooze_url)
        message.html=_('reminder_gig_email_html').format(the_band.name, the_gig.title, the_date_string, the_time_string, contact_name, the_status_string, the_gig.details, the_gig_url,"",the_yes_url,the_no_url,the_snooze_url)
    else:
        message.body=_('new_gig_email').format(the_band.name, the_gig.title, the_date_string, the_time_string, contact_name, the_status_string, the_gig.details, the_gig_url,"",the_yes_url,the_no_url,the_snooze_url)
        message.html=_('new_gig_email_html').format(the_band.name, the_gig.title, the_date_string, the_time_string, contact_name, the_status_string, the_gig.details, the_gig_url,"",the_yes_url,the_no_url,the_snooze_url)
        
    try:
        message.send()
    except:
        logging.error('failed to send email!')
        
    return True


def announce_new_gig(the_gig, the_gig_url, is_edit=False, is_reminder=False, change_string="", the_members=[]):

    the_params = pickle.dumps({'the_gig_key': the_gig.key,
                            'the_gig_url': the_gig_url,
                            'is_edit': is_edit,
                            'is_reminder': is_reminder,
                            'change_string': change_string,
                            'the_members': the_members})

    taskqueue.add(
            url='/announce_new_gig_handler',
            params={'the_params': the_params
            })

class AnnounceNewGigHandler(webapp2.RequestHandler):

    def post(self):

        the_params = pickle.loads(self.request.get('the_params'))

        the_gig_key  = the_params['the_gig_key']
        the_gig_url = the_params['the_gig_url']
        is_edit = the_params['is_edit']
        is_reminder = the_params['is_reminder']
        change_string = the_params['change_string']
        the_members = the_params['the_members']

        the_gig = the_gig_key.get()
        the_band_key = the_gig_key.parent()
        the_assocs = assoc.get_confirmed_assocs_of_band_key(the_band_key, include_occasional=the_gig.invite_occasionals)

        if is_reminder and the_members:
            recipient_assocs=[]
            for a in the_assocs:
                if a.member in the_members:
                    recipient_assocs.append(a)
        else:
            recipient_assocs = the_assocs

        logging.info('announcing gig {0} to {1} people'.format(the_gig_key,len(recipient_assocs)))


        the_shared_params = pickle.dumps({
            'the_gig_key': the_gig_key,
            'the_band_key': the_band_key,
            'the_gig_url': the_gig_url,
            'is_edit': is_edit,
            'is_reminder': is_reminder,
            'change_string': change_string
        })

        for an_assoc in recipient_assocs:
            if an_assoc.email_me:
                the_member_key = an_assoc.member

                the_member_params = pickle.dumps({
                    'the_member_key': the_member_key
                })

                task = taskqueue.add(
                    queue_name='emailqueue',
                    url='/send_new_gig_handler',
                    params={'the_shared_params': the_shared_params,
                            'the_member_params': the_member_params
                    })                
                # send_newgig_email(the_member, the_gig, the_band, the_gig_url, is_edit, is_reminder, change_string)
        
        logging.info('announced gig {0}'.format(the_gig_key))

        self.response.write( 200 )


class SendNewGigHandler(webapp2.RequestHandler):

    def post(self):

        the_shared_params = pickle.loads(self.request.get('the_shared_params'))
        the_member_params = pickle.loads(self.request.get('the_member_params'))

        the_member_key  = the_member_params['the_member_key']
        the_gig_key = the_shared_params['the_gig_key']
        the_band_key = the_shared_params['the_band_key']
        the_gig_url = the_shared_params['the_gig_url']
        is_edit = the_shared_params['is_edit']
        is_reminder = the_shared_params['is_reminder']
        change_string = the_shared_params['change_string']

        send_newgig_email(the_member_key.get(), the_gig_key.get(), the_band_key.get(), the_gig_url, is_edit, is_reminder, change_string)

        self.response.write( 200 )


def send_new_member_email(band,new_member):
    members=assoc.get_admin_members_from_band_key(band.key)
    for the_member in members:
        send_the_new_member_email(the_member.preferences.locale, the_member.email_address, new_member=new_member, the_band=band)
        
 
def send_the_new_member_email(the_locale, the_email_address, new_member, the_band):

    if not mail.is_email_valid(the_email_address):
        return False
        
    i18n.get_i18n().set_locale(the_locale)
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_email_address
    message.subject = _('Gig-o-Matic New Member for band {0})').format(the_band.name)
    message.body = _('new_member_email').format( '{0} ({1})'.format(new_member.name, new_member.email_address), the_band.name, the_band.key.urlsafe())

    try:
        message.send()
    except:
        logging.error('failed to send email!')
        
    return True        

def send_new_band_via_invite_email(the_band, the_member):
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_member.email_address
    message.subject = _('Gig-o-Matic New Band Invite')
    message.body = _('new_band_via_invite_email').format(the_band.name)
    try:
        message.send()
    except:
        logging.error(u'failed to send new_band_via_invite email to user {0}!'.format(the_member.email_address))

    return True

def send_gigo_invite_email(the_band, the_member, the_url):
    if not mail.is_email_valid(the_member.email_address):
        return False
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_member.email_address
    message.subject = _('Invitation to Join Gig-o-Matic')
    message.body=_('gigo_invite_email').format(the_band.name, the_url)
    try:
        message.send()
    except:
        logging.error('failed to send email!')


def send_the_pending_email( the_email_address, the_confirm_link):
    if not mail.is_email_valid(the_email_address):
        return False
        
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = the_email_address
    message.subject = _('Gig-o-Matic Confirm Email Address')
    message.body=_('confirm_email_address_email').format(the_confirm_link)
    try:
        message.send()
    except:
        logging.error('failed to send email!')

    return True

def notify_superuser_of_archive(the_num):
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = 'gigomatic.superuser@gmail.com'
    message.subject = 'Gig-o-Matic Auto-Archiver'
    message.body = """
Yo! The Gig-o-Matic archived {0} gigs last night.
    """.format(the_num)
    try:
        message.send()
    except:
        logging.error('failed to send email!')
        
    return True        


def notify_superuser_of_old_tokens(the_num):
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = 'gigomatic.superuser@gmail.com'
    message.subject = 'Gig-o-Matic Old Tokens'
    message.body = """
Yo! The Gig-o-Matic found {0} old signup tokens last night.
    """.format(the_num)
    try:
        message.send()
    except:
        logging.error('failed to send email!')
    return True        

def send_band_request_email(the_email_address, the_name, the_info):
    if not mail.is_email_valid(the_email_address):
        return False
    message = mail.EmailMessage()
    message.sender = SENDER_EMAIL
    message.to = 'gigomatic.superuser@gmail.com'
    message.subject = 'Gig-o-Matic New Band Request'
    message.body = u"""
Hi there! Someone has requested to add their band to the Gig-o-Matic. SO EXCITING!

{0}
{1}
{2}

Enjoy,
Team Gig-o-Matic

    """.format(the_email_address, the_name, the_info)
    try:
        message.send()
    except:
        logging.error('failed to send email!')

    return True
