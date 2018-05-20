Spritzle CI
===========

Spritzle uses CircleCI for testing.

Image
=====
We install libtorrent on a docker image that we use in our tests.

Updating Image
==============

Build
-------
    docker build -t spritzle/cci-python image

Push
-------
    docker login
    docker push spritzle/cci-python
    
Running CircleCI Locally
====================

Install the circleci application as described here: https://circleci.com/docs/2.0/local-cli/

Run
-----
    circleci build .circleci/config.yml
