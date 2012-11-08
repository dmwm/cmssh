#!/usr/bin/env python
#-*- coding: ISO-8859-1 -*-

"""
Print utilities
"""

__revision__ = "$Id: iprint.py,v 1.5 2009/10/20 15:00:55 valya Exp $"
__version__ = "$Revision: 1.5 $"
__author__ = "Valentin Kuznetsov"

import sys
import re

#
# http://code.activestate.com/recipes/475116/
#
class TerminalController:
    """
    A class that can be used to portably generate formatted output to
    a terminal.  
    
    `TerminalController` defines a set of instance variables whose
    values are initialized to the control sequence necessary to
    perform a given action.  These can be simply included in normal
    output to the terminal:

        >>> term = TerminalController()
        >>> print 'This is '+term.GREEN+'green'+term.NORMAL

    Alternatively, the `render()` method can used, which replaces
    '${action}' with the string required to perform 'action':

        >>> term = TerminalController()
        >>> print term.render('This is ${GREEN}green${NORMAL}')

    If the terminal doesn't support a given action, then the value of
    the corresponding instance variable will be set to ''.  As a
    result, the above code will still work on terminals that do not
    support color, except that their output will not be colored.
    Also, this means that you can test whether the terminal supports a
    given action by simply testing the truth value of the
    corresponding instance variable:

        >>> term = TerminalController()
        >>> if term.CLEAR_SCREEN:
        ...     print 'This terminal supports clearning the screen.'

    Finally, if the width and height of the terminal are known, then
    they will be stored in the `COLS` and `LINES` attributes.
    """
    # Cursor movement:
    BOL = ''             #: Move the cursor to the beginning of the line
    UP = ''              #: Move the cursor up one line
    DOWN = ''            #: Move the cursor down one line
    LEFT = ''            #: Move the cursor left one char
    RIGHT = ''           #: Move the cursor right one char

    # Deletion:
    CLEAR_SCREEN = ''    #: Clear the screen and move to home position
    CLEAR_EOL = ''       #: Clear to the end of the line.
    CLEAR_BOL = ''       #: Clear to the beginning of the line.
    CLEAR_EOS = ''       #: Clear to the end of the screen

    # Output modes:
    BOLD = ''            #: Turn on bold mode
    BLINK = ''           #: Turn on blink mode
    DIM = ''             #: Turn on half-bright mode
    REVERSE = ''         #: Turn on reverse-video mode
    NORMAL = ''          #: Turn off all modes

    # Cursor display:
    HIDE_CURSOR = ''     #: Make the cursor invisible
    SHOW_CURSOR = ''     #: Make the cursor visible

    # Terminal size:
    COLS = None          #: Width of the terminal (None for unknown)
    LINES = None         #: Height of the terminal (None for unknown)

    # Foreground colors:
    BLACK = BLUE = GREEN = CYAN = RED = MAGENTA = YELLOW = WHITE = ''
    
    # Background colors:
    BG_BLACK = BG_BLUE = BG_GREEN = BG_CYAN = ''
    BG_RED = BG_MAGENTA = BG_YELLOW = BG_WHITE = ''
    
    _STRING_CAPABILITIES = """
    BOL=cr UP=cuu1 DOWN=cud1 LEFT=cub1 RIGHT=cuf1
    CLEAR_SCREEN=clear CLEAR_EOL=el CLEAR_BOL=el1 CLEAR_EOS=ed BOLD=bold
    BLINK=blink DIM=dim REVERSE=rev UNDERLINE=smul NORMAL=sgr0
    HIDE_CURSOR=cinvis SHOW_CURSOR=cnorm""".split()
    _COLORS = """BLACK BLUE GREEN CYAN RED MAGENTA YELLOW WHITE""".split()
    _ANSICOLORS = "BLACK RED GREEN YELLOW BLUE MAGENTA CYAN WHITE".split()

    def __init__(self, term_stream=sys.stdout):
        """
        Create a `TerminalController` and initialize its attributes
        with appropriate values for the current terminal.
        `term_stream` is the stream that will be used for terminal
        output; if this stream is not a tty, then the terminal is
        assumed to be a dumb terminal (i.e., have no capabilities).
        """
        # Curses isn't available on all platforms
        try: import curses
        except: return

        # If the stream isn't a tty, then assume it has no capabilities.
        if not term_stream.isatty(): return

        # Check the terminal type.  If we fail, then assume that the
        # terminal has no capabilities.
        try: curses.setupterm()
        except: return

        # Look up numeric capabilities.
        self.COLS = curses.tigetnum('cols')
        self.LINES = curses.tigetnum('lines')
        
        # Look up string capabilities.
        for capability in self._STRING_CAPABILITIES:
            (attrib, cap_name) = capability.split('=')
            setattr(self, attrib, self._tigetstr(cap_name) or '')

        # Colors
        set_fg = self._tigetstr('setf')
        if set_fg:
            for i, color in zip(range(len(self._COLORS)), self._COLORS):
                setattr(self, color, curses.tparm(set_fg, i) or '')
        set_fg_ansi = self._tigetstr('setaf')
        if set_fg_ansi:
            for i, color in zip(range(len(self._ANSICOLORS)), self._ANSICOLORS):
                setattr(self, color, curses.tparm(set_fg_ansi, i) or '')
        set_bg = self._tigetstr('setb')
        if set_bg:
            for i, color in zip(range(len(self._COLORS)), self._COLORS):
                setattr(self, 'BG_'+color, curses.tparm(set_bg, i) or '')
        set_bg_ansi = self._tigetstr('setab')
        if set_bg_ansi:
            for i, color in zip(range(len(self._ANSICOLORS)), self._ANSICOLORS):
                setattr(self, 'BG_'+color, curses.tparm(set_bg_ansi, i) or '')

    def _tigetstr(self, cap_name):
        # String capabilities can include "delays" of the form "$<2>".
        # For any modern terminal, we should be able to just ignore
        # these, so strip them out.
        import curses
        cap = curses.tigetstr(cap_name) or ''
        return re.sub(r'\$<\d+>[/*]?', '', cap)

    def render(self, template):
        """
        Replace each $-substitutions in the given template string with
        the corresponding terminal control string (if it's defined) or
        '' (if it's not).
        """
        return re.sub(r'\$\$|\${\w+}', self._render_sub, template)

    def _render_sub(self, match):
        s = match.group()
        if s == '$$': return s
        else: return getattr(self, s[2:-1])

