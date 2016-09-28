import praw
import time
import re
import os
import json
from configparser import ConfigParser
# from apiclient.errors import HttpError

#    Configs    ###

# oauth stuff - reenable when oauth stops being broken
# client_id=os.environ.get('client_id')
# client_secret=os.environ.get('client_secret')
# redirect_uri='http://127.0.0.1:65010/authorize_callback'
# state="Modmail Archivist"
# refresh_token=os.environ.get('refresh_token')

config = ConfigParser()
config.read('mmb_config.ini')

owner      = config.get('reddit', 'owner')
version    = config.get('reddit', 'version')
username   = config.get('reddit', 'username')
password   = config.get('reddit', 'password')
user_agent = username + ' by ' + owner + ' version ' + version

r = praw.Reddit(user_agent)

#  End Configs  ###


class Bot():

    def oauth_login(self):
        # Oauth currently disabled due to praw bug where oauth does not work in private subreddits

        # r.set_oauth_app_info(client_id, client_secret, redirect_uri)

        # r.refresh_access_information(refresh_token)

        r.login(username, password, disable_warning=True)

        print('authentication successful')

    def message_string(self, message):
        # Takes a single message object and returns a markdown string to be used in the archive post

        # From - check distinguished status and append #mod or #admin to username link as needed - for CSS hooks
        # also check for [deleted]
        if message.distinguished == 'moderator':
            archive_string = 'from ['+message.author.name+'](/u/'+message.author.name+'#mod) '
        elif message.distinguished == 'admin':
            archive_string = 'from ['+message.author.name+'](/u/'+message.author.name+'#admin) '
        elif message.author==None:
            archive_string = 'from [deleted] '
        else:
            archive_string = 'from ['+message.author.name+'](/u/'+message.author.name+') '

        # To
        archive_string = archive_string + 'to ' + message.dest

        # Timestamp
        timestamp = time.strftime("%a %b %d %Y %H:%M:%S GMT",time.gmtime(int(message.created_utc)))
        archive_string = archive_string + ' at ' + timestamp + '\n\n'

        # Message contents
        archive_string = archive_string + message.body

        # Replace --- and ___ line seperators with ##--- or ##___ due to subreddit css
        archive_string = re.sub("\n---+\n","\n##---\n",archive_string)
        archive_string = re.sub("\n___+\n","\n##___\n",archive_string)

        return archive_string

    def archive_modmail(self):

        i=-1
        for modmail in r.get_mod_mail('mod', limit=1000):
            # Get the corresponding archive subreddit - if there isn't one then skip modmail
            # This is necessary to prevent it spending time trying to archive modmail in archive subreddits

            archive_subreddit = "ar_modmail"

            i+=1
            # Begin assembling text, starting with permalink
            archive_text = 'https://www.reddit.com/message/messages/'+modmail.id+'\n\n---\n\n'

            isMod = False
            isBanned = False

            message_title = ""

            if "you've been banned from" in modmail.subject.lower():
                isBanned = True
            if modmail.distinguished:
                isMod = True

            if isBanned:
                message_title = "[Ban thread] " + modmail.subject
            elif isMod:
                message_title = "[Mod thread] " + modmail.subject
            else:
                message_title = modmail.subject

            # First message
            archive_text = archive_text + self.message_string(modmail)

            # all reply message objects
            for reply in modmail.replies:
                archive_text = archive_text + '\n\n---\n\n' + self.message_string(reply)

            # Check and see if there's a submission for this thread already
            permalink = "http://www.reddit.com/message/messages/"+modmail.id
            query = "self:yes selftext:"+permalink

            for submission in r.search(query, subreddit=archive_subreddit,sort='new'):

                # Make sure search result isn't a false positive due to one thread being linked in another
                # since message permalink is first thing in archive text, this works

                if not submission.selftext.startswith(permalink):
                    continue

                # Check to see if nothing has changed, and if so, stop (because we're out of modmails to do since last cycle)
                if submission.selftext == archive_text:
                    print('all done for now. %(i)s threads archived or updated' % {"i":str(i)})
                    return

                # try to edit; otherwise remove and resubmit
                try:
                    submission.edit(archive_text)
                    print('submission edited')
                except:
                    submission.remove()
                    r.submit(archive_subreddit, message_title, text=archive_text).approve()
                    print('removed and recreated submission')

                break

            else:
                # If there isn't an existing submission, make one and self-approve it
                r.submit(archive_subreddit, message_title, text=archive_text).approve()
                print('new submission created')


if __name__=='__main__':
    modbot=Bot()
    print('running cycle')
    while True:
        try:
            modbot.oauth_login()
            modbot.archive_modmail()
            break
        except HttpError:
            print("HTTP error occured, retrying in 20 seconds")
            time.sleep(20)
            continue