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


# read the contents of your README file
from os import path
this_directory = path.abspath(path.dirname(__file__))
with open(path.join(this_directory, 'README.md'), encoding='utf-8') as f:
    long_description = f.read()

setup(  name='gitlab-job-guard',
        version='v0.0.1',
        description="Guard gitlab jobs from multiple simultaneous executions",
        long_description=long_description,
        long_description_content_type="text/markdown",
        url='https://gitlab.com/s.bhooshi/gitlab-job-guard',
        author='Shalom Bhooshi',
        author_email='s.bhooshi@gmail.com',
        license='Apache License 2.0',
        packages=['gitlab-job-guard'],
        zip_safe=False,
        scripts=['gitlab-job-guard/gitlab-job-guard.py'],
        install_requires=requirements,
        keywords='gitlab-ci pipeline job guard',
        python_requires='>=2.7, >=2.7.1, !=3.0, !=3.0.*, !=3.1, !=3.1.*, !=3.2, !=3.2.*, !=3.3, !=3.3.*, !=3.4, !=3.4.*',
    )

