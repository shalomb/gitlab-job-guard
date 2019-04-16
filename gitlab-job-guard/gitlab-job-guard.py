#!/usr/bin/env python3

# -*- coding: utf-8 -*-

# gitlab-job-guard
# guard pipeline jobs from multiple simultaneous executions

from __future__ import absolute_import, division, print_function

from argparse  import ArgumentParser, RawTextHelpFormatter
from datetime  import datetime
from functools import wraps
try:
  import json
except ImportError:
  import simplejson as json
import logging
from os        import environ, path
from os.path   import basename
from posixpath import join as urljoin
from random    import randint, random
import re
import requests
import requests.exceptions
import signal
from six       import PY2, PY3
import sys
from time      import sleep


class Dotable(dict):
  '''
  Convert any dict/map into a dotable datastructure to make accessing
  attributes easy/elegant and less clumsy.
  src: [Dot notation in python nested dictionaries]
       (https://hayd.github.io/2013/dotable-dictionaries)
  '''

  __getattr__= dict.__getitem__

  def __init__(self, d):
    iterator = d.items() if PY3 else d.iteritems()
    self.update(**dict((k, self.parse(v)) for k, v in iterator))

  @classmethod
  def parse(cls, v):
    if isinstance(v, dict):
      return cls(v)
    elif isinstance(v, list):
      return [cls.parse(i) for i in v]
    else:
      return v

def dotable(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        return Dotable.parse( method(*args, **kwargs) )
    return wrapped


class GuardApiAccessException(Exception):
    pass

class GuardTimeoutException(Exception):
    pass


@dotable
def get_pipeline_runs(project_api_url, private_token):
    '''
    Retrieve the current pipelines objects from the Gitlab Pipelines API.
    [Pipelines API | GitLab](https://docs.gitlab.com/ee/api/pipelines.html)
    '''

    url = urljoin(project_api_url, 'pipelines')
    headers = { 'PRIVATE-TOKEN': private_token,
                'Accept':        'application/json' }

    try:
        response = requests.get(url, headers=headers, timeout=2)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        msg = 'Failed to retrieve project pipeline data, ' + str(e)
        raise GuardApiAccessException(msg)


def setup_logger(*args, **kwargs):
    '''
    Setup and return the root logger ojbect for the application
    '''
    root = logging.getLogger(basename(__file__))
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)
    f = '%(asctime)s %(levelname)s %(name)s %(processName)s[%(process)d,%(lineno)d]: %(message)s'
    formatter = logging.Formatter(f)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    return root


def print_unbuffered(*args, **kwargs):
    '''
    Workaround for python3 where stderr is buffered. WTH python?
    TODO: We could use python -u or set PYTHONUNBUFFERED in the environment but
          those are both settings made outside of this script and also requires
          users to be explicit in how they call it. We need an elegant way that
          does not impose on the user and always does the right thing.
          Fix this once python2 is fully deprecated and we only have to support
          python3 - we may be able to set the shebang to something like
          #!/usr/local/bin/python3 -u
    '''
    if PY3:
        kwargs['flush'] = True
    print(*args, **kwargs)
    file = kwargs.get('file', sys.stderr)
    file.flush()


def env_var_as_arg(*args, **kwargs):
    '''
    Convenience wrapper around argparse.add_argument()

    Derive a named argument from a named environment variable and setup
    sys.argv for argparse to process a lower case variant as a regular CLI
    argument.

    e.g - converting gitlab ci runner environment variables to cmdline args
    CI_API_V4_URL becomes --ci-api-v4-url
    CI_PROJECT_ID becomes --ci-project-id
    ...

    NOTE: Args specified at the command line are trumped by
    values derived from the env and so are effectively useless.
    '''
    env_var   = kwargs.pop('env_var',   None)
    arg_group = kwargs.pop('arg_group', None)

    args      = args if args else ()  # is a tuple
    args      = ( '--' + re.sub('_', '-', env_var).lower(), ) + args

    default   = environ.get(env_var, None)
    if default:  # overrides arguments specified at the command line
        sys.argv = sys.argv + [ args[0], default ]

    # TODO: Refactor for SRP
    kwargs['help'] = ( '\n{}\n\n{}="{}"\n\t'.format( kwargs['help'], env_var,
                         default if default else kwargs.get('default', None) ) )

    arg_group.add_argument(*args, **kwargs)


