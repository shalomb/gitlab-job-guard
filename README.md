[![pipeline status](https://gitlab.com/s.bhooshi/gitlab-job-guard/badges/master/pipeline.svg)](https://gitlab.com/s.bhooshi/gitlab-job-guard/commits/master)

# gitlab-job-guard

Guard pipeline jobs from multiple simultaneous executions

```bash
$ PRIVATE_TOKEN="$GITLAB_API_TOKEN" gitlab-job-guard -w 3600
$ my-unguarded-deployment-task --to=production
```

`gitlab-job-guard`  will block  if  it detects  other  pipelines running  for
the  current  project   to  avoid  multiple  pipelines  from   clobbering  up  a
deployment/environment.

While gitlab will _auto-cancel redundant, pending pipelines_ for the same branch
by  default -  this  is not  the  case for  multiple  pipelines from  _different
branches_ targeting  a particular deployment/environment.  Gitlab has no  way to
detect  or control  these user-defined  branch-to-environment mappings  and this
means  environments  can  easily  be  left  in  an  unsafe/broken  state.  (e.g.
`terraform apply` or `ansible`, etc from different pipelines running at the same
time).

`gitlab-job-guard` uses the Gitlab API to determine if existing pipelines are
scheduled and to backoff-and-retry  until it is safe to proceed. Conflicts
are detected  by user-defined matches on  pipeline ref names (branch,  tag, etc)
and/or status.

## Usage

The  simplest  usage   would  likely  be  placing   `gitlab-job-guard`  in  a
`before_script` section in your `gitlab-ci.yml` to protect all jobs (though this
can slow things down).

```yaml
before_script:
  - PRIVATE_TOKEN="$GITLAB_API_TOKEN" gitlab-job-guard
```

Though often,  this is only  needed to guard  jobs that share  common state/data
(i.e. a deployment environment, an artifact build/release, etc).

```yaml
deploy-production:
  stage: deploy
  script:
    - PRIVATE_TOKEN="$GITLAB_API_TOKEN" gitlab-job-guard
    - my-unguarded-deployment-task --to=production
```

To hold jobs for a collisions on pattern matches in the ref/branch name.

```bash
gitlab-job-guard -c=^master$   # Match branch names matching master exactly.

gitlab-job-guard -c=^(master|dev(elop)?)$   # Match any mainline branches

gitlab-job-guard -c=^[0-9]\-   # Match branch names beginning with a number and dash
                                  # ignoring all other text.
                                  # e.g. a gitlab branch made from an issue.

gitlab-job-guard -c=^v[\d.]+$               # Match (semver) tags

gitlab-job-guard -c=^environment/           # Match any environment deployments?

gitlab-job-guard -c=^environment/dc1.+      # Match deployments to DC1?

gitlab-job-guard -c="$CI_BUILD_REF_NAME"    # Match current branch name (partially).
                                               # e.g. 'master' matches 'feature/master-document'

gitlab-job-guard -c="^$CI_BUILD_REF_NAME$"  # Match current branch name (exactly).
                                               # e.g. 'master' does not match 'master-deployment'

```

To hold a job for a collision on part of the ref name (e.g. on branch prefix
such as `feature/` or `hotfix/` or `release/`, etc _a la_ `gitflow`).

```bash
# Assuming CI_BUILD_REF_NAME=feature/foo

CI_BUILD_REF_PREFIX=$(echo "$CI_BUILD_REF_NAME" | sed -r 's@(.+/)(.+)@\1@')
# CI_BUILD_REF_PREFIX now contains 'feature/'

gitlab-job-guard -c="^$CI_BUILD_REF_PREFIX" -s='running|pending'
```

# TODO

For long pipelines, this solution can have subtle consequences with growing
queues and increased contention and unpredictability as to which pipeline is
the first-past-the-post. An older pipeline taking precedence over newer commits
if often not desired and newer pipelines always winning is probably desired.

* Handle existing conflicting pipelines - cancel them or give-way.
* Narrow down conflicts to jobs (`CI_JOB_NAME`) or stages (`CI_JOB_STAGE`)
  so that other parts of the pipelines that do not share state are allowed to
  run freely.
