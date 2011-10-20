import IPython.ipapi
import sys, os

ip = IPython.ipapi.get()
LOGNAME = ".ipython_history.log"


def startup_logger(self):
    """ Executed at the ipython startup for loading last saved session
    
    """
    if os.path.exists(LOGNAME):
        p = raw_input("Load last saved session in the current directory ([y]/n)? ")
        if (p.lower() == 'y') or (p == ''):
            ip.magic('run -i -e %s' %LOGNAME)
    return

def shutdown_logger(self):
    """ Prompts for saving the current session during shutdown

    """
    
    p = raw_input("Save current session (y/[n])? ")
    if p.lower() == 'y':
        #ip.magic('logstart %s over' %LOGNAME)
        shell = ip.IP.shell
        logger = shell.logger
        head = shell.loghead_tpl % (LOGNAME, '[]')
        #head = "#saved session in the current directory"
        try:
            started = logger.logstart(logfname=LOGNAME, loghead=head, logmode='append')
        except:
            print("Couldn't save session: %s" % sys.exc_info()[1])
        input_hist = shell.input_hist
        logger.log_write(input_hist[1:])
    return

ip.set_hook('late_startup_hook', startup_logger)    
ip.set_hook('shutdown_hook', shutdown_logger)

