#
# fabfile.py -- install SolrCloud with fabric
#

# See the NOTICE file distributed with this work for additional
# information regarding copyright ownership.
#
# LucidWorks, Inc. licenses this file to you under the Apache License,
# Version 2.0 (the "License"); you may not use this file except in
# compliance with the License.  You may obtain a copy of the License at
#
#  http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or
# implied.  See the License for the specific language governing
# permissions and limitations under the License.

from fabric.api import *
from fabric.contrib.files import *
from fabric.contrib.project import *
from sets import Set
from fabric.task_utils import merge
import time, os

# define roles for our cluster: 3 zookeeper nodes and 4 solr nodes
env.roledefs.update({
    'zookeeper': [ 'vm110', 'vm111', 'vm112' ],
    'solr': [ 'vm110', 'vm111', 'vm112', 'vm113' ],
})

# If you have a different username on the nodes, set it here:
#env.user = "ubuntu"

# URLs to download ZooKeeper and Solr from
env.zookeeper_url = 'http://www.mirrorservice.org/sites/ftp.apache.org/zookeeper/zookeeper-3.4.5/zookeeper-3.4.5.tar.gz'
env.solr_url = 'http://www.mirrorservice.org/sites/ftp.apache.org/lucene/solr/4.3.0/solr-4.3.0.tgz'

### You don't need to change anything below here

env.always_use_pty = False
env.forward_agent = True
env.use_ssh_config = True

# Name of the directory on the nodes where we install our components,
# relative to the remote user directory
MY_DIR_NAME = 'solr-fabric'

env.num_shards = 2

# prepare local filenames for distribution
env.zookeeper_tgz = os.path.basename(env.zookeeper_url)
env.solr_tgz = os.path.basename(env.solr_url)

# prepare remote directory names for extracted distributions
env.my_dir_path = os.path.expanduser("/home/{0}/{1}".format(env.user, MY_DIR_NAME))
env.zookeeper_dir = os.path.join(env.my_dir_path, re.sub(r'\.tar\.gz$', '', env.zookeeper_tgz))
env.solr_dir = os.path.join(env.my_dir_path, re.sub(r'\.tgz$', '', env.solr_tgz))

# names for upstart services. Use a prefix to prevent accidentally overwriting a system package
env.zookeeper_service  = 'my_zookeeper'
env.solr_service = 'my_solr'

# create an 'all' role containing all hosts
env.roledefs.update({ 'all': merge([], ['zookeeper', 'solr'], [], env.roledefs) })

env.first_solr = env.roledefs['solr'][0]
env.first_zookeeper = env.roledefs['zookeeper'][0]

# local jinja2 templates directory
TEMPLATES = "./templates"

@roles('all')
def test_ssh():
    """ Run 'hostname' on all hosts, to test ssh. """
    run("hostname")

@roles('all')
def test_ping():
    """ Run 'ping' on all hosts, to test hostname resolution. """
    for host in env.roledefs['all']:
        run("ping -c 1 {0}".format(host))

@roles('all')
def copy_ssh_key(ssh_pub_key = "~/.ssh/id_dsa.pub"):
    """ Append a public key to .ssh/authorized_keys on the nodes, for password-less ssh. """
    ssh_pub_key_path = os.path.expanduser(ssh_pub_key)
    remote = "solr-fabric-key.pem"
    put(ssh_pub_key_path, remote)
    run("mkdir -p ~/.ssh")
    run("cat {0} >> ~/.ssh/authorized_keys".format(remote))
    run("rm {0}".format(remote))

@roles('all')
def setup_sudoers():
    """ Add the user to sudoers, allowing password-less sudo. """
    append("/etc/sudoers", "{0}  ALL=(ALL) NOPASSWD:ALL".format(env.user), use_sudo=True)

@roles('all')
def create_my_dir():
    """ Create a directory on the nodes to hold our ZooKeeper and Solr installs. """
    run("mkdir -p {0}".format(env.my_dir_path))

