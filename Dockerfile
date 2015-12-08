FROM stackbrew/ubuntu:14.04
MAINTAINER Brad Chapman "https://github.com/chapmanb"

# Release 0.9.5a -- https://github.com/chapmanb/bcbio-nextgen/commit/40fb5ba

# Setup a base system 
RUN apt-get update && apt-get install -y build-essential zlib1g-dev wget curl python-setuptools git && \
    apt-get install -y openjdk-7-jdk openjdk-7-jre ruby libncurses5-dev libcurl4-openssl-dev libbz2-dev \
    unzip pigz bsdmainutils && \

# Fake a fuse install; openjdk pulls this in 
# https://github.com/dotcloud/docker/issues/514
# https://gist.github.com/henrik-muehe/6155333
    mkdir -p /tmp/fuse-hack && cd /tmp/fuse-hack && \
    apt-get install libfuse2 && \
    apt-get download fuse && \
    dpkg-deb -x fuse_* . && \
    dpkg-deb -e fuse_* && \
    rm fuse_*.deb && \
    echo -en '#!/bin/bash\nexit 0\n' > DEBIAN/postinst && \
    dpkg-deb -b . /fuse.deb && \
    dpkg -i /fuse.deb && \
    rm -rf /tmp/fuse-hack && \

# bcbio-nextgen installation
    mkdir -p /tmp/bcbio-nextgen-install && cd /tmp/bcbio-nextgen-install && \
    wget --no-check-certificate \
      https://raw.github.com/chapmanb/bcbio-nextgen/master/scripts/bcbio_nextgen_install.py && \
    python bcbio_nextgen_install.py /usr/local/share/bcbio-nextgen \
      --nodata -u development && \
    git config --global url.https://github.com/.insteadOf git://github.com/ && \
    /usr/local/share/bcbio-nextgen/anaconda/bin/bcbio_nextgen.py upgrade --sudo --tooldir=/usr/local --tools && \
    /usr/local/share/bcbio-nextgen/anaconda/bin/bcbio_nextgen.py upgrade --isolate -u development --tools --toolplus data  && \

# setup paths
    echo 'export PATH=/usr/local/bin:$PATH' >> /etc/profile.d/bcbio.sh && \

# add user run script
    wget --no-check-certificate -O createsetuser \
      https://raw.github.com/chapmanb/bcbio-nextgen-vm/master/scripts/createsetuser && \
    chmod a+x createsetuser && mv createsetuser /sbin && \

# clean filesystem
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* /var/tmp/* && \
    /usr/local/share/bcbio-nextgen/anaconda/bin/conda remove --yes qt && \
    /usr/local/share/bcbio-nextgen/anaconda/bin/conda clean --yes --tarballs && \
    rm -rf /usr/local/share/bcbio-nextgen/anaconda/pkgs/qt* && \
    rm -rf $(brew --cache) && \
    rm -rf /usr/local/.git && \
    rm -rf /.cpanm && \
    rm -rf /tmp/bcbio-nextgen-install && \

# Create directories and symlinks for data 
    mkdir -p /mnt/biodata && \
    mkdir -p /tmp/bcbio-nextgen && \
    mv /usr/local/share/bcbio-nextgen/galaxy/bcbio_system.yaml /usr/local/share/bcbio-nextgen/config && \
    rmdir /usr/local/share/bcbio-nextgen/galaxy && \
    ln -s /mnt/biodata/galaxy /usr/local/share/bcbio-nextgen/galaxy && \
    ln -s /mnt/biodata/gemini_data /usr/local/share/bcbio-nextgen/gemini_data && \
    ln -s /mnt/biodata/genomes /usr/local/share/bcbio-nextgen/genomes && \
    ln -s /mnt/biodata/liftOver /usr/local/share/bcbio-nextgen/liftOver && \
    chmod a+rwx /usr/local/share/bcbio-nextgen && \
    chmod a+rwx /usr/local/share/bcbio-nextgen/config && \
    chmod a+rwx /usr/local/share/bcbio-nextgen/config/*.yaml && \
    chmod a+rwx /usr/local/share/bcbio-nextgen/gemini-config.yaml && \

# Ensure permissions are set for update in place by arbitrary users
    find /usr/local -perm /u+x -execdir chmod a+x {} \; && \
    find /usr/local -perm /u+w -execdir chmod a+w {} \;
