# -*- coding: utf-8 -*-
# Copyright (c) 2018-2020 Christiaan Frans Rademan <chris@fwiw.co.za>.
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
# * Redistributions of source code must retain the above copyright notice, this
#   list of conditions and the following disclaimer.
#
# * Redistributions in binary form must reproduce the above copyright notice,
#   this list of conditions and the following disclaimer in the documentation
#   and/or other materials provided with the distribution.
#
# * Neither the name of the copyright holders nor the names of its
#   contributors may be used to endorse or promote products derived from
#   this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT HOLDER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF
# THE POSSIBILITY OF SUCH DAMAGE.
import sys
import logging
import logging.handlers
import multiprocessing
import traceback

from luxon import g
from luxon.utils.system import switch
from luxon.core.networking.sock import (Pipe,
                                        recv_pickle,
                                        send_pickle)
from luxon.exceptions import NoContextError
from luxon.utils.singleton import NamedSingleton
from luxon.utils.formatting import format_seconds
from luxon.utils.files import is_socket
from luxon.utils.split import list_of_lines, split_by_n
from luxon.utils.encoding import if_bytes_to_unicode
from luxon.utils.unique import string_id

log_format = logging.Formatter('%(asctime)s %(app_name)s:' +
                               '%(name)s' +
                               '[%(process)d][%(threadName)s]' +
                               ' <%(levelname)s>: %(message)s',
                               datefmt='%b %d %H:%M:%S')

simple_format = logging.Formatter('%(name)s' +
                                  '[%(process)d]' +
                                  ' <%(levelname)s>: %(message)s')


def log_formatted(logger_facility, message, prepend=None, append=None,
                  timer=None, log_id=None):
    """Using logger log formatted content

    Args:
        logger_facility (object): Python logger. (log.debug for example)
        content (str): Message to log.
    """
    try:
        log_items = list(g.current_request.log.items())
        try:
            log_items.append(('REQUEST-ID', g.current_request.id))
        except NotImplementedError:
            pass
        request = " ".join(['(%s: %s)' % (key, value)
                           for (key, value) in log_items])
    except NoContextError:
        request = ''

    message = str(if_bytes_to_unicode(message)).strip()

    if message != '':
        if timer is not None:
            message += ' (DURATION: %s)' % format_seconds(timer)

        _message = list_of_lines(message)
        message = []
        for line in _message:
            # Safe Limit per message...
            # There is resrictions on message sizes.
            # https://tools.ietf.org/html/rfc3164
            # https://tools.ietf.org/html/rfc5426
            message += split_by_n(line, 300)

        if len(message) > 1:
            if log_id is None:
                log_id = string_id(6)

            if prepend is not None:
                logger_facility("(%s) #0 %s" % (log_id, prepend,))

            for line, p in enumerate(message):
                msg = '(%s) %s# %s' % (log_id, line+1, p)
                logger_facility(msg)

            if append is not None:
                logger_facility("(%s) #%s %s" % (log_id, line+2, append))
        else:
            if log_id is not None:
                msg = '(%s) ' % log_id
            else:
                msg = ''
            if prepend is not None:
                msg += '%s %s' % (prepend, message[0])
            else:
                msg += '%s' % message[0]

            if append is not None:
                msg = '%s %s' % (msg, append)

            msg = '%s %s' % (msg, request)

            logger_facility(msg)


class _TachyonFilter(logging.Filter):
    def __init__(self, app_name=None):
        logging.Filter.__init__(self)
        self.app_name = app_name

    def filter(self, record):
        try:
            record.app_name = g.app.config.get('application',
                                               'name',
                                               fallback='').title()
            return True
        except NoContextError:
            pass

        if self.app_name:
            record.app_name = ' ' + self.app_name

        return True


def set_level(logger, level):
        try:
            level = int(level)
            logger.setLevel(level)
        except ValueError:
            level = level.upper().strip()
            if level in ['CRITICAL',
                         'ERROR',
                         'WARNING',
                         'INFO',
                         'DEBUG']:
                logger.setLevel(getattr(logging, level))
            else:
                raise ValueError("Invalid logging level '%s'" % level +
                                 " for logger" +
                                 " '%s'" % logger.name) from None


