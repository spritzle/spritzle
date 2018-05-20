FROM circleci/python

RUN sudo apt-get update && sudo apt-get install build-essential checkinstall libboost-system-dev libboost-python-dev libboost-chrono-dev libboost-random-dev libssl-dev
RUN sudo git clone https://github.com/arvidn/libtorrent.git
RUN cd libtorrent && sudo ./autotool.sh && sudo ./configure --libdir=/usr/lib --enable-python-binding --disable-static --with-libiconv --with-boost-python=boost_python3 --disable-deprecated-functions && sudo make && sudo make install