def cli_args():
    parser = ArgumentParser(
    description='''%(prog)s - Gitlab Pipeline Guard

    Guard against multiple gitlab pipelines running simultaneously.

    This is especially needed to protect against multiple pipeline jobs
    clobbering a deployment and leaving it in an unknown state. This script
    detects conflicts if it detects existing pipelines scheduled for the
    current project and then applies a backoff-and-retry until there are no
    conflicts and it is safe to confinue. Conflicts with other pieplines can
    be narrowed down to ref names (branch or tag name matching a regex) as
    well as pipeline status (also a regex, e.g. 'running', 'pending', etc -
    see https://docs.gitlab.com/ee/api/pipelines.html).

    The default behaviour is to keep retrying until the timeout (1 hour -
    i.e.the default gitlab job timeout) is reached, allowing this script to be
    placed in a separate "guard" job or as a guard condition around existing
    gitlab jobs.
    ''', formatter_class=RawTextHelpFormatter )

    from_env = parser.add_argument_group(
                            'Arguments linked to environment variables (' +
                            'See https://docs.gitlab.com/ee/ci/variables/)' )

    env_var_as_arg( '-c', '--check', '--guard', default='^\d+\-',
        env_var   = 'GUARD_REF_REGEX', arg_group = from_env,
        action = 'store', required = False,
        help='Regular expression to match on pipeline git refs (branch or tag)'+
             ' to detect conflicts.\n'                                         +
             'e.g.\n'                                                          +
             '-c=^[0-9]   - guard if other pipelines ref names begin with a number\n'+
             '-c=^master$ - guard if other pipelines ref matches "master" exactly'
    )

    env_var_as_arg( '-s', '--status-regex', default='running',
        env_var   = 'GUARD_STATUS_REGEX', arg_group = from_env,
        action = 'store', required = False,
        help='Regular expression to match on pipelines status to detect a \n'  +
             'conflict. A match on ref name (-c) is also made.\n'              +
             'e.g.\n'                                                          +
             '-s=running            - guard if other pipelines are running\n'  +
             '-s="running|pending"  - guard if pipelines are running or pending'
    )

    env_var_as_arg( '-u', '--api-url',
        env_var   = 'CI_API_V4_URL', arg_group = from_env,
        action = 'store', required = True,
        help='Absolute URL of the Gitlab API (v4) endpoint\n' +
             'Default value is taken from the environment variable.'
    )

    env_var_as_arg( '-p', '--project-id',
        env_var   = 'CI_PROJECT_ID', arg_group = from_env,
        action = 'store', required = True,
        help='Gitlab project ID whose pipelines are examined for conflicts.\n' +
             'Default value is taken from the environment variable.'
    )

    env_var_as_arg( '-i', '--pipeline-id',
        env_var   = 'CI_PIPELINE_ID', arg_group = from_env,
        action = 'store', required = True,
        help='ID of the pipeline that the current job runs under.\n' +
             'Default value is taken from the environment variable.'
    )

    env_var_as_arg( '-t', '--access-token', '--api-token',
        env_var   = 'PRIVATE_TOKEN', arg_group = from_env,
        action = 'store', required = True,
        help='Personal access token for Gitlab API access. \n' +
             '(See https://docs.gitlab.com/ee/api/#personal-access-tokens)'
    )

    env_var_as_arg( '-w', '--timeout', default = 3600,
        env_var   = 'GUARD_TIMEOUT', arg_group = from_env,
        action = 'store', required = False, type = int,
        help='Timeout after which script fails.'
    )

    parser.add_argument('-q', '--silent', '--quiet', default = False,
        action = 'store_true',
        help='Do not print any output.')

    parser.add_argument('-x', '--no-wait', '--exit', default = False,
        action = 'store_true',
        help='Fail immediately if conflicting pipelines are detected.')

    return parser.parse_args()


def main():
    args = cli_args()
    log = setup_logger()

    def timeout_handler(signum, frame):
        msg = 'Timeout reached after {} seconds, giving up ...'.format(
                                                            args.guard_timeout )
        log.error(msg)
        sys.exit(11)

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(args.guard_timeout)

    backoff_factor  = randint(2, 5) + random()

    _conflicts = []
    while True:
        try:
            project_api_url = urljoin( args.ci_api_v4_url,
                                        'projects', args.ci_project_id )

            runs = get_pipeline_runs(project_api_url, args.private_token)

            # Conflict detection
            conflicts = [ p for p in runs if
                            re.search( args.guard_ref_regex,    p.ref    ) and
                            re.match(  args.guard_status_regex, p.status ) and
                            int(p.id) != int(args.ci_pipeline_id) ]

        except Exception as e:
            log.error('{}("{}")'.format(e.__class__.__name__, str(e)))

            # Play nice to network/gitlab if in failure/recovery
            backoff_factor = int(backoff_factor * 1.5) % 30
            sleep(backoff_factor)
            continue

        msg = '{} other pipelines in ({}) state.'.format(
                                                    len(conflicts),
                                                    args.guard_status_regex )

        # Log a summary of conflicting pipelines
        if not args.silent:
            if _conflicts != conflicts:
                print_unbuffered('')
                log.info(msg)
                for i in conflicts:
                    log.info( 'Pipeline #{} {:<10} {} {}'.format(
                                            str(i.id), i.status, i.sha, i.ref ))
            else:
                # Dot status if no changes are detected since last poll.
                print_unbuffered('.', end='', file=sys.stderr)

        if conflicts:
            if args.no_wait:
                log.error(msg + '. Exiting on request.')
                sys.exit(7)
            else:
                sleep(randint(3, 15))  # collision avoidance
        else:
            log.info('No other conflicting pipelines detected, proceeding ...')
            sys.exit(0)

        _conflicts = conflicts


if __name__ == '__main__':
    main()

