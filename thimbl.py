'''thimbl.py - Command-line python tools '''

import copy
import cStringIO
import datetime
import getpass
import json
import pdb
import optparse
import os
import platform
import re
import subprocess
import sys
import time


#################################################################

def writeln(text):
    print text
        
#################################################################

class Data:
    def __init__(self):

        # Try to load the cache file, if it exists
        thimblfile = self.__cache_filename()
        if os.path.isfile(thimblfile):
            data = load(thimblfile)
        else:
            print 'Configuration was guessed. You should run the commands'
            print "'info' or 'setup' to put in proper values"
            data = self.empty_cache()

        self.set_data(data)

    def set_data(self, data):
        self.whoami = data['me']
        self.data = data
        self.me = data['plans'][self.whoami]
            

    def __cache_filename(self):
        'Return the name of the cache file that stores all of the data'
        thimbldir = os.path.expanduser('~/.config/thimbl')
        try: os.makedirs(thimbldir)
        except OSError: pass # don't worry if directory already exists
        thimblfile = os.path.join(thimbldir, 'data1.jsn')
        return thimblfile

    def info(self):
        'Print some information about thimbl-cli'
        print "cache_filename: " + self.__cache_filename()
        me = self.me
        print "name:           " + me['name']
        print "address:        " + me['address']
        props =  me['properties']
        print "email:          " + props['email']
        print "mobile:         " + props['mobile']
        print "website:        " + props['website']

    def empty_cache(self):
        'Create a blank config cache, populating it with sensible defaults'

        host = platform.node()
        name = getpass.getuser() # user name
        email = '{0}@{1}'.format(name, host)
        address = email

        properties =  {}
        properties['website'] = 'http://' + host
        properties['mobile']  = 'Mobile withheld'
        properties['email'] = email

        plan = {}
        plan['address'] = address
        plan['name'] = name
        plan['messages'] = []
        plan['replies'] = {}
        plan['following'] = []
        plan['properties'] = properties

        return { 'me' : address, 'plans' : { address : plan }}


    def save_cache(self):
        cache_file = self.__cache_filename()
        save(self.data, cache_file)
 
    def fetch(self, wout = writeln):
        '''Retrieve all the plans of the people I am following'''
        for following in self.me['following']:
            address = following['address']
            if address == self.data['me']:
                wout("Stop fingering yourself!")
                continue

            wout('Fingering ' + address)
            try:
                plan = finger_user(address)
                wout("OK")
            except AttributeError:
                wout('Failed. Skipping')
                continue
            #print "DEBUG:", plan
            self.data['plans'][address] = plan
        wout('Finished')
    
    def follow(self, nick, address):

        # rebuild the list of followees, removing duplicate addresses
        followees = []
        for f in self.me['following']:
            if f['address'] == address:
                print "Dropping dupe address"
            else:
                followees.append(f)
                
        # now add the address back in
        followees.append({ 'nick' : nick, 'address' : address })

        self.me['following'] = followees
    
    def post(self, text):
        'Create a message. Remember to publish() it'
        timefmt = time.strftime('%Y%m%d%H%M%S', time.gmtime())
        message = { 'time' : timefmt, 'text' : text }
        self.me['messages'].append(message)
    
    
    def post_file(self, filename):
        'Create a post from the text in a file'
        text = file(filename, 'r').read()
        self.post(text)
        
    def prmess(self, wout = writeln):
        'Print messages in reverse chronological order'
        
        # accumulate messages
        messages = []
        for address in self.data['plans'].keys():
            plan = self.data['plans'][address]
            if not plan.has_key('messages'): continue
            for msg in plan['messages']:
                msg['address'] = address
                messages.append(msg)
                
        messages.sort(key = lambda x: x['time'])
        
        # print messages
        for msg in messages:
            # format time
            t = str(msg['time'])
            tlist = map(int, [t[:4], t[4:6], t[6:8], t[8:10], 
                              t[10:12], t[12:14]])
            tstruct = apply(datetime.datetime, tlist)
            ftime = tstruct.strftime('%Y-%m-%d %H:%M:%S')

            text = '{0}  {1}\n{2}\n\n'.format(ftime, msg['address'], 
                                              msg['text'].encode('utf-8'))
            wout(text)
        
        
    def following(self):
        'Who am I following?'
        followees = self.me['following']
        followees.sort(key = lambda x: x['nick'])
        for f in followees:
            print '{0:5} {1}'.format(f['nick'], f['address'])


    
    def setup(self):
        'Interactively enter user information'
        def getval(v, prompt):
            while True:
                print prompt + '=' + v+ ' [Accept (default)/Change/Erase]? '
                inp = raw_input()
                if inp in ['A', 'a', '']:
                    return v
                elif inp in ['C', 'c']:
                    print 'Input new value: ',
                    v = raw_input()
                    return v
                elif inp in ['E', 'e']:
                    return ''
                else:
                    print "Didn't understand your response"

        me = copy.copy(self.me)
        del self.data['plans'][self.whoami]
        me['name'] = getval(me['name'], 'Name')
        address = getval(me['address'], 'Address')
        me['address'] = address

        props = me['properties']
        props['website'] = getval(props['website'], 'Website')
        props['mobile'] = getval(props['mobile'], 'Mobile')
        props['email'] = getval(props['email'], 'Email')
        me['properties'] = props

        self.data['plans'][address] = me
        self.data['me'] = address
        self.set_data(self.data)



    def unfollow(self, address):
        'Remove an address from someone being followed'
        def func(f): return not (f['address'] == address)
        new_followees = filter(func, self.me['following'])
        self.me['following'] = new_followees
      

    
    def __del__(self):
        #print "Data exit"
        self.save_cache()
        save(self.me, os.path.expanduser('~/.plan'))
        
