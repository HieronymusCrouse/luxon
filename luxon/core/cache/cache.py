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
from luxon import g
from luxon.utils.imports import get_class
from luxon.utils.singleton import Singleton


class Cache(metaclass=Singleton):
    """Caching class

    Used to globally cache objects using the class specified in the
    *settings.ini* file

    """
    def __init__(self):
        max_objects = g.app.config.getint('cache',
                                          'max_objects',
                                          fallback=2048)
        max_object_size = g.app.config.getint('cache',
                                              'max_object_size',
                                              fallback=50)
        self._cached_backend = get_class(
            g.app.config.get('cache',
                             'backend',
                             fallback="luxon.core.cache:Memory"))(
                             max_objects,
                             max_object_size)

    def store(self, reference, obj, expire=60):
        """Store object

        Args:
            reference (str): reference to object
            obj (obj): object to be cached
            expire (int): time to expire (s)
        """
        if expire > 604800:  # 7 days
            expire = 604800

        self._cached_backend.store(reference, obj, expire)

    def load(self, reference):
        """Returns Cached Object

        Args:
            reference (str): reference to object to be loaded

        Returns:
            object from cache
        """
        return self._cached_backend.load(reference)
