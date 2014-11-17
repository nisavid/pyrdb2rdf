#!/usr/bin/env python
# -*- coding: utf-8 -*-

__copyright__ = "Copyright (C) 2014 Ivan D Vasin"
__credits__ = ["Ivan D Vasin"]
__maintainer__ = "Ivan D Vasin"
__email__ = "nisavid@gmail.com"
__docformat__ = "restructuredtext"

from setuptools import find_packages as _find_packages, setup as _setup


# basics ----------------------------------------------------------------------

NAME = 'rdb2rdf'

ROOT_PKG_NAME = NAME.lower().replace('-', '_')

ROOT_PKG = __import__(ROOT_PKG_NAME)

VERSION = ROOT_PKG.__version__

SITE_URI = ''

DOWNLOAD_URI = 'https://github.com/nisavid/pyrdb2rdf'

DESCRIPTION = \
    iter(line for line in ROOT_PKG.__doc__.split('\n') if line.strip()).next()

README_FILE = 'README.rst'
with open(README_FILE, 'r') as _file:
    README = _file.read()

CHANGES_FILE = 'CHANGES.rst'
with open(CHANGES_FILE, 'r') as _file:
    CHANGES = _file.read()

LICENSE_FILE = 'LICENSE'
with open(LICENSE_FILE, 'r') as _file:
    LICENSE = _file.read()

LONG_DESCRIPTION = '\n\n'.join((README, CHANGES))

TROVE_CLASSIFIERS = \
    ('Development Status :: 2 - Pre-Alpha',
     'Intended Audience :: Developers',
     'License :: OSI Approved :: GNU Lesser General Public License v3'
      ' (LGPLv3)',
     'Operating System :: POSIX',
     'Programming Language :: Python :: 2.7',
     'Topic :: Database',
     'Topic :: Internet',
     'Topic :: Software Development :: Libraries :: Python Modules',
     )


# dependencies ----------------------------------------------------------------

SETUP_DEPS = ()

INSTALL_DEPS = ('rdflib', 'spruce-collections', 'spruce-datetime',
                'spruce-lang', 'sqlalchemy >=0.9.1')

EXTRAS_DEPS = {}

TESTS_DEPS = ()

DEPS_SEARCH_URIS = ()


# packages --------------------------------------------------------------------

NAMESPACE_PKGS_PATHS = ()

SCRIPTS_PKG_NAME = '.'.join((ROOT_PKG_NAME, 'scripts'))

TESTS_PKG_NAME = '.'.join((ROOT_PKG_NAME, 'tests'))


# entry points ----------------------------------------------------------------

STD_SCRIPTS_PKG_COMMANDS = {}

COMMANDS = {cmd: '{}.{}:{}'.format(SCRIPTS_PKG_NAME,
                                   script if isinstance(script, basestring)
                                          else script[0],
                                   'main' if isinstance(script, basestring)
                                          else script[1])
            for cmd, script in STD_SCRIPTS_PKG_COMMANDS.items()}

ENTRY_POINTS = {'console_scripts': ['{} = {}'.format(name, funcpath)
                                    for name, funcpath in COMMANDS.items()],
                'rdf.plugins.store':
                    ('rdb2rdf_dm = rdb2rdf.stores:DirectMapping',),
                }


if __name__ == '__main__':
    _setup(name=NAME,
           version=VERSION,
           url=SITE_URI,
           download_url=DOWNLOAD_URI,
           description=DESCRIPTION,
           long_description=LONG_DESCRIPTION,
           author=', '.join(__credits__),
           maintainer=__maintainer__,
           maintainer_email=__email__,
           license=LICENSE,
           classifiers=TROVE_CLASSIFIERS,
           setup_requires=SETUP_DEPS,
           install_requires=INSTALL_DEPS,
           extras_require=EXTRAS_DEPS,
           tests_require=TESTS_DEPS,
           dependency_links=DEPS_SEARCH_URIS,
           namespace_packages=NAMESPACE_PKGS_PATHS,
           packages=_find_packages(),
           test_suite=TESTS_PKG_NAME,
           include_package_data=True,
           entry_points=ENTRY_POINTS)
