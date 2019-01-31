FROM base/archlinux

RUN pacman -Sy --noconfirm pacman-contrib
RUN curl -s "https://www.archlinux.org/mirrorlist/?country=US&protocol=https&use_mirror_status=on" | sed -e 's/^#Server/Server/' -e '/^#/d' | rankmirrors -n 5 -
RUN pacman -Sy --noconfirm git cmake boost base-devel python python-setuptools
RUN curl -sSL https://raw.githubusercontent.com/sdispater/poetry/master/get-poetry.py | python
RUN git clone https://github.com/arvidn/libtorrent.git
RUN cd libtorrent && \
     git checkout RC_1_2 && \
     git submodule init && \
     git submodule update && \
    cd .. && \
     mkdir build && \
    cd build && \
     cmake \
        -DCMAKE_BUILD_TYPE=Release \
        -DCMAKE_INSTALL_PREFIX="/usr" \
        -DCMAKE_INSTALL_LIBDIR="lib" \
        -Ddeprecated-functions=OFF \
        -Dpython-bindings=ON \
        -DPYTHON_EXECUTABLE="/usr/bin/python3" \
        "../libtorrent" && \
     make && \
     make install
