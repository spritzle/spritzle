#
# spritzle/user.py
#
# Copyright (C) 2016 Andrew Resch <andrewresch@gmail.com>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.    See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.    If not, write to:
#   The Free Software Foundation, Inc.,
#   51 Franklin Street, Fifth Floor
#   Boston, MA    02110-1301, USA.
#

from spritzle import hooks
from bottle import delete, get, post, put

@get('/user')
def get_users(**opts):
    raise NotImplementedError

@post('/user')
def create_user(user, **opts):
    raise NotImplementedError

@delete('/user/<user>')
def delete_user(user, **opts):
    raise NotImplementedError

@get('/user/<user>')
def get_user(user, **opts):
    raise NotImplementedError

@put('/user/<user>')
def update_user(user, **opts):
    raise NotImplementedError
