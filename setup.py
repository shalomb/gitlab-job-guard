#!/usr/bin/env python3

# -*- coding: utf-8 -*-

import os
from setuptools import setup

# pip install -e ./  # requires the following
# pip install setuptools wheel

requirements = '''
future
requests
six
'''.split('\n')

setup(  name='gitlab-job-guard',
        version='v0.0.1',
        description="Guard gitlab jobs from multiple simultaneous executions",
        url='https://gitlab.com/s.bhooshi/gitlab-job-guard',
        author='Shalom Bhooshi',
        author_email='s.bhooshi@gmail.com',
        license='Apache License 2.0',
        packages=['gitlab-job-guard'],
        zip_safe=False,
        scripts=['gitlab-job-guard/guard.py'],
        install_requires=requirements,
        keywords='gitlab-ci pipeline job guard',
        python_requires='>=2.7, >=3.5, !=3.0, !=3.0.*, !=3.1, !=3.1.*, !=3.2, !=3.2.*, !=3.3, !=3.3.*, !=3.4, !=3.4.*',
    )

