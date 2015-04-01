# -*- coding: utf-8 -*-
#!python3
from __future__ import print_function
import os, sys
import datetime
import json
import logging
import smtplib
try:
    from email.Message import Message
    from email.MIMEBase import MIMEBase
    from email.MIMEMultipart import MIMEMultipart
    from email.MIMEText import MIMEText
except ImportError:
    from email.message import Message
    from email.mime.base import MIMEBase
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

import buildbotlib

#
# Default params
#
BUILDBOT_URL = "http://buildbot.python.org/"
REPO_URL = "http://hg.python.org/cpython/"
PATTERN = "*"
ALWAYS_STATUS = None
SINCE_MINUTES = None
LATEST_N_BUILDS = 1
OUTPUT_AS = "text"
FOR_EMAIL = False

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
.exception {background-color : darkred; color : white;}
.retry {background-color : orange; color : white;}
li.build {padding-bottom : 0.333em;}
</style>
            """
            yield "</head>"
            yield "<body>"

            bb = builder = None
            for build in self.builds:
                if build.builder.buildbot != bb:
                    bb = build.builder.buildbot
                    yield '<h1>Builds for <a href="{url}">{url}</a> against <a href="{repo_url}">{repo_url}</a></h1>'.format(url=bb.url, repo_url=bb.repo_url)
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

def get_builds(buildbot_url, repo_url, pattern, always_status, since_minutes, latest_n_builds):
    """Generate the `latest_n_builds` for each builder under `buildbot_url`
    if it matches `pattern`, limiting to failures if requested, and
    only considering results in the last `since_minutes` in an attempt to
    skip dead buildbots.

    It is assumed that the parameters have already been converted from their
    web or command-line versions to they now contain their expected datatypes.
    """
    #
    # A pattern or a status coming from the command line or web interface
    # can be a list whose results should be combined
    #
    patterns = pattern if isinstance(pattern, list) else [pattern]
    if always_status is None:
        always_status = []
    elif not isinstance(always_status, list):
        always_status = [always_status]
    always_statuses = set(a.lower() for a in always_status)
    if since_minutes is None:
        since = datetime.datetime.min
    else:
        since = datetime.datetime.now() - datetime.timedelta(minutes=int(since_minutes))

    bb = buildbotlib.Buildbot(buildbot_url, repo_url)
    for pattern in patterns:
        builders = bb.builders(pattern)
        for builder in builders:
            builds = []
            for build in builder.last_n_builds(latest_n_builds):
                if build is None:
                    continue
                if build.finished_at < since:
                    continue
                builds.append(build)

            #
            # If a set of "always status" has been specified, then only return the builds
            # if the status for all of them matches at least one of the set.
            # This would most commonly be used for checking long-term red buildbots
            # (including FAIL, EXCEPTION and perhaps RETRY)
            #
            if always_statuses and not all(build.result.lower() in always_statuses for build in builds):
                continue
            else:
                for b in builds:
                    yield b

def to_email(mimetype, content):
    maintype, subtype = mimetype.split("/")
    message = MIMEMultipart ()
    message['Subject'] = "Buildbot info"
    if maintype == "text":
        message_part = MIMEText(content, subtype, "utf-8")
    else:
        message_part = MIMEBase(maintype, subtype)
        message_part.set_payload(content)
    message.attach(message_part)
    return message.as_string()

def cli(
    buildbot_url=BUILDBOT_URL,
    repo_url=REPO_URL,
    pattern=PATTERN,
    always_status=ALWAYS_STATUS,
    since_minutes=SINCE_MINUTES,
    latest_n_builds=LATEST_N_BUILDS,
    output_as=OUTPUT_AS,
    for_email=FOR_EMAIL
):
    builds = Builds(get_builds(buildbot_url, repo_url, pattern, always_status, since_minutes, latest_n_builds))
    mimetype, output = builds.output_as(output_as)
    if for_email:
        text = to_email(mimetype, output)
    else:
        text = output
    sys.stdout.write(text)

if __name__ == "__main__":
    logging.getLogger("buildbot").addHandler(logging.NullHandler())
    import argparse
    parser = argparse.ArgumentParser("Show Buildbot info")
    parser.add_argument("--buildbot-url", dest="buildbot_url", default=BUILDBOT_URL)
    parser.add_argument("--repo-url", dest="repo_url", default=REPO_URL)
    parser.add_argument("--pattern", dest="pattern", nargs="*", default=PATTERN)
    parser.add_argument("--always-status", dest="always_status", nargs="*", default=ALWAYS_STATUS)
    parser.add_argument("--since-minutes", type=int, dest="since_minutes", default=SINCE_MINUTES)
    parser.add_argument("--latest-n-builds", type=int, dest="latest_n_builds", default=LATEST_N_BUILDS)
    parser.add_argument("--output-as", type=str, dest="output_as", default=OUTPUT_AS)
    parser.add_argument("--for-email", dest="for_email", action="store_true")
    cli(**vars(parser.parse_args()))
