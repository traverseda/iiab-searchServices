![Home page](home.png)
![Results page](results.png)

Simple website search using flask/whoosh. Originally I was going to use
OpenSemanticSearch, but I found it far too difficult to get working on armbian,
so I settled on simple text search instead.

This is intended to be the search engine for my personal archive, but it might
be a good fit for internet-in-a-box as well.

# Goals

 * Simple to set up, no need for docker, no dependencies on other services
 * Avoid duplicating data (data retrieval needs to be fast for snippets to work
     without caching)
 * Return results in under 0.6 seconds
 * Works on low-ish power/memory systems like the raspberry PI (or worse)
 * JSON(rest-ish) API
 * Expose CLI commands for all API endpoints
 * Support clustering to minimize load on embedded devices
 * Extract data from many different types of files

We use whoosh as our search engine, and huey with the sqlite backend as a
task-queue, although it could also use redis for distributed crawling.

# Compression

It's highly recomended to use this with a file system that supports in-line
compression, for example btrfs. There are various points in this system where I
*could* have enabled compression, and gotten some pretty good gains, but I made
the choice to push that down to the filesystem layer as that allows for better
customization of speed/performance tradeoffs. BTRFS's `zstd` support is quite a
bit faster than python's zlib, and I don't want to be supporting a bunch of
different compression options.

# Alternatives

There are some more mature alternatives for intranet search that you might want
to investigate. For the most part these will have better performance but also
have higher system requirments.

 * Yacy, the "peer to peer" serach engine. I found this returned much better
     results on limited intranet datasets than on the general internet. You can
     set it as an intranet search without connecting to the peer to peer
     network. Very simple to deploy. Probably the one I'd recomend the most,
     although the results page is a bit ugly.

 * OpenSemanticSearch, very powerful but hard to set up. Has facilities for
     structured data and named-entity-recognition, so it can be quite a bit more
     powerful than google for highly-linked data sets that don't use actual
     hyperlinks. Thinks like research papers or corporate ledgers. Great for
     indexing the kinds of content google traditionaly does poorly with.

 * sist2, designed for very large multimedia collections. Very fast indexing,
     but you need to feed it files not web pages. Created for the-eye-dot-eu, a
     large public archive of mostly pdfs and epubs.

# Performance

Python whoosh seems to perform a bit slower that xapian at retrieval, but
indexes a fair bit faster.

# Technology

We use the "whoosh" search engine because it's reasonably responive, doesn't
take a huge amount of memory, it's easy to deploy, and it's easier to work with
than other libraries like xapian. In order to meet our goals we need a search
engine *library*, not a server/service, which makes a lot of search backend
inaccesable.

We use textract to extract text from more complicated dataformats, you can
see how that works
[here](https://textract.readthedocs.io/en/stable/#currently-supporting).

# Usage

I will try to be pretty resonsive, so if you have any questions feel free to
open an issue, it's not just for bug/feature-requests.

If you're writing a new app you can integrate with the api to update indexes.
Otherwise you probably want to use things like cron (timers) and incron (run
command when files change) and the command line interface.
