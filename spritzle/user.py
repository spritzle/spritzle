#
# spritzle/user.py
#
# Copyright (C) 2011 Andrew Resch <andrewresch@gmail.com>
#               2011 Damien Churchill <damoxc@gmail.com>
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
from spritzle.rest import delete, get, post, put

@get('/user')
def users_view(**opts):
    print opts
    return [
        {'username': 'damoxc'},
        {'username': 'andar'},
        {'username': 'johnnyg'}
    ]

@post('/user')
def create_user(user, **opts):
    return data

@delete('/user/:user')
def delete_user(**opts):
    return 'This is delete user'

@get('/user/:user')
def fetch_user(**opts):
    return {'username': 'damoxc'}

@put('/user/:user')
def update_user(user, **opts):
    return 'This is update user'
