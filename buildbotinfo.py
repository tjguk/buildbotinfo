# -*- coding: utf-8 -*-
#!python3
from __future__ import print_function
import os, sys
import datetime
import json
import logging

from bottle import route, run, template, request, response

import buildbot
buildbot_logger = logging.getLogger("buildbot")
buildbot_logger.addHandler(logging.StreamHandler())

#
# Default params
#
BUILDBOT_URL = "http://buildbot.python.org/"
REPO_URL = "http://hg.python.org/cpython/"
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
        latest_build = builder.last_build()
        if latest_build is None:
            continue
        if only_failures and latest_build.result == "success":
            continue
        if latest_build.finished_at < since:
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

def as_code(name, separator="-"):
    return separator.join(name.lower().split())

def jsonify(obj):
    if isinstance(obj, datetime.datetime):
        return obj.isoformat()
    else:
        return obj

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

    @with_mimetype("application/json")
    def as_json(self):
        return json.dumps(
            [(b.builder.buildbot.name, b.builder.name, b.sequence, dict(b)) for b in self.builds],
            default=jsonify
        )

    @with_mimetype("text/html")
    def as_html(self):
        def _lines():
            yield "<!DOCTYPE html>"
            yield "<meta charset=utf-8>"
            yield "<html>"
            yield "<head>"
            yield "<title>Buildbot Info</title>"
            yield """<style>
body {font-family : Tahoma, Helvetica, sans-serif;}
.outcome {font-variant : small-caps; font-weight : bold;}
.success {background-color : green; color : white;}
.failure {background-color : red; color : white;}
li.build {padding-bottom : 0.333em;}
</style>
            """
            yield "</head>"
            yield "<body>"

            bb = builder = None
            for build in self.builds:
                if build.builder.buildbot != bb:
                    bb = build.builder.buildbot
                    yield "<h1>Builds for %s</h1>" % bb.name
                if build.builder != builder:
                    if builder is not None:
                        yield "</ul>"
                        yield "</div>"
                    builder = build.builder
                    yield '<div class="builder" id="%s">' % (as_code(builder.name))
                    yield '<h2><a href="%s">%s</a></h2>' % (builder.url, builder.name)
                    yield "<ul>"
                yield '<li class="build"><span class="outcome %s">%s</span> <a href="%s">Build %d</a> on branch %s <a href="%s">rev %s</a> at %s<br></li>' % (
                    build.result.lower(),
                    build.result.upper(),
                    build.url, build.sequence,
                    build.branch,
                    (build.builder.buildbot.repo_url + "/rev/" + build.revision) if build.builder.buildbot.repo_url else "#", build.revision,
                    build.finished_at.strftime(self.TIMESTAMP_FORMAT)
                )

            if builder is not None:
                yield "</ul>"
                yield "</div>"
            yield "</body>"
            yield "</html>"

        return "\n".join(_lines())

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

        return "\n".join(_lines())

def get_builds(buildbot_url, repo_url, pattern, only_failures, since_minutes, latest_n_builds):
    """Generate the `latest_n_builds` for each builder under `buildbot_url`
    if it matches `pattern`, limiting to failures if requested, and
    only considering results in the last `since_minutes` in an attempt to
    skip dead buildbots.

    It is assumed that the parameters have already been converted from their
    web or command-line versions to they now contain their expected datatypes.
    """
    #
    # A pattern coming from the command line or web interface
    # can be a list of patterns whose results should be combined
    #
    if isinstance(pattern, list):
        patterns = pattern
    else:
        patterns = [pattern]
    if since_minutes is None:
        since = datetime.datetime.min
    else:
        since = datetime.datetime.now() - datetime.timedelta(minutes=int(since_minutes))
    bb = buildbot.Buildbot(buildbot_url, repo_url)
    for pattern in patterns:
        builders = bb.builders(pattern)
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
    repo_url=REPO_URL,
    pattern=PATTERN,
    only_failures=ONLY_FAILURES,
    since_minutes=SINCE_MINUTES,
    latest_n_builds=LATEST_N_BUILDS,
    output_as="text"
):
    builds = Builds(get_builds(buildbot_url, repo_url, pattern, only_failures, since_minutes, latest_n_builds))
    mimetype, output = builds.output_as(output_as)
    print(output)

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser("Show Buildbot info")
    parser.add_argument("--buildbot-url", dest="buildbot_url", default=BUILDBOT_URL)
    parser.add_argument("--repo-url", dest="repo_url", default=REPO_URL)
    parser.add_argument("--pattern", dest="pattern", nargs="*", default=PATTERN)
    parser.add_argument("--only-failures", type=bool, dest="only_failures", default=ONLY_FAILURES)
    parser.add_argument("--since-minutes", type=int, dest="since_minutes", default=SINCE_MINUTES)
    parser.add_argument("--latest-n-builds", type=int, dest="latest_n_builds", default=LATEST_N_BUILDS)
    parser.add_argument("--output-as", type=str, dest="output_as", default=OUTPUT_AS)
    cli(**vars(parser.parse_args()))

## run(host='localhost', port=8080, debug=True)