#######################################################################
# Example use case: progress bar
#######################################################################

class ProgressBar:
    """
    A 3-line progress bar, which looks like::
    
                                Header
        20% [===========----------------------------------]
                           progress message

    The progress bar is colored, if the terminal supports color
    output; and adjusts to the width of the terminal.
    """
    BAR = '%3d%% ${GREEN}[${BOLD}%s%s${NORMAL}${GREEN}]${NORMAL}\n'
    HEADER = '${BOLD}${CYAN}%s${NORMAL}\n\n'
        
    def __init__(self, term, header):
        self.term = term
        if not (self.term.CLEAR_EOL and self.term.UP and self.term.BOL):
            raise ValueError("Terminal isn't capable enough -- you "
                             "should use a simpler progress dispaly.")
        self.width = self.term.COLS or 75
        self.bar = term.render(self.BAR)
        self.header = self.term.render(self.HEADER % header.center(self.width))
        self.cleared = 1 #: true if we haven't drawn the bar yet.
        self.update(0, '')

    def update(self, percent, message):
        if self.cleared:
            sys.stdout.write(self.header)
            self.cleared = 0
        n = int((self.width-10)*percent)
        sys.stdout.write(
            self.term.BOL + self.term.UP + self.term.CLEAR_EOL +
            (self.bar % (100*percent, '='*n, '-'*(self.width-10-n))) +
            self.term.CLEAR_EOL + message.center(self.width))

    def clear(self):
        if not self.cleared:
            sys.stdout.write(self.term.BOL + self.term.CLEAR_EOL +
                             self.term.UP + self.term.CLEAR_EOL +
                             self.term.UP + self.term.CLEAR_EOL)
            self.cleared = 1

class PrintManager(object):
    def __init__(self):
        self.instance = "Instance at %d" % self.__hash__()
        self.term = TerminalController()

    def print_warning(self, msg):
        """print message using pink color"""
        print self.msg_yellow('\nWARNING:'), msg

    def print_error(self, msg):
        """print message using red color"""
        print self.msg_red('\nERROR:'), msg

    def print_success(self, msg):
        """print message using green color"""
        print self.msg_green('\nSUCCESS:'), msg

    def print_info(self, msg):
        """print message using green color"""
        print self.msg_green('\nINFO:'), msg

    def print_status(self, msg):
        """print message using blue color"""
        print self.msg_green('\nSTATUS:'), msg

    def print_red(self, msg):
        """print message using red color"""
        print self.msg_red(msg)

    def print_green(self, msg):
        """print message using green color"""
        print self.msg_green(msg)

    def print_blue(self, msg):
        """print message using blue color"""
        print self.msg_blue(msg)

    def msg_red(self, msg):
        """yield message using red color"""
        if  not msg:
            msg = ''
        return self.term.RED + msg + self.term.NORMAL

    def msg_yellow(self, msg):
        """yield message using yellow color"""
        if  not msg:
            msg = ''
        return self.term.YELLOW + msg + self.term.NORMAL

    def msg_green(self, msg):
        """yield message using green color"""
        if  not msg:
            msg = ''
        return self.term.GREEN + msg + self.term.NORMAL

    def msg_blue(self, msg):
        """yield message using blue color"""
        if  not msg:
            msg = ''
