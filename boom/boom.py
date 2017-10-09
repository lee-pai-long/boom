from __future__ import absolute_import
import argparse
import gevent
import logging
import requests
import sys
import time

try:
    import urlparse
except ImportError:
    from urllib import parse as urlparse

import math
from collections import defaultdict, namedtuple
from copy import copy
from gevent import monkey
from gevent.pool import Pool
from requests import RequestException
from requests.packages.urllib3.util import parse_url
from socket import gethostbyname, gaierror

from boom import __version__
from boom.util import resolve_name
from boom.pgbar import AnimatedProgressBar


monkey.patch_all()
logger = logging.getLogger('boom')
_VERBS = ('GET', 'POST', 'DELETE', 'PUT', 'HEAD', 'OPTIONS')
_DATA_VERBS = ('POST', 'PUT')
ARGS = [
    {
        'flags': ['--version'],
        'options': {
            'help': 'Displays version and exits.',
            'action': 'store_true'
        }
    },
    {
        'flags': ['-m', '--method'],
        'options': {
            'help': "One of {verbs}.".format(verbs=', '.join(_VERBS)),
            'type': str,
            'default': 'GET',
            'choices': _VERBS
        }
    },
    {
        'flags': ['--content-type'],
        'options': {
            'help': 'Content-Type to use.',
            'type': str,
            'default': 'text/plain'
        }
    },
    {
        'flags': ['-D', '--data'],
        'options': {
            'help': 'Data. Prefixed by "py:" to point a python callable.',
            'type': str
        }
    },
    {
        # REVIEW: Change this to clients.
        'flags': ['-c', '--concurrency'],
        'options': {
            'help': 'Number of client ot use',
            'type': int,
            'default': 1
        }
    },
    {
        'flags': ['-a', '--auth'],
        'options': {
            'help': 'Basic authentication user:password',
            'type': str
        }
    },
    {
        'flags': ['-H', '--header'],
        'options': {
            'help': 'Custom header. name:value',
            'action': 'append',
            'type': str
        }
    },
    {
        'flags': ['--pre-hook'],
        'options': {
            'help': (
                'Python module path (eg: mymodule.pre_hook) '
                'to a callable which will be executed before '
                'doing a request for example: '
                'pre_hook(method, url, options). '
                'It must return a tuple of parameters given in '
                'function definition'
            ),
            'type': str
        }
    },
    {
        'flags': ['--post-hook'],
        'options': {
            'help': (
                'Python module path (eg: mymodule.post_hook) '
                'to a callable which will be executed after '
                'a request is done for example: '
                'eg. post_hook(response). '
                'It must return a given response parameter or '
                'raise an `boom.boom.RequestException` for '
                'failed request.'
            ),
            'type': str
        }
    },
    {
        'flags': ['--json-output'],
        'options': {
            'help': 'Prints the results in JSON.',
            'action': 'store_true'
        }
    },
    {
        'flags': ['-q', '--quiet'],
        'options': {
            'help': "Don't display progress bar",
            'action': 'store_true',
        }
    },
    {
        'flags': ['-n', '--requests'],
        'options': {
            'help': 'Number of requests',
            'type': int
        }
    },
    {
        'flags': ['-d', '--duration'],
        'options': {
            'help': 'Duration in seconds.',
            'type': int
        }
    },
    {
        'flags': ['url'],
        'options': {
            'help': 'URL to hit.',
            # REVIEW: Why nargs ?, there is no default...
            'nargs': '?'
        }
    },
    {
        'flags': ['-k ', '--insecure'],
        'options': {
            'help': 'Allow insecure SSL connections',
            'action': 'store_true',
        }
    }
]


class RunResults(object):

    """Encapsulates the results of a single Boom run.

    Contains a dictionary of status codes to lists of request durations,
    a list of exception instances raised during the run, the total time
    of the run and an animated progress bar.
    """

    def __init__(self, num=1, quiet=False):
        self.status_code_counter = defaultdict(list)
        self.errors = []
        self.total_time = None
        if num is not None:
            self._progress_bar = AnimatedProgressBar(
                end=num,
                width=65)
        else:
            self._progress_bar = None
        self.quiet = quiet

    def incr(self):
        if self.quiet:
            return
        if self._progress_bar is not None:
            self._progress_bar + 1
            self._progress_bar.show_progress()
        else:
            sys.stdout.write('.')
            sys.stdout.flush()

# REVIEW: Put elements in one line each.
RunStats = namedtuple(
    'RunStats', ['count', 'total_time', 'rps', 'avg', 'min',
                 'max', 'amp', 'stdev'])


