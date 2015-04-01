============
buildbotinfo
============

-------------------------------------------
Provide summary information about buildbots
-------------------------------------------

tl;dr
-----

You can schedule a command-line to show a pattern of buildbot status::

  buildbotinfo.py --pattern "*Windows*" "*XP*" --output-as=html
  
I have a cron job running which sends me an HTML email with the current
status of all Windows buildbots::

  python3 ~/work-in-progress/buildbotinfo/buildbotinfo.py \
  --pattern "*Windows*" "*XP*" --output-as=html --for-email \
 | sendmail mail@timgolden.me.uk
  

Background
----------

The Python development effort is assisted by a fleet of buildbots, mostly volunteer-driven,
and covering a range of platforms. They serve to let us know whether a code change is going
to cause a problem with a particular platform. Most developers have one primary platform
and perhaps test on one another if they can do so easily, but most of us don't have a
raft of *BSD, Win* or *nix machines all configured to pull and build.

You can view the buildbots in various ways: https://www.python.org/dev/buildbot/ and those
screens offer an RSS feed. But sometimes people find it handy to have a push mechanism
which emails them when some situation obtains. For example, someone who's responsible for
running certain buildbot machines might want to see when they're failing continuously. Or
a Python developer specialising in one platform might want to see the status of the
buildbots supporting that platform.

buildbotlib.py & buildbotinfo.py
--------------------------------

buildbotlib
~~~~~~~~~~~

`buildbotlib` is a light wrapper around some of the 
`Buildbot XML-RPC <http://docs.buildbot.net/0.8.0/XMLRPC-server.html>`_ interface.

buildbotinfo
~~~~~~~~~~~~

The core of the `buildbotinfo` module is the `get_builds` function which yields builds
from a buildbot according to:

* Whether the buildbot name matches one or more patterns
* Looking only for builds completed since a certain number of minutes ago
* Looking only for the last n completed builds
* Whether all the builds found matching the previous rules are of a given status

By combining these parameters, you can produce the following kinds of output:

* The latest status of all the Windows buildbots
* The last three builds for all buildbots which built over the last two days
  [implicitly excluding "dead" buildbots]
* Any Solaris buildbot which has failed the last three builds

Command Line
~~~~~~~~~~~~

By default, `buildbotinfo` runs a command line with the following arguments::

    usage: Show Buildbot info [-h] [--buildbot-url BUILDBOT_URL]
                              [--repo-url REPO_URL]
                              [--pattern [PATTERN [PATTERN ...]]]
                              [--always-status [ALWAYS_STATUS [ALWAYS_STATUS ...]]]
                              [--since-minutes SINCE_MINUTES]
                              [--latest-n-builds LATEST_N_BUILDS]
                              [--output-as OUTPUT_AS] [--for-email]

    optional arguments:
      -h, --help            show this help message and exit
      --buildbot-url BUILDBOT_URL
      --repo-url REPO_URL
      --pattern [PATTERN [PATTERN ...]]
      --always-status [ALWAYS_STATUS [ALWAYS_STATUS ...]]
      --since-minutes SINCE_MINUTES
      --latest-n-builds LATEST_N_BUILDS
      --output-as OUTPUT_AS
      --for-email

buildbot_url
    The root of the buildbot API. Defaults to the Python one although 
    in other respects this code is designed to work with any buildbot setup
    which has the same XML-RPC interface.
    
    **Example:** http://buildbot.python.org/ 

repo_url
    (Optional) 
    Allows the output to link through to the underlying repository.
    Again, defaults to the CPython repo.
    
    **Example:** http://hg.python.org/cpython/

pattern
    (Multiple, Optional, Default: all) 
    None or more builder names, using fnmatch wildcards.
    
    **Example:** \*Windows\* \*XP\* [will find all windows builders]
    
always-status
    (Multiple, Optional)
    If specified, will return only builds from those builders where all the builds considered
    match one of the status. Typically this will be FAILED to show always-red builders.
    
    **Example:** Failure

since-minutes
    (Optional, Default: no time limit)
    Only builds completing since this time are considered
    
    **Example:** 2880 [will consider builds completing in the last two days]

latest-n-builds
    (Optional, Default: 1)
    Only this many builds will be considered for each builder. The default (1) means that the
    current status of the builder is effectively shown.

output-as
    (Optional, Default: text)
    Output will produced in this format, currently accepting: text, html, json.

for-email
    (Optional, Default: No)
    Output will be formatted as a MIME Message, suitable for piping to a sendmail command
    or some other mailer.

Examples
~~~~~~~~

* Show the latest status of all Windows builders::

    buildbotinfo.py --pattern "*Windows*" "*XP*"

* Show the Solaris builders which have been red for their last three builds::

    buildbotinfo.py --pattern "*Solaris*" --latest-n-builds=3 --always-status Failure Exception

* Show all the builds over the last two days::

    buildbotinfo.py --since-minutes=2880 
