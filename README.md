[![pipeline status](https://gitlab.com/s.bhooshi/gitlab-job-guard/badges/master/pipeline.svg)](https://gitlab.com/s.bhooshi/gitlab-job-guard/commits/master)

# gitlab-job-guard

Guard pipeline jobs from multiple simultaneous executions

```bash
$ PRIVATE_TOKEN="$GITLAB_PERSONAL_ACCESS_TOKEN" ./guard.py -w 3600
$ my-unguarded-deployment-task --to=production
```

`./guard.py` will block if it detects other pipelines running for the current
project to avoid multiple pipelines from clobbering up a deployment/environment.

While gitlab will _auto-cancel redundant, pending pipelines_ for the same
branch, multiple pipelines for _different branches_ targeting a particular
deployment/environment are allowed to run simultaneously (especially if
using `gitflow` and say, `feature/*` branches target a `dev` environment or
`release/*` branches target a `staging` environment, etc). Gitlab has no way
to detect or control these user-defined branch-to-environment mappings and this
often means jobs from different pipelines are allowed to run simultaneously
against an environment - clobbering it up and leaving it in a unsafe/broken
state. (e.g. `terraform apply` or `ansible`, etc from different pipelines
running at the same time).

`./guard.py` uses the Gitlab API to query pipeline data and detect conflicts.
Conflicts are detected by user-defined matches on pipeline ref names
(branch, tag, etc) and/or status.

## Usage

The simplest usage would likely be placing `./guard.py` in a `before_script`
section in your `gitlab-ci.yml` to protect all jobs (though this can slow
things down).

```yaml
before_script:
  - PRIVATE_TOKEN="$GITLAB_PERSONAL_ACCESS_TOKEN" ./guard.py
```

Though often, this is only needed to guard jobs that share common state/data
(i.e. a deployment environment, an artifact build/release, etc).

```yaml
deploy-production:
  stage: deploy
  script:
    - PRIVATE_TOKEN="$GITLAB_PERSONAL_ACCESS_TOKEN" ./guard.py
    - my-unguarded-deployment-task --to=production
```