#################################################################


    
    



def finger_user(user_name):
    '''Try to finger a user, and convert the returned plan into a dictionary
    E.g. j = finger_user("dk@telekommunisten.org")
    print j['bio']    
    '''
    args = ['finger', user_name]
    p = subprocess.Popen(args, stdout=subprocess.PIPE)
    output = p.communicate()[0]
    m = re.search('^.*?Plan:\s*(.*)', output, re.M + re.S)
    raw = m.group(1)
    j = json.loads(raw)
    return j


    
    





def save(data, filename):
    'Save data to a file as a json file'
    j = json.dumps(data)
    file(filename, 'w').write(j)


         
def load(filename):
    'Load data from a json file'
    s = file(filename, 'r').read()
    return json.loads(s)


    


def main():

    #parser.add_option("-f", "--file", dest="filename",
    #help="write report to FILE", metavar="FILE")
    #parser.add_option("-q", "--quiet",
    #action="store_false", dest="verbose", default=True,
    #help="don't print status messages to stdout")
    #parser.add_option

    num_args = len(sys.argv) - 1
    if num_args < 1 :
        print "No command specified. Try help"
        return
        
    d = Data()
    cmd = sys.argv[1]
    if cmd =='fetch':
        d.fetch()
    elif cmd == 'follow':
        d.follow(sys.argv[2], sys.argv[3])
    elif cmd == 'following':
        d.following()
    elif cmd == 'info':
        d.info()
    elif cmd == 'help':
        print "Sorry, not much help at the moment"
    elif cmd == 'post':
        d.post(sys.argv[2])
    elif cmd == 'print':
        d.prmess()
    elif cmd == 'read':
        d.fetch()
        d.prmess()
    elif cmd == 'setup':
        d.setup()
    elif cmd == 'stdin':
        text = sys.stdin.read()
        d.post(text)
    elif cmd == 'unfollow':
        d.unfollow(sys.argv[2])
    else:
        print "Unrecognised command: ", cmd


if __name__ == "__main__":
    main()
