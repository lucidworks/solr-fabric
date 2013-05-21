
Installing Distributed Solr 4 with Fabric
=========================================

_The latest version of this document is on
[github.com/lucidimagination/solr-fabric](https://github.com/lucidimagination/solr-fabric/)_

Solr 4 has a subset of features that allow it be run as a distributed
fault-tolerant cluster, referred to as "SolrCloud". Installing and
configuring Solr on a multi-node cluster can seem daunting when you're
a developer who just wants to give the latest release a try. The [wiki
page](http://wiki.apache.org/solr/SolrCloud) is long and complex, and
configuring nodes manually is laborious and error-prone. And while
your OS has ZooKeeper/Solr packages, they are probably outdated. But
it doesn't have to be a lot of work: in this post I will show you how
to deploy and test a Solr 4 cluster using just a few commands, using
mechanisms you can easily adjust for your own deployments.

I am using a cluster consisting of a virtual machines running Ubuntu
12.04 64bit and I am controlling them from my MacBook Pro. The Solr
configuration will mimic the [Two shard cluster with shard replicas
and zookeeper ensemble](http://wiki.apache.org/solr/SolrCloud#Example_C:_Two_shard_cluster_with_shard_replicas_and_zookeeper_ensemble)
example from the wiki.

You can run this on AWS EC2, but some special considerations apply,
see the footnote.

We'll use [Fabric](http://www.fabfile.org/), a light-weight deployment
tool that is basically a Python library to easily execute commands on
remote nodes over ssh. Compared to Chef/Puppet it is simpler to learn
and use, and because it's an imperative approach it makes sequential
orchestration of dependencies more explicit. Most importantly, it does
not require a separate server or separate node-side software
installation.

DISCLAIMER: these instructions and associated scripts are released
under the [Apache
License](http://www.apache.org/licenses/LICENSE-2.0.txt); use at your
own risk.

I strongly recommend you use disposable virtual machines to experiment
with.


Getting Started
---------------

First, if you've not already got Fabric installed, follow [these
Fabric installation instructions](./fabric-install.md).

To make things easier, I've prepared [a small
repository](https://github.com/makuk66/solr-fabric) with example
config and scripts. Download that first:

    git clone https://github.com/lucidimagination/solr-fabric
    cd solr-fabric

The main script here is the [fabfile.py](./fabfile.py). Open this with
an editor, and edit the host definition to replace the hostname
configuration with your own hostnames:

    env.roledefs.update({
        'zookeeper': [ 'vm110', 'vm111', 'vm112' ],
        'solr': [ 'vm110', 'vm111', 'vm112', 'vm113' ],
    })


These hostnames need to be resolvable from the system running fabric,
and the remote nodes themselves. In this example I run the ZooKeeper
cluster and the Solr cluster on the same machines, but you can
use different machines if you like. You do need different machines for
each of the nodes in the ZooKeeper and Solr cluster though.

The [fabfile.py](./fabfile.py) contains various Python methods that
represent tasks that will get executed on the remote nodes. It is easy
to read, so do refer to the code as you run these commands to see what
they do behind the scenes.

The target nodes are fresh Ubuntu 12.04 installations; dependencies
will get installed as we go along.

To test your configuration, run:

    fab test_ssh

which executes a simple "hostname" command on all your nodes. Next,
test you can ping all the machines in your roles from all nodes:

    fab test_ping

If that works, you should be good to go.

To stop fabric prompting for passwords, you want to use password-less
ssh. You can do that manually if you prefer, or use this task (adjust
the location of your desired public key):

    fab copy_ssh_key:ssh_pub_key=~/.ssh/id_dsa.pub

After this, a `fab test_ssh` should work without prompting for
passwords.

Note that the scripts here will run some commands as root:

- to install Java and other dependencies with apt
- to install Ubuntu Upstart scripts in /etc/init/ and invoke them

Fabric will prompt for the root password. If you prefer to use
passwordless sudo, run:

    fab setup_sudoers

By the way, if you want to run some random command on all nodes,
you can do it like this:

    fab --roles all -- ps -efl


Installing Java
---------------

Solr requires Java. If you already have that installed in your VMs
(you should!), skip this section.

We recommend the latest Oracle Java. Installing that on Ubuntu is a
bit of pain, because you have to manually accept the Oracle licensing.
Here we see how scripting with fabric is a help:

    fab install_oracle_java
    fab java_version

That first command installs java on all your nodes, dealing with the
licensing accepting on your behalf, and that second command prints the
java version on all nodes so you can verify it worked. That was easy,
right?


Downloading ZooKeeper and Solr
------------------------------

Download the ZooKeeper and Solr distributions to your local computer:

    fab download


Installing ZooKeeper
--------------------

Next, install zookeeper:

    fab install_zookeeper
    fab wait_for_zookeeper

This uploads the ZooKeeper distribution file to your nodes, configures
each of the nodes, starts them up, and waits for the cluster to elect
a leader.


Installing Solr
---------------

And then, install Solr:

    fab install_solr
    fab wait_for_solr

This uploads the Solr distribution file to your nodes, configures each
of the nodes, starts them up, and waits for the cluster to become
ready.

You can inspect the Solr Admin user interface on e.g.
[http://vm110.lan:8983/solr/#/~cloud](http://vm110.lan:8983/solr/#/~cloud)
(adjust for your hostname)


Loading data
------------

We'll load the Solr exampledocs/books.json data, which defines 4
documents:

    (fabric)mak@crab$ fab sample_data
    [vm110] Executing task 'sample_data'
    [vm110] run: curl -sS 'http://vm110:8983/solr/update/json?commit=true' --data-binary @books.json -H 'Content-type:application/json'
    [vm110] out: {"responseHeader":{"status":0,"QTime":175}}
    [vm110] out: 


    Done.
    Disconnecting from vm110... done.

 query it for the word "monsters", which finds one match:

    (fabric)mak@crab$ $ fab sample_query 
    [vm110] Executing task 'sample_query'
    [localhost] local: curl  -sS 'http://vm110:8983/solr/select?q=name:monsters&wt=json&indent=true'
    {
      "responseHeader":{
        "status":0,
        "QTime":2,
        "params":{
          "indent":"true",
          "q":"name:monsters",
          "wt":"json"}},
      "response":{"numFound":1,"start":0,"docs":[
          {
            "id":"978-1423103349",
            "cat":["book",
              "paperback"],
            "name":"The Sea of Monsters",
            "author":"Rick Riordan",
            "author_s":"Rick Riordan",
            "series_t":"Percy Jackson and the Olympians",
            "sequence_i":2,
            "genre_s":"fantasy",
            "inStock":true,
            "price":6.49,
            "price_c":"6.49,USD",
            "pages_i":304,
            "_version_":1434957795244900352}]
      }}

    Done.

and `fab sample_query_all` returns all docs.

You can display status of each of the cores with:

    fab display_status


Removing It all
---------------
To remove the installation from the remote machines:

    fab stop_solr
    fab stop_zookeeper
    fab uninstall

And if you want to remove your Fabric install locally:

    rm -fr $HOME/fabric


Next Steps
----------

I hope this post has inspired you to try out SolrCloud, and has made
you appreciate the power of Fabric for automating remote
administration. You can use this approach for trying out new features
in Solr, do nightly automated testing from your CI systems, or to
get familiar with Solr deployments prior to planning your production
deployment.

For production use there are many other considerations that this
fabfile does not address:

- you may not want installs in a home directory, and you won't want to run out of the example directory
- your ZooKeeper nodes will want a special configuration for disk layout, log management and memory. See the [ZooKeeper Administrator's Guide](http://zookeeper.apache.org/doc/r3.3.3/zookeeperAdmin.html). And you probably want to run them on separate hosts.
- similar considerations apply to Solr. See the [Apache Solr Reference Guide](http://docs.lucidworks.com/display/solr/Apache+Solr+Reference+Guide) recently [donated](https://issues.apache.org/jira/browse/SOLR-4618) by LucidWorks.
- you need to consider your collections and sharding
- you need to consider host-based firewall rules: open ports such that Solr nodes can communicate with eachother and ZooKeeper, and ZooKeeper can communicate between its nodes.
- you need to consider integration in your Ops team monitoring and alerting
- you need to consider nodes leaving/joining the cluster

etc.


Footnotes
---------

### EC2 Considerations

You can run this on AWS EC2, but note:

- You must create security groups such that the ZooKeeper nodes can talk TCP to each other on ports 2181/2888/3888, Solr nodes can talk to ZooKeeper on 2181, and Solr nodes can talk to each other on 8983. And allow TCP port 22 (ssh) access to all nodes from your IP address.
- Solr registers its nodes by IP address, which change when you stop/start your instances. You can avoid this by using a VPC. See also [SOLR-4078](https://issues.apache.org/jira/browse/SOLR-4078).
- You won't have a password to login, instead you will use your keypair. Use `ssh-add` to add the key to your ssh agent, or configure your ~/.ssh/config to contain Host entries for your instances and specify the key there. You can skip the `fab copy_ssh_key` step.
- Make sure you configure your hosts' domain name in the roledefs, not the public IP address.