def calc_stats(results):
    """Calculate stats (min, max, avg) from the given RunResults.

       The statistics are returned as a RunStats object.
    """
    all_res = []
    count = 0
    for values in results.status_code_counter.values():
        all_res += values
        count += len(values)

    cum_time = sum(all_res)

    if cum_time == 0 or len(all_res) == 0:
        rps = avg = min_ = max_ = amp = stdev = 0
    else:
        if results.total_time == 0:
            rps = 0
        else:
            rps = len(all_res) / float(results.total_time)
        avg = sum(all_res) / len(all_res)
        max_ = max(all_res)
        min_ = min(all_res)
        # REVIEW: No need to reuse max/min here, use max_ and min_.
        amp = max(all_res) - min(all_res)
        # REVIEW: Rename x to res for readability.
        stdev = math.sqrt(sum((x-avg)**2 for x in all_res) / count)

    return (
        RunStats(count, results.total_time, rps, avg, min_, max_, amp, stdev)
    )


# TODO: Switch to PrettyTable.
def print_stats(results):
    stats = calc_stats(results)
    rps = stats.rps

    print('')
    print('-------- Results --------')

    print('Successful calls\t\t%r' % stats.count)
    print('Total time        \t\t%.4f s  ' % stats.total_time)
    print('Average           \t\t%.4f s  ' % stats.avg)
    print('Fastest           \t\t%.4f s  ' % stats.min)
    print('Slowest           \t\t%.4f s  ' % stats.max)
    print('Amplitude         \t\t%.4f s  ' % stats.amp)
    print('Standard deviation\t\t%.6f' % stats.stdev)
    print('RPS               \t\t%d' % rps)
    if rps > 500:
        print('BSI              \t\tWoooooo Fast')
    elif rps > 100:
        print('BSI              \t\tPretty good')
    elif rps > 50:
        print('BSI              \t\tMeh')
    else:
        print('BSI              \t\t:(')
    print('')
    print('-------- Status codes --------')
    for code, items in results.status_code_counter.items():
        print('Code %d          \t\t%d times.' % (code, len(items)))
    print('')
    print('-------- Legend --------')
    print('RPS: Request Per Second')
    print('BSI: Boom Speed Index')


def print_server_info(url, method, headers=None, **options):
    res = requests.head(url, **options)
    print(
        'Server Software: %s' %
        res.headers.get('server', 'Unknown')
    )
    print('Running %s %s' % (method, url))

    if headers:
        for k, v in headers.items():
            print('\t%s: %s' % (k, v))


def print_errors(errors):
    if len(errors) == 0:
        return
    print('')
    print('-------- Errors --------')
    for error in errors:
        print(error)


def print_json(results):
    """Prints a JSON representation of the results to stdout."""
    import json
    stats = calc_stats(results)
    print(json.dumps(stats._asdict()))


def onecall(method, url, results, **options):
    """Performs a single HTTP call and puts the result into the
       status_code_counter.

    RequestExceptions are caught and put into the errors set.
    """
    start = time.time()

    if 'data' in options and callable(options['data']):
        options = copy(options)
        options['data'] = options['data'](method, url, options)

    if 'pre_hook' in options:
        method, url, options = options[
            'pre_hook'](method, url, options)
        del options['pre_hook']

    if 'post_hook' in options:
        post_hook = options['post_hook']
        del options['post_hook']
    else:
        def post_hook(res):
            return res

    try:
        res = post_hook(method(url, **options))
    except RequestException as exc:
        results.errors.append(exc)
    else:
        duration = time.time() - start
        results.status_code_counter[res.status_code].append(duration)
    finally:
        results.incr()