def configure(config, config_section, logger):
    if (config_section == 'application' and
            config_section not in config):

        # Clean/Remove Handlers
        for handler in logger.handlers:
            logger.removeHandler(handler)

        # DEFAULT Set Stdout
        handler = logging.StreamHandler(stream=sys.stdout)
        handler.addFilter(_TachyonFilter())
        logger.addHandler(handler)
        handler.setFormatter(simple_format)

    if config_section in config:
        # Config Section
        section = config[config_section]

        # Giving out-of-context apps the opportunity to
        # specify a name
        if config_section == 'application' and 'name' in section:
            _tachyonfilter = _TachyonFilter(section['name'])
        else:
            _tachyonfilter = _TachyonFilter()

        # Remove Handlers
        logger.handlers = []

        # Set Logger Level
        level = section.get('log_level')
        if level is not None:
            set_level(logger, level)
        elif config_section == 'application':
            set_level(logger, 'WARNING')

        # Set Stdout
        if section.getboolean('log_stdout', fallback=False):
            handler = logging.StreamHandler(stream=sys.stdout)
            handler.setFormatter(log_format)
            handler.addFilter(_tachyonfilter)
            logger.addHandler(handler)

        # Set Syslog
        host = section.get('log_server', fallback=None)
        if host is not None:
            port = section.get('log_server_port', fallback=514)
            if host == '127.0.0.1' or host.lower() == 'localhost':
                if is_socket('/dev/log'):
                    handler = logging.handlers.SysLogHandler(
                        address='/dev/log')
                elif is_socket('/var/run/syslog'):
                    handler = logging.handlers.SysLogHandler(
                        address='/var/run/syslog')
                else:
                    handler = logging.handlers.SysLogHandler(
                        address=(host, port))
            else:
                handler = logging.handlers.SysLogHandler(address=(host, port))

            handler.setFormatter(log_format)
            handler.addFilter(_tachyonfilter)
            logger.addHandler(handler)

        # ENABLE FILE LOG FOR GLOBAL OR MODULE
        log_file = section.get('log_file', fallback=None)
        if log_file is not None:
            handler = logging.FileHandler(log_file)

            handler.setFormatter(log_format)
            handler.addFilter(_tachyonfilter)
            logger.addHandler(handler)


class MPLoggerSocketQueue(object):
    def __init__(self, sock):
        self._sock = sock

    def get(self):
        return recv_pickle(self._sock)

    def put(self, msg):
        send_pickle(self._sock, msg)

    def put_nowait(self, msg):
        send_pickle(self._sock, msg)

    def flush(self):
        return True


class MPLogger(object):
    # Multiprocessing queues are too slow and limited to 32786.
    # Using Socket Socket Pipe with Queue wrapper interface.
    def __init__(self, name, queue=None):
        self._running = False
        self._log_thread = None
        self._name = name
        self._client = queue
        if self._name == "__main__":
            self._server, self._client = Pipe()
            self._logger = logging.getLogger(name)
        else:
            if not queue:
                raise ValueError('MPLogger for Process requires queue')
            root = logging.getLogger()
            queue = MPLoggerSocketQueue(self._client)
            root.handlers = [logging.handlers.QueueHandler(queue)]

            for logger in logging.Logger.manager.loggerDict:
                sub_logger = logging.Logger.manager.loggerDict[logger]
                if isinstance(sub_logger, logging.Logger):
                    sub_logger.handlers = []

            self._logger = logging.getLogger(name)

    @property
    def queue(self):
        return self._client

    def receive(self):
        def handle(logger, record):
            def log(msg):
                record.msg = msg
                logger.handle(record)

            return log

        def receiver():
            self._running = True

            # Switch from root to daemon user/group
            try:
                user = g.app.config.get('minion', 'user',
                                        fallback=None)
                if user:
                    group = g.app.config.get('minion', 'group',
                                             fallback="tachyonic")
                    switch(user, group)
            except Exception:
                print('MPLogger Whoops! Problem:', file=sys.stderr)
                traceback.print_exc(file=sys.stderr)
                self._running = False

            while self._running:
                try:
                    while self._running:
                        queue = MPLoggerSocketQueue(self._server)
                        record = queue.get()
                        if record is None:
                            break
                        # Get Logger
                        logger = logging.getLogger(record.name)
                        logger_facility = handle(logger, record)
                        logger_facility(record.msg)
                except (KeyboardInterrupt, SystemExit):
                    self._running = False
                except Exception:
                    if self._running is True:
                        print('MPLogger Whoops! Problem:', file=sys.stderr)
                        traceback.print_exc(file=sys.stderr)

        if self._name == "__main__":
            self._log_thread = multiprocessing.Process(
                target=receiver,
                name='Logger',
                daemon=True)
            self._log_thread.start()

    def close(self):
        self._running = False
        self._log_thread.terminate()
        # self._client.close()
        # self._server.close()


