''' Script that sends info E-Mails if the data taking stops. Therefore it checks if at least one file of some given files in a specified folder 
is changed in a specified time. If not an alert E-Mail is send. If the data taking work again an info email is send
'''
import time
import os
import string
import smtplib
import logging
import pprint
from datetime import datetime
from threading import Event
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


configuration = {
    "path_to_monitor": 'data/SCC_99',  # the monitor the watchdog checks
    "timeout": 30 * 60,  # the timeout in seconds until an alert email is send (if the data files did not change)
    "timeout_alert": 10,  # the timeout in seconds until the alert status is reset (if the data files did change)
    'data_files': None,  # the files that are monitored for changes
    "check_subfolders": True,  # check also the subfolders of 'path_to_monitor'
    "email_text_alert": 'Sorry, SCC 99 did not collect data within the last 30 min. Usually one GDAC setting takes less than 15. min to collect the desired triggers. Please check ;-)\nSincerely Mr. Beam',  # outgoing mail server
    "email_text_alert_cleared": 'Very nice, I see that the data taking for SCC 99 works again\nSincerely Mr. Beam',  # outgoing mail server
    "email_host": 'mail.gmx.net',  # outgoing mail server
    "email_to": ["pohl@physik.uni-bonn.de", "janssen@physik.uni-bonn.de"],  # the Email adresses the status emails are send to
    "email_account": ['mr_beam@gmx.de', 'pidub123']  # email account name and password used to send email
}


def send_mail(text, subject=''):
    logging.info('send status E-Mail (' + subject + ')')
    body = string.join((
            "From: %s" % configuration['email_account'][0],
            "To: %s" % configuration['email_to'],
            "Subject: %s" % subject,
            "",
            text
            ), "\r\n")
    server = smtplib.SMTP(configuration['email_host'])
    server.login(configuration['email_account'][0], configuration['email_account'][1])
    server.sendmail(configuration['email_account'][0], configuration['email_to'], body)
    server.quit()


class MyHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if configuration['data_files'] is None:
            data_changed.set()
        elif os.path.basename(event.src_path) in configuration['data_files']:
            data_changed.set()

if __name__ == '__main__':
    logging.info('Configuration:\n' + pprint.pformat(configuration))
    timeout = configuration['timeout']
    alert_status = Event()
    data_changed = Event()
    alert_status.clear()
    data_changed.clear()
    observer = Observer()
    observer.schedule(MyHandler(), path=configuration['path_to_monitor'], recursive=configuration['check_subfolders'])
    observer.start()

    try:
        while True:
            time.sleep(timeout)
            if not data_changed.is_set():
                logging.info('data taking BAD')
                if not alert_status.is_set():
                    send_mail(configuration['email_text_alert'], subject='TESTBEAM WARNING')
                    timeout = configuration['timeout_alert']
                    alert_status.set()
            else:
                logging.info('data taking OK')
                if alert_status.is_set():
                    send_mail(configuration['email_text_alert_cleared'], subject='TESTBEAM INFO')
                    timeout = configuration['timeout']
                    alert_status.clear()
            data_changed.clear()
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
