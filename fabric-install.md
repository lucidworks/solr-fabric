Installing Fabric and its dependencies
======================================

Fabric itself takes a little effort to setup, but it's worth it.

The Fabric community is quite active, and we will use the latest version.

We will run Fabric from Python's
[virtualenv](http://www.virtualenv.org/en/latest/), which isolates the installation in a
virtual environment that is easy to remove and re-install.

If you do not already have virtualenv installed, do that first:

#### On Ubuntu

    sudo apt-get install python-virtualenv

and use the (outdated) Ubuntu fabric package to install Fabric's dependencies (such as compiler and python header files required for the crypto library):

    apt-cache depends fabric | grep Depends: | sed 's/^ *Depends: //' | xargs sudo apt-get ---yes install
    sudo apt-get --yes install python-dev


### On OSX

You need a system compiler. If you have a developer.apple.com account you can download and
install the command-line tools separately; if not, download Xcode from the App Store, and install the
"Command Line Tools" component in the Downloads pane in Preferences.

You need a recent Python, pip, and virtual_env.
I strongly recommend [homebrew](http://brew.sh),
so you can install a fresh python and virtualenv with:

    brew install python
    sudo pip install virtualenv

### Installing Fabric

Now we can create a virtualenv to install fabric into:

    VIRTUAL_ENV_DIR=$HOME/fabric
    virtualenv "$VIRTUAL_ENV_DIR"
    source "$VIRTUAL_ENV_DIR/bin/activate"

This will change your bash prompt to include a "(fabric)" prefix.
Whenever you want to run fabric, just re-activate your virtualenv with that source command.

And, finally, we're ready to actually install Fabric:

    pip install fabric jinja2

To verify you can run it, invoke it to print out its versions:

    (fabric)mak@crab$ fab -V
    Fabric 1.5.1
    Paramiko 1.9.0

Yay!