@roles('all')
def install_oracle_java():
    """ Install Oracle java. """
    # This runs on all the individual nodes. That is a little slow and
    # wasteful, as it does repeated download from Oracle. We could try
    # to download once from Oracle to the laptop, but that adds more
    # complexity and depends on what OS you run on. We could speed
    # things up with a fabric @parallel decorator, but then the output
    # becomes more confusing, which is not ideal for a tutorial.
    # Really, you want to install Java in your VM base image so you
    # can skip all this.
    execute("create_my_dir")
    script = os.path.join(env.my_dir_path, "oracle-java6.sh")
    put("scripts/oracle-java6.sh", script)
    sudo("bash -x {0}".format(script))

@roles('all')
def java_version():
    """ Print the Java version. """
    run("java -version")

def download_zookeeper():
    """ Download ZooKeeper to the local directory. """
    if os.path.exists(env.zookeeper_tgz):
        puts("{0} already exists".format(env.zookeeper_tgz))
        return
    local("wget {0}".format(env.zookeeper_url))

def download_solr():
    """ Download Solr to the local directory. """
    if os.path.exists(env.solr_tgz):
        puts("{0} already exists".format(env.solr_tgz))
        return
    local("wget {0}".format(env.solr_url))

@roles('zookeeper')
def copy_zookeeper():
    """ Upload ZooKeeper to the nodes. """
    put(env.zookeeper_tgz, os.path.join(env.my_dir_path, env.zookeeper_tgz))

@roles('solr')
def copy_solr():
    """ Upload Solr to the nodes. """
    put(env.solr_tgz,  os.path.join(env.my_dir_path, env.solr_tgz))

@roles('zookeeper')
def extract_zookeeper():
    """ Extract ZooKeeper """
    with cd(env.my_dir_path):
        run("tar xf {0}".format(env.zookeeper_tgz))

def configure_zookeeper_id(zk_id):
    """ Write the zookeeper node id to the my_id file. """
    with cd(env.zookeeper_dir):
        run("mkdir -p data")
        run("echo {0} > data/myid".format(zk_id))
        context = { "hosts": env.roledefs['zookeeper'], "path": env.zookeeper_dir }
        upload_template(filename='zoo.cfg', destination='conf/', template_dir=TEMPLATES, context=context, use_jinja=True)

@roles('zookeeper')
def upstart_zookeeper():
    """ Write an Upstart script for ZooKeeper. """
    context = { "user": env.user, "group": env.user, "path": env.zookeeper_dir }
    upload_template(filename='zookeeper-upstart.conf', destination='/etc/init/{0}.conf'.format(env.zookeeper_service),
        template_dir=TEMPLATES, context=context, use_sudo=True, use_jinja=True)

@roles('zookeeper')
def zookeeper_upstart_log():
    """ Tail the Upstart log for ZooKeeper. """
    sudo("tail /var/log/upstart/{0}.log".format(env.zookeeper_service))

@roles('zookeeper')
def check_zookeeper():
    """ Ask ZooKeeper if it is ok, and report its leader/follower mode. """
    out = run("echo ruok | nc localhost 2181")
    if not "imok" in out:
        abort("zookeeper not ok")
    run("echo stat | nc localhost 2181 | grep Mode:")

@hosts(env.first_zookeeper)
def show_zookeeper():
    """ Show zookeeper content. """
    with cd(env.zookeeper_dir):
        run("echo ls / | ./bin/zkCli.sh")
        run("echo ls /live_nodes | ./bin/zkCli.sh")
        run("echo get /overseer | ./bin/zkCli.sh")

def wait_for_zookeeper():
    """ Wait for ZooKeeper to come up and elect a leader. """
    sleep_seconds = 3
    while True:
        complete = True
        for host in env.roledefs['zookeeper']:
            with settings(host_string=host):
                mode = run("echo stat | nc localhost 2181 | grep Mode:", warn_only=True)
            if not ("Mode: follower" in mode or "Mode: leader" in mode):
                complete = False
                break
        if complete:
            puts("got a leader, and all nodes are up")
            return
        else:
            puts("zookeeper cluster not complete yet; sleeping {0} seconds".format(sleep_seconds))
            time.sleep(sleep_seconds)

def configure_zookeeper():
    """ Configure ZooKeeper. """
    zk_id = 0
    for host in env.roledefs['zookeeper']:
        zk_id = zk_id + 1
        execute(configure_zookeeper_id, zk_id, hosts=[host])

