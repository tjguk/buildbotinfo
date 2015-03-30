#!python
# -*- coding: utf-8 -*-
"""Provide simple object support for the builders and builds
in a buildbot, using the XMLRPC interface.
"""
import os, sys
import collections
import datetime
import fnmatch
import logging
try:
    # Python 2.x
    import xmlrpclib
    from urlparse import urljoin
    from urllib2 import quote as urlquote
except ImportError:
    # Python 3.x
    import xmlrpc.client as xmlrpclib
    from urllib.parse import quote as urlquote
    from urllib.parse import urljoin

logger = logging.getLogger("buildbot")
logger.setLevel(logging.DEBUG)

class Build(object):

    def __init__(self, builder, **kwargs):
        self.builder = builder
        self.sequence = kwargs.pop("sequence")
        self.url = "%s/builds/%d" % (self.builder.url, self.sequence)
        self._info = kwargs

    def __getattr__(self, attr):
        return self._info[attr]

    def __str__(self):
        return "Build %s at %s on %s" % (self.sequence, self._info.get("started_at"), self.builder)

    def __repr__(self):
        items = self._info.items()
        litems = [("%s = %s" % (k, v)) for (k, v) in self._info.items()]
        return "%s: %s" % (self, ", ".join(litems))

    def __eq__(self, other):
        if other is None: return False
        return self.builder == other.builder and self.sequence == other.sequence

    def __hash__(self):
        return hash((self.builder, self.name))

    def __iter__(self):
        return iter(self._info.items())

class Builder(object):

    def __init__(self, buildbot, name):
        self.name = name
        self.buildbot = buildbot
        self.url = "%s/all/builders/%s" % (self.buildbot.url, urlquote(self.name))

    def __repr__(self):
        return "<%s: %s on %s>" % (self.__class__.__name__, self.name, self.buildbot)

    def __str__(self):
        return self.name

    def __eq__(self, other):
        if other is None: return False
        return self.buildbot == other.buildbot and self.name == other.name

    def __hash__(self):
        return hash((hash(self.buildbot), self.name))

    def last_n_builds(self, n_builds):
        logger.debug("Looking for last %d builds on %s", n_builds, self)
        for build in self.buildbot._proxy.getLastBuilds(self.name, n_builds):
            name, sequence, started_at, finished_at, branch, revision, result, text, reasons = build
            yield Build(
                self,
                name=name, sequence=sequence,
                started_at=datetime.datetime.fromtimestamp(started_at),
                finished_at=datetime.datetime.fromtimestamp(finished_at),
                branch=branch, revision=revision,
                result=result, text=text, reasons=reasons
            )

    def last_build(self):
        for build in self.last_n_builds(1):
            return build

class Buildbot(object):

    def __init__(self, url, repo_url=""):
        self.url = self.name = url.rstrip("/") + "/"
        self.repo_url = repo_url.rstrip("/") + "/"
        self._proxy = xmlrpclib.ServerProxy(self.url + "all/xmlrpc")

    def __repr__(self):
        return "<%s: %s>" % (self.__class__.__name__, self.url)

    def __str__(self):
        return self.url

    def __iter__(self):
        return self.builders()

    def __eq__(self, other):
        if other is None: return False
        return self.name == other.name

    def __hash__(self):
        return hash(self.name)

    def builder(self, name):
        return Builder(self, name)

    def builders(self, pattern="*"):
        logger.debug("Looking for builders matching %s on %s", pattern, self)
        for name in self._proxy.getAllBuilders():
            if fnmatch.fnmatch(name, pattern):
                yield self.builder(name)

if __name__ == "__main__":
    logging.getLogger("buildbot").addHandler(logging.NullHandler())
    for builder in Buildbot('http://buildbot.python.org/'):
        print(builder)

