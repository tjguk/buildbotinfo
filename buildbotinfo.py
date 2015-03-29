# -*- coding: utf-8 -*-
#!python3
from __future__ import print_function
import os, sys
import datetime
import logging

from bottle import route, run, template, request, response

import buildbot
buildbot_logger = logging.getLogger("buildbot")
buildbot_logger.addHandler(logging.StreamHandler())

#
# Default params
#
BUILDBOT_URL = "http://buildbot.python.org/"
PATTERN = "*"
ONLY_FAILURES = False
SINCE_MINUTES = None
LATEST_N_BUILDS = 1
OUTPUT_AS = "text"

@route('/')
def index():
    params = request.params
    pattern = params.get("pattern", "*")
    only_failures = bool(int(params.get("only-failures", 0)))
    since_minutes = params.get("since-minutes")

    python_buildbot = buildbot.Buildbot(buildbot_url)
    builders = python_buildbot.builders("*" + pattern + "*")
    builds = []
    for builder in builders:
        print("Looking at", builder)
        latest_build = builder.last_build()
        if latest_build is None:
            print("No build")
            continue
        if only_failures and latest_build.result == "success":
            print("Succeeded; failures only")
            continue
        if latest_build.finished_at < since:
            print("Finished at", latest_build.finished_at, "wanted", since)
            continue
        builds.append(latest_build)

    return template("""
<html>
<head>
<title>Buildbot: {{buildbot}}</title>
</head>
<body>
<h1>{{buildbot}}</h1>
% for build in builds:
<h2>{{build.builder}}</h2>
<h3>{{build.__repr__()}}</h3>
% end
</body>
</html>
    """, buildbot=python_buildbot, builds=builds)

@route("/feed/")
def feed():
    return ""

def with_mimetype(mimetype):
    """Decorate a function which will be yielding lines of text.
    The result returns a tuple of (mimetype, output) where
    output is the yields concatenated with linefeeds.
    """
    def _decorator(function):
        def _with_mimetype(*args, **kwargs):
            return mimetype, function(*args, **kwargs)
        return _with_mimetype
    return _decorator

class Builds(object):
    """Take an iterable of builds (typically from get_builds) and
    allow them to be output in different formats, each with the
    appropriate mimetype
    """

    TIMESTAMP_FORMAT = "%d %b %Y %H:%M"

    def __init__(self, builds):
        #
        # Because of multiple patterns, builds can come in more than
        # once. Use set() to eliminate duplicates and then sort according
        # to Buildbot, builder, and specific build
        #
        self.builds = sorted(
            set(builds),
            key=lambda b: (b.builder.buildbot.name, b.builder.name, -1 * b.sequence)
        )

    def output_as(self, format):
        return getattr(self, "as_" + format)()

    @with_mimetype("text/plain")
    def as_text(self):
        def _lines():
            bb = builder = None
            for build in self.builds:
                if build.builder.buildbot != bb:
                    bb = build.builder.buildbot
                    yield ""
                    yield bb.name
                    yield "=" * len(bb.name)
                    yield ""
                if build.builder != builder:
                    builder = build.builder
                    yield ""
                    yield builder.name
                yield "  [%s] Build %d on branch %s rev %s at %s" % (
                    build.result.upper(),
                    build.sequence, build.branch, build.revision,
                    build.finished_at.strftime(self.TIMESTAMP_FORMAT)
                )
                for stage, result in build.reasons:
                    yield "  %s: %s" % (stage, result)

        return "\n".join(_lines())

def get_builds(buildbot_url, pattern, only_failures, since_minutes, latest_n_builds):
    """Generate the latest build for each builder under `buildbot_url`
    if it matches `pattern`, limiting to failures if requested, and
    only considering results in the last `since_minutes` in an attempt to
    skip dead buildbots
    """
    #
    # A pattern coming from the command line or web interface
    # can be a list of patterns whose results should be combined
    #
    if isinstance(pattern, list):
        patterns = pattern
    else:
        patterns = [pattern]
    print("patterns:", patterns)
    if since_minutes is None:
        since = datetime.datetime.min
    else:
        since = datetime.datetime.now() - datetime.timedelta(minutes=int(since_minutes))
    bb = buildbot.Buildbot(buildbot_url)
    for pattern in patterns:
        builders = bb.builders(pattern)
        print("Looking for builders on %s matching %s since %s" % ( bb, pattern, since))
        for builder in builders:
            for build in builder.last_n_builds(latest_n_builds):
                if build is None:
                    continue
                if only_failures and build.result == "success":
                    continue
                if build.finished_at < since:
                    continue
                yield build

def cli(
    buildbot_url=BUILDBOT_URL,
    pattern=PATTERN,
    only_failures=ONLY_FAILURES,
    since_minutes=SINCE_MINUTES,
    latest_n_builds=LATEST_N_BUILDS,
    output_as="text"
):
    print("pattern:", pattern)
    builds = Builds(get_builds(buildbot_url, pattern, only_failures, since_minutes, latest_n_builds))
    mimetype, output = builds.output_as(output_as)
    print(mimetype)
    print(output)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("Show Buildbot info")
    parser.add_argument("--buildbot-url", dest="buildbot_url", default=BUILDBOT_URL)
    parser.add_argument("--pattern", dest="pattern", nargs="*", default=PATTERN)
    parser.add_argument("--only-failures", type=bool, dest="only_failures", default=ONLY_FAILURES)
    parser.add_argument("--since-minutes", type=int, dest="since_minutes", default=SINCE_MINUTES)
    parser.add_argument("--latest-n-builds", type=int, dest="latest_n_builds", default=LATEST_N_BUILDS)
    parser.add_argument("--output-as", type=str, dest="output_as", default=OUTPUT_AS)
    cli(**vars(parser.parse_args()))

## run(host='localhost', port=8080, debug=True)
