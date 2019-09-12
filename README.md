![Home page](home.png)
![Results page](results.png)

Simple website search using flask/xapian. Originally I was going to use
OpenSemanticSearch, but I found it far too difficult to get working on armbian,
so I settled on simple text search instead.

This is intended to be the search engine for my personal archive, but it might
be a good fit for internet-in-a-box as well.

We use xapian as our search engine, and huey with the sqlite backend as a
task-queue, although it could also use redis.

In addition to the (portable) dependencies listed in the `requirements.txt`
file, you'll also need a copy of python-xapian from your package manager.

Aims to be extensable so that other people can package internet-in-a-box
services as easy to install pip packages, although of course a lot of
internet-in-a-box services are complicated third-party webapps, that should work
fine for simple python based services.

It's highly recomended to use this with a file system that supports in-line
compression, for example btrfs. There are various points in this system where I
*could* have enabled compression, and gotten some pretty good gains, but I made
the choice to push that down to the filesystem layer as that allows for better
customization of speed/performance tradeoffs. BTRFS's `zstd` support is quite a
bit faster than python's zlib, and I don't want to be supporting a bunch of
different compression options.