def run(url, num=1, duration=None, method='GET', data=None, auth=None,
        content_type='text/plain', concurrency=1, headers=None, pre_hook=None,
        post_hook=None, quiet=False, insecure=False):

    if headers is None:
        headers = {}

    if 'content-type' not in headers:
        headers['Content-Type'] = content_type

    # REVIEW: callable is error prone because a build-in of same name exists.
    if data is not None and data.startswith('py:'):
        callable = data[len('py:'):]
        data = resolve_name(callable)

    method = getattr(requests, method.lower())
    options = {
        'headers': headers,
        'verify': not insecure
    }

    if pre_hook is not None:
        options['pre_hook'] = resolve_name(pre_hook)

    if post_hook is not None:
        options['post_hook'] = resolve_name(post_hook)

    if data is not None:
        options['data'] = data

    if auth is not None:
        options['auth'] = tuple(auth.split(':', 1))

    pool = Pool(concurrency)
    start = time.time()
    jobs = None
    res = RunResults(num, quiet)

    # REVIEW: Rewrite this with suppress(https://goo.gl/d1hguZ)
    try:
        if num is not None:
            jobs = [pool.spawn(onecall, method, url, res, **options)
                    for i in range(num)]
            pool.join()
        else:
            with gevent.Timeout(duration, False):
                jobs = []
                while True:
                    jobs.append(pool.spawn(onecall, method, url, res,
                                           **options))
                pool.join()
    except KeyboardInterrupt:
        # In case of a keyboard interrupt, just return whatever already got
        # put into the result object.
        pass
    finally:
        res.total_time = time.time() - start

    return res


# FIXME: Doesn't seems to work with /etc/hosts files?
def resolve(url):
    parts = parse_url(url)

    if not parts.port and parts.scheme == 'https':
        port = 443
    elif not parts.port and parts.scheme == 'http':
        port = 80
    else:
        port = parts.port

    original = parts.host
    resolved = gethostbyname(parts.host)

    # Don't use a resolved hostname for SSL requests otherwise the
    # certificate will not match the IP address (resolved)
    host = resolved if parts.scheme != 'https' else parts.host
    netloc = '%s:%d' % (host, port) if port else host

    if port not in (443, 80):
        host += ':%d' % port
        original += ':%d' % port

    return (urlparse.urlunparse((parts.scheme, netloc, parts.path or '',
                                 '', parts.query or '',
                                 parts.fragment or '')),
            original, host)


def load(url, requests, concurrency, duration, method, data, content_type,
         auth, headers=None, pre_hook=None, post_hook=None, quiet=False,
         insecure=False):
    if not quiet:
        print_server_info(url, method, headers=headers, verify=not insecure)

        if requests is not None:
            print('Running %d queries - concurrency %d' % (requests,
                                                           concurrency))
        else:
            print('Running for %d seconds - concurrency %d.' %
                  (duration, concurrency))

        sys.stdout.write('Starting the load')
    try:
        return run(url, requests, duration, method, data, auth,
                   content_type, concurrency, headers, pre_hook, post_hook,
                   quiet=quiet, insecure=insecure)
    finally:
        if not quiet:
            print(' Done')


def _split(header):
    header = header.split(':')
    if len(header) != 2:
        raise ValueError(
            "A header must be of the form name:value, got '{}'".format(header)
        )
    return header


def cli(arguments=ARGS):
    """Parse arguments an return a parser object."""

    # Parsing arguments from cli.
    parser = argparse.ArgumentParser(
        description='Simple HTTP Load runner.',
        formatter_class=argparse.ArgumentDefaultsHelpFormatter
    )
    for argument in arguments:
        parser.add_argument(*argument['flags'], **argument['options'])

    # Validate arguments.
    # TODO: print usage to stderr.
    args = parser.parse_args()
    if args.version:
        print(__version__)
        sys.exit(1)
    if args.url is None:
        print('You need to provide an URL.')
        parser.print_usage()
        sys.exit(1)
    if args.data is not None and args.method not in _DATA_VERBS:
        print("You can't provide data with %r" % args.method)
        parser.print_usage()
        sys.exit(1)
    if args.requests is None and args.duration is None:
        args.requests = 1
    if args.header is None:
        args.headers = {}
    else:
        try:
            args.headers = dict([_split(header) for header in args.header])
        except ValueError as e:
            print(str(e))
            parser.print_usage()

    # Return arguments.
    return args


def main():

    args = cli()

    try:
        url, original, resolved = resolve(args.url)
    except gaierror as e:
        print_errors(("DNS resolution failed for %s (%s)" %
                      (args.url, str(e)),))
        sys.exit(1)

    if original != resolved and 'Host' not in args.headers:
        args.headers['Host'] = original

    try:
        res = load(url, args.requests, args.concurrency, args.duration,
                   args.method, args.data, args.content_type, args.auth,
                   headers=args.headers, pre_hook=args.pre_hook,
                   post_hook=args.post_hook,
                   quiet=(args.json_output or args.quiet),
                   insecure=args.insecure)
    except RequestException as e:
        print_errors((e, ))
        sys.exit(1)

    if not args.json_output:
        print_errors(res.errors)
        print_stats(res)
    else:
        print_json(res)

    logger.info('Bye!')

if __name__ == '__main__':
    main()
