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

from bottle import delete, get, post, put, response, request

@get('/user')
def users():
    return 'This is get user'

@post('/user')
def create_user():
    return 'This is create user'

@delete('/user/:user')
def delete_user(user):
    return 'This is delete user'

@get('/user/:user')
def fetch_user(user):
    return 'This is fetch user'

@put('/user/:user')
def update_user(user):
    return 'This is update user'
