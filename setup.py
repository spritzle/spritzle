#!/usr/bin/env python
#
# setup.py
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

from setuptools import setup

setup(
    name='spritzle',
    version='0.1',
    fullname='Spritzle Bittorrent Client',
    description='Lightweight Bitorrent Client',
    author='Andrew Resch',
    author_email='andrewresch@gmail.com',
    keywords='torrent bittorrent p2p fileshare filesharing',
    url='http://github.com/damoxc/spritzle',
    license='GPLv3',
    packages=['spritzle', 'spritzle.resource'],
    entry_points={
        'console_scripts': [
            'spritzled =  spritzle.main:main'
        ]
    }
)
