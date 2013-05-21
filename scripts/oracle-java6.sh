#!/bin/bash
#
# Install Oracle Java6 on Ubuntu
# Based on http://www.webupd8.org/2012/01/install-oracle-java-jdk-7-in-ubuntu-via.html

set -e

function install_oracle_java() {
    export DEBIAN_FRONTEND=noninteractive

    apt-get --yes purge openjdk*

    which add-apt-repository || apt-get --yes install python-software-properties software-properties-common

    # to skip the license screen:
    /usr/bin/debconf-set-selections <<EOM
debconf shared/accepted-oracle-license-v1-1 select true
debconf shared/accepted-oracle-license-v1-1 seen true
EOM

    add-apt-repository --yes ppa:webupd8team/java
    apt-get update
    apt-get --yes install oracle-java6-installer
}

function set_java_home() {

    # determine JAVA_HOME
    JAVA_HOME=`readlink /etc/alternatives/java | sed 's/\/bin\/java$//'`

    # add to /etc/environment
    if ! grep -q JAVA_HOME /etc/environment ; then
      bash -c "echo JAVA_HOME=$JAVA_HOME >> /etc/environment"
    fi

    if ! grep -q 'env_keep+=JAVA_HOME' /etc/sudoers; then
      ed /etc/sudoers <<EOM
/env_reset
a
Defaults    env_keep+=JAVA_HOME
.
w
q
EOM
    fi

    # we do not need to add the JAVA_HOME to the sudoers path because
    # we use /usr/bin/java
}

our_java=`which java||true`
if [ "x$our_java" = "x" ]; then
    install_oracle_java
else
    echo "our_java=$our_java"
    if [ -x $our_java ]; then
        file=`readlink -f $our_java`
        if echo "$file" | grep oracle ; then
            echo looks like you already have oracle java in $file
        else
            echo "not oracle java but $file"
            install_oracle_java
        fi
    else
        echo "no java"
        install_oracle_java
    fi
fi

set_java_home