Spritzle CI
===========

Spritzle uses CircleCI for testing.

Image
=====
We install libtorrent on a docker image that we use in our tests.

Updating Image
==============

** Build
    docker build -t spritzle/cci-python image

** Push
    docker login
    docker push spritzle/cci-python