@roles('solr')
def extract_solr():
    """ Extract Solr. """
    with cd(env.my_dir_path):
        run("tar xf {0}".format(env.solr_tgz))

def zookeeper_hostports():
    """ Return a comma-separated list of ZooKeeper hostname:port pairs. """
    return ",".join([ "{0}:2181".format(host) for host in env.roledefs['zookeeper'] ])

@hosts(env.first_solr)
def bootstrap_solrcloud():
    """ Bootstrap SolrCloud. """
    # See http://docs.lucidworks.com/display/solr/Command+Line+Utilities
    zkhost = "{0}:2181".format(env.first_zookeeper)
    collection = "collection1"
    conf_set = "configuration1"
    solr_home = "solr"
    with cd(os.path.join(env.solr_dir, "example")):
        # jetty has not run yet, so the webapp has not been extracted; do it here ourselves
        run("mkdir solr-webapp-tmp; (cd solr-webapp-tmp; jar xvf ../webapps/solr.war)")
        zk_cli = "java -classpath solr-webapp-tmp/WEB-INF/lib/*:./lib/ext/* org.apache.solr.cloud.ZkCLI"
        run("{0} -cmd upconfig -zkhost {1} -d solr/{2}/conf/ -n {3}".format(zk_cli, zkhost, collection, conf_set))
        run("{0} -cmd linkconfig -zkhost {1} -collection {2} -confname {3} -solrhome {4}".format(zk_cli, zkhost, collection, conf_set, solr_home))
        run("{0} -cmd bootstrap -zkhost {1} -solrhome {2}".format(zk_cli, zkhost, solr_home))
        run("{0} -cmd upconfig -zkhost {1} -d solr/{2}/conf/ -n {3}".format(zk_cli, zkhost, collection, conf_set))
        run("rm -fr solr-webapp-tmp")

def solrcloud_url():
    """ Print a URL for the Solr Admin interface. """
    puts("http://{0}:8983/solr/#/~cloud".format(env.first_solr))

def wait_for_port(port, max_wait=60, interval=5):
    """ Wait for a TCP port to be listened to. """
    while True:
        started = time.time()
        status = run("netstat --listen --numeric  | grep ':{0} ' || echo no".format(port))
        if status != "no":
            return
        delta = time.time() - started
        if delta > max_wait:
            raise Exception("port {0} still not listening after {1} seconds".format(port, delta))
        time.sleep(interval)

def wait_for_solr():
    """ Wait for Solr nodes to come up. """
    execute('wait_for_solr_ports')
    execute('wait_for_solr_in_zookeeper')
    execute('solr_clusterstate')

@roles('solr')
def wait_for_solr_ports():
    """ Wait for Solr ports to be listened on. """
    status = sudo("service {0} status".format(env.solr_service))
    if "running" not in status:
        abort("solr not running")
    execute('wait_for_port', 8983)

def wait_for_solr_in_zookeeper():
    """ Wait for Solr data to appear in ZooKeeper. """
    sleep_seconds = 3
    # look in zookeeper for the nodes
    while True:
        complete = True
        with(settings(host_string=env.first_zookeeper)):
            with cd(env.zookeeper_dir):
                result = run("echo get /live_nodes | ./bin/zkCli.sh", warn_only=True)
            if not "numChildren = {0}".format(len(env.roledefs['solr'])) in result:
                complete = False
        if complete:
            puts("got all nodes in zookeeper")
            break
        else:
            puts("not complete yet; sleeping {0} seconds".format(sleep_seconds))
            time.sleep(sleep_seconds)

@hosts(env.first_zookeeper)
def solr_clusterstate():
    """ Display cluster state. """
    with cd(env.zookeeper_dir):
        run("echo get /clusterstate.json | ./bin/zkCli.sh", warn_only=True)

@roles('solr')
def upstart_solr():
    """ Write an Upstart script for Solr. """
    context = { "host": env.host, "user": env.user, "group": env.user, "path": os.path.join(env.solr_dir, "example"),
    "num_shards": env.num_shards, "zookeeper_hostports": zookeeper_hostports() }
    upload_template(filename='solr-upstart.conf', destination='/etc/init/{0}.conf'.format(env.solr_service),
        template_dir=TEMPLATES, context=context, use_sudo=True, use_jinja=True)

