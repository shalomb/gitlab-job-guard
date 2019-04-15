from setuptools import setup

# pip install -e ./  # requires the following
# pip install setuptools wheel

setup(  name='gitlab-job-guard',
        version='v1.3.0',
        description="Guard gitlab jobs from multiple simultaneous executions",
        url='https://gitlab.com/s.bhooshi/gitlab-job-guard',
        author='Shalom Bhooshi',
        author_email='s.bhooshi@gmail.com',
        license='Apache License 2.0',
        packages=['gitlab-job-guard'],
        zip_safe=False,
        scripts=['./guard.py'],
        install_requires=[
          'pyyaml'
        ],
    )

