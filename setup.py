from setuptools import setup, find_packages
from boom import __version__

description = ''
for file_ in ('README', 'CHANGES', 'CONTRIBUTORS', 'LICENCE'):
    with open('%s.rst' % file_) as f:
        description += f.read() + '\n\n'

# TODO: Change name to publish in PYPI.
setup(
    name='boom',
    version=__version__,
    url='https://github.com/lee-pai-long/boom',
    packages=find_packages(),
    long_description=description,
    description="Simple HTTP Load tester",
    author="Lee Pai Long",
    author_email="mohamed.ali.saidina+github@gmail.com",
    include_package_data=True,
    zip_safe=False,
    classifiers=[
        "Development Status :: 5 - Production/Stable",
        "License :: OSI Approved :: Apache Software License",
        "Programming Language :: Python",
        "Programming Language :: Python :: 2.7",
        "Programming Language :: Python :: 3.4",
        "Programming Language :: Python :: 3.5",
    ],
    install_requires=[
        'gevent==1.1.2',
        'requests>=2.3.0',
        'PyYAML>=3.12'
    ],
    test_suite='unittest2.collector',
    entry_points={
        "console_scripts": [
            "boom = boom.boom:main"
        ]
    }
)