@roles('zookeeper')
def start_zookeeper():
    """ Start ZooKeeper. """
    sudo("service {0} start".format(env.zookeeper_service))

@roles('zookeeper')
def stop_zookeeper():
    """ Stop ZooKeeper. """
    sudo("service {0} stop".format(env.zookeeper_service))

@roles('solr')
def start_solr():
    """ Start Solr. """
    if not "running" in sudo("service {0} status".format(env.solr_service)):
        sudo("service {0} start".format(env.solr_service))

@roles('solr')
def stop_solr():
    """ Stop Solr. """
    sudo("service {0} stop".format(env.solr_service))

@roles('solr')
def solr_upstart_log():
    """ Tail the Upstart log for Solr. """
    sudo("tail /var/log/upstart/{0}.log".format(env.solr_service))

@roles('solr')
def solr_status():
    """ Report the service status for Solr, and print the Solr cores status. """
    sudo("service {0} status".format(env.solr_service))
    run("wget -O - http://localhost:8983/solr/admin/cores?action=STATUS")


### Below here are top-level tasks

def download():
    """ Download ZooKeeper and Solr. """
    execute('download_zookeeper')
    execute('download_solr')

def install_zookeeper():
    """ Install the ZooKeeper nodes. """
    execute('download_zookeeper')
    execute('copy_zookeeper')
    execute('extract_zookeeper')
    execute('configure_zookeeper')
    execute('upstart_zookeeper')
    execute('start_zookeeper')

def install_solr():
    """ Install the Solr nodes. """
    execute('download_solr')
    execute('copy_solr')
    execute('extract_solr')
    execute('bootstrap_solrcloud')
    execute('upstart_solr')
    execute('start_solr')

def everything():
    """ Do everything. """
    execute('test_ssh')
    execute('copy_ssh_key')
    execute('setup_sudoers')
    execute('create_my_dir')
    execute('install_oracle_java')
    execute('java_version')
    execute('install_solr_and_zookeeper')
    execute('sample_data')
    execute('sample_query')
    execute('display_status')

def install_solr_and_zookeeper():
    """ Install ZooKeeper and Solr. """
    execute('create_my_dir')
    execute('download')
    execute('install_zookeeper')
    execute('wait_for_zookeeper')
    execute('install_solr')
    execute('wait_for_solr')

@hosts(env.first_solr)
def sample_data():
    """ Load the "books" sample data. """
    with cd(os.path.join(env.solr_dir, "example/exampledocs")):
        run("curl -sS 'http://{0}:8983/solr/update/json?commit=true' --data-binary @books.json -H 'Content-type:application/json'".format(env.first_solr))

@hosts(env.first_solr)
def sample_query():
    """ Do a query. """
    local("curl  -sS 'http://{0}:8983/solr/select?q=name:monsters&wt=json&indent=true'".format(env.first_solr))

@hosts(env.first_solr)
def sample_query_all():
    """ Do a query for all documents. """
    local("curl  -sS 'http://{0}:8983/solr/select?q=*:*&wt=json&indent=true'".format(env.first_solr))

@roles('solr')
def sample_query_all_distrib_false():
    """ Do a query for all documents, against each node, with distrib=false. """
    run("curl  -sS 'http://localhost:8983/solr/select?q=*:*&wt=json&indent=true&distrib=false'")

@roles('solr')
def display_status():
    """ Show Solr core status. """
    run("""curl  -sS "http://localhost:8983/solr/admin/cores?action=STATUS&indent=true&wt=json" """)

@roles('zookeeper')
def uninstall_zookeeper_upstart():
    """ Uninstall ZooKeeper Upstart script. """
    sudo("rm -f /etc/init/{0}.conf".format(env.zookeeper_service))

@roles('solr')
def uninstall_solr_upstart():
    """ Uninstall Solr Upstart script. """
    sudo("rm -f /etc/init/{0}.conf".format(env.solr_service))

@roles('all')
def uninstall_mydir():
    """ Remove our directory on the nodes. """
    run("rm -fr {0}".format(env.my_dir_path))

@roles('all')
def uninstall():
    """ Uninstall ZooKeeper and Solr. """
    execute('uninstall_solr_upstart')
    execute('uninstall_zookeeper_upstart')
    execute('uninstall_mydir')
