#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-
"""
File: paramiko_client.py
Author: Valentin Kuznetsov <vkuznet@gmail.com>
Description: Paramiko SSH module for cmssh

Some ideas taken from paramiko/demos/demo.py and
http://code.activestate.com/recipes/576810-copy-files-over-ssh-using-paramiko/
"""

# system modules
import os
import sys
import types
import socket
import select
import getpass
import paramiko
from   paramiko import Transport
from   binascii import hexlify

def agent_auth(transport, username):
    """
    Attempt to authenticate to the given transport using any of
    the private keys available from an SSH agent.
    """
    agent = paramiko.Agent()
    agent_keys = agent.get_keys()
    if  len(agent_keys) == 0:
        return
        
    for key in agent_keys:
        print 'Trying ssh-agent key %s' % hexlify(key.get_fingerprint()),
        try:
            transport.auth_publickey(username, key)
            print '... success!'
            return
        except paramiko.SSHException:
            print '... nope.'

def manual_auth(transport, username, hostname):
    """
    Attempt to authenticate to the given transport using manual
    login/password method
    """
    default_auth = 'p'
#    auth = raw_input(\
#        'Authenticate by (p)assword, (r)sa key, or (d)sa key? [%s] ' % default_auth)
#    if  len(auth) == 0:
#        auth = default_auth
    auth = default_auth

    if  auth == 'r':
        default_path = os.path.join(os.environ['HOME'], '.ssh', 'id_rsa')
        path = raw_input('RSA key [%s]: ' % default_path)
        if  len(path) == 0:
            path = default_path
        try:
            key = paramiko.RSAKey.from_private_key_file(path)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('RSA key password: ')
            key = paramiko.RSAKey.from_private_key_file(path, password)
        transport.auth_publickey(username, key)
    elif auth == 'd':
        default_path = os.path.join(os.environ['HOME'], '.ssh', 'id_dsa')
        path = raw_input('DSS key [%s]: ' % default_path)
        if len(path) == 0:
            path = default_path
        try:
            key = paramiko.DSSKey.from_private_key_file(path)
        except paramiko.PasswordRequiredException:
            password = getpass.getpass('DSS key password: ')
            key = paramiko.DSSKey.from_private_key_file(path, password)
        transport.auth_publickey(username, key)
    else:
        passwd = getpass.getpass('Password for %s@%s: ' % (username, hostname))
        transport.auth_password(username, passwd)

def connect(username, hostname='lxplus.cern.ch', port=22):
    "Connect to a given host"
    print "Connecting to %s@%s" % (username, hostname)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((hostname, port))
    except Exception as err:
        print '*** Connect failed: ' + str(err)
        sys.exit(1)
    transport = Transport(sock)
    try:
        transport.start_client()
    except paramiko.SSHException as err:
        print "SSH negotiation failed\n%s" % str(err)

    try:
        keys = paramiko.util.load_host_keys(\
                os.path.expanduser('~/.ssh/known_hosts'))
    except IOError:
        try:
            keys = paramiko.util.load_host_keys(\
                os.path.expanduser('~/ssh/known_hosts'))
        except IOError:
            print '*** Unable to open host keys file'
            keys = {}

    # check server's host key -- this is important.
    key = transport.get_remote_server_key()
    if  not keys.has_key(hostname):
        print '*** WARNING: Unknown host key!'
    elif not keys[hostname].has_key(key.get_name()):
        print '*** WARNING: Unknown host key!'
    elif keys[hostname][key.get_name()] != key:
        print '*** WARNING: Host key has changed!!!'
        sys.exit(1)
    else:
        pass

    # get username
    if  username == '':
        default_username = getpass.getuser()
        username = raw_input('Username [%s]: ' % default_username)
        if  len(username) == 0:
            username = default_username

    agent_auth(transport, username)
    if not transport.is_authenticated():
        manual_auth(transport, username, hostname)
    if not transport.is_authenticated():
        print '*** Authentication failed. :('
        transport.close()
        sys.exit(1)
    return transport, sock

def execute(cmd, username, hostname='lxplus.cern.ch'):
    "Execute given command on remove host"
    transport, sock = connect(username, hostname)
    channel = transport.open_session()
    channel.exec_command(cmd)
    stdout = [l.replace('\n', '') for l in channel.makefile()]
    stderr = [l.replace('\n', '') for l in channel.makefile_stderr()]
    channel.close()
    transport.close()
    sock.close()
    return stdout, stderr

def test():
    "test function"
    username = raw_input('username: ')
    result = execute('ls', username)
    print result, type(result)

if  __name__ == '__main__':
    test()
