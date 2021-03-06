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
import os
import random
import string

# Use cryptographic-safe random generator as provided by the OS.
random_generator = random.SystemRandom()


def string_id(length=8):
    """ Generate Random ID.

    Random ID contains ascii letters and digitis.

    Args:
        length (int): Character length of id.

    Returns:
        Random id string.
    """
    return ''.join(random.choice(string.ascii_letters +
                                 string.digits)
                   for _ in range(length))


# Request ID Counter
####################

req_c = None
pid = None


def request_id():
    # Using random is pretty slow. This is way quicker.
    # It uses cached proc id. Then only does this append counter.
    # per request...
    #
    # It may not be as unique, but highly unlikely to collide
    # with recent requet ids.
    global req_c, pid

    if req_c is None:
        req_c = random.randint(1000*1000, 1000*1000*1000)

    if pid is None:
        pid = str(os.getpid())

    req_id = req_c = req_c + 1
    req_id = hex(req_id)[2:].zfill(8)[-8:]

    return pid + '-' + req_id