class GetLogger(metaclass=NamedSingleton):
    """Wrapper Class for convienance.

    Args:
        name (str): Typical Module Name, sub-logger name, (optional)

    Ensures all log output is formatted correctly.
    """
    __slots__ = ('name',
                 'logger',)

    def __init__(self, name=None):
        self.logger = logging.getLogger(name)

        if not name:
            # DEFAULT Set Stdout
            handler = logging.StreamHandler(stream=sys.stdout)
            handler.addFilter(_TachyonFilter())
            self.logger.addHandler(handler)
            handler.setFormatter(simple_format)

    @property
    def level(self):
        return self.logger.getEffectiveLevel()

    @level.setter
    def level(self, level):
        set_level(self.logger, level)

    def configure(self, config):
        # Configure Root
        configure(config, 'application', logging.getLogger())

        # Configure Sub-Loggers
        for logger in logging.Logger.manager.loggerDict:
            sub_logger = logging.Logger.manager.loggerDict[logger]
            if isinstance(sub_logger, logging.Logger):
                configure(config, logger, sub_logger)

    def critical(self, msg, prepend=None, append=None, timer=None,
                 log_id=None):
        """Log Critical Message.

        Args:
            msg (str): Log Message.
            prepend (str): Prepend Message (optional)
            append (str): Append Message (optional)

            timer (int): Integer value in ms.
                Usually from :class:`luxon.utils.timer.Timer`
                Adds (DURATION: time) to log entry.

        """
        if self.level <= logging.CRITICAL:
            log_formatted(self.logger.critical, msg, prepend, append, timer,
                          log_id)

    def error(self, msg, prepend=None, append=None, timer=None, log_id=None):
        """Log Error Message.

        Args:
            msg (str): Log Message.
            prepend (str): Prepend Message (optional)
            append (str): Append Message (optional)

            timer (int): Integer value in ms.
                Usually from :class:`luxon.utils.timer.Timer`
                Adds (DURATION: time) to log entry.

        """
        if self.level <= logging.ERROR:
            log_formatted(self.logger.error, msg, prepend, append, timer,
                          log_id)

    def warning(self, msg, prepend=None, append=None, timer=None, log_id=None):
        """Log Warning Message.

        Args:
            msg (str): Log Message.
            prepend (str): Prepend Message (optional)
            append (str): Append Message (optional)

            timer (int): Integer value in ms.
                Usually from :class:`luxon.utils.timer.Timer`
                Adds (DURATION: time) to log entry.

        """
        if self.level <= logging.WARNING:
            log_formatted(self.logger.warning, msg, prepend, append, timer,
                          log_id)

    def info(self, msg, prepend=None, append=None, timer=None, log_id=None):
        """Log Info Message.

        Args:
            msg (str): Log Message.
            prepend (str): Prepend Message (optional)
            append (str): Append Message (optional)

            timer (int): Integer value in ms.
                Usually from :class:`luxon.utils.timer.Timer`
                Adds (DURATION: time) to log entry.

        """
        if self.level <= logging.INFO:
            log_formatted(self.logger.info, msg, prepend, append, timer,
                          log_id)

    def debug(self, msg, prepend=None, append=None, timer=None, log_id=None):
        """Log Debug Message.

        Args:
            msg (str): Log Message.
            prepend (str): Prepend Message (optional)
            append (str): Appener value returned using

            timer (int): Integer value in ms.
                Usually from :class:`luxon.utils.timer.Timer`
                Adds (DURATION: time) to log entry.

        """
        if self.level <= logging.DEBUG:
            log_formatted(self.logger.debug, msg, prepend, append, timer,
                          log_id)