#        return self.term.BLUE + msg + self.term.NORMAL
        return self.term.CYAN + msg + self.term.NORMAL

    def print_txt(self, tlist, olist, llist, msg=None):
        """
        Print text in a form of table
        --------------
        title1  title2
        --------------
        val     value
        """
        sss = ""
        for item in llist:
            sss += "-"*(item+2) # add 2 char space for wrap
        print sss
        for idx in xrange(0, len(tlist)):
            title  = tlist[idx]
            length = llist[idx]
            print "%s%s " % (title, " "*abs(length-len(title))),
        print
        print sss
        for item in olist:
            for idx in xrange(0, len(item)):
                elem = str(item[idx])
                length = llist[idx]
                print "%s%s " % (elem, " "*abs(length-len(elem))),
            print
        print sss

    def print_xml(self, tlist, olist, llist, msg=None):
        """Print in XML format"""
        sss  = """<?xml version="1.0" encoding="utf-8"?>\n"""
        sss += "<query>\n"
        sss += "  <sql>%s</sql>\n" % msg
        sss += "  <table>\n"
        for item in olist:
            sss += "    <row>\n"
            for idx in xrange(0, len(item)):
                ttt  = item[idx]
                sss +="      <%s>%s</%s>\n" % (tlist[idx], ttt, tlist[idx])
            sss += "    </row>\n"
        sss += "  </table>\n"
        sss += "</query>\n"
        print sss

    def print_html(self, tlist, olist, llist, msg=None):
        """Print in HTML format"""
        sss  = "<table class=\"dbsh_table\">\n"
        sss += "<th>\n"
        for ttt in tlist:
            sss += "<td>%s</td>\n" % ttt
        sss += "</th>\n"
        for item in olist:
            sss += "<tr>\n"
            for ttt in item:
                sss += "<td>%s</td>\n" % ttt
            sss += "</tr>\n"
        sss += "</table>\n"
        print sss

    def print_cvs(self, tlist, olist, llist, msg=None):
        """Print in CVS format"""
        for ttt in tlist:
            if  ttt != tlist[:-1]:
                print "%s," % ttt,
            else:
                print ttt
        print
        for item in olist:
            for ooo in item:
                if  ooo != olist[:-1]:
                    print "%s," % ooo,
                else:
                    print ooo

PM_SINGLETON = PrintManager()
def print_red(msg):
    """print input message in red color"""
    PM_SINGLETON.print_red(msg)
def print_warning(msg):
    """print warning message"""
    PM_SINGLETON.print_warning(msg)
def print_error(msg):
    """print error message"""
    PM_SINGLETON.print_error(msg)
def print_success(msg):
    """print success message"""
    PM_SINGLETON.print_success(msg)
def print_info(msg):
    """print info message"""
    PM_SINGLETON.print_info(msg)
def print_status(msg):
    """print status message"""
    PM_SINGLETON.print_status(msg)
def msg_red(msg):
    """convert input message into red color"""
    return PM_SINGLETON.msg_red(msg)
def print_blue(msg):
    """print input message in blue color"""
    PM_SINGLETON.print_blue(msg)
def msg_blue(msg):
    """convert input message into blue color"""
    return PM_SINGLETON.msg_blue(msg)
def print_green(msg):
    """print input message in green color"""
    PM_SINGLETON.print_green(msg)
def msg_green(msg):
    """convert input message into green color"""
    return PM_SINGLETON.msg_green(msg)

def format_dict(data):
    msg = ''
    length = 0
    for key in data.keys():
        if  length < len(str(key)):
            length = len(str(key))
    keys = data.keys()
    keys.sort()
    for key in keys:
        val = data[key]
        if  isinstance(val, list):
            if  len(val) and isinstance(val[0], basestring):
                if  len(val) < 5:
                    val = ', '.join(val)
                else:
                    val = '\n'.join(val)
        if  len(str(key)) < length:
            wkey = str(key) + ' '*(length-len(str(key)))
        else:
            wkey = str(key)
        msg += wkey + ': ' + str(val) + '\n'
    return msg

if __name__ == "__main__":
    term = TerminalController()
    print 'This is '+ term.RED + 'green' +term.NORMAL

    mypb = ProgressBar(term, "Test progress")
    #mypb.update(0.1, "doing...")
    for i in range(1, 10):
        mypb.update(i, "doing...")
