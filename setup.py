#!/usr/bin/env python
# -*- coding: utf-8 -*-

__copyright__ = "Copyright (C) 2014 Ivan D Vasin"
__credits__ = ["Ivan D Vasin"]
__maintainer__ = "Ivan D Vasin"
__email__ = "nisavid@gmail.com"
__docformat__ = "restructuredtext"

import io as _io
import os as _os
import re as _re

from setuptools import find_packages as _find_packages, setup as _setup


# helpers ---------------------------------------------------------------------


MOD_DOC_RE = _re.compile(r'\A(?:(?:\s*(?:\#[^$]*)?)\n)*'
                          r'(?:(?P<dquot>""")|(?P<squot>\'\'\'))\n?'
                          r'(?P<doc>.*)'
                          r'(?(dquot)"""|\'\'\')',
                         _re.DOTALL | _re.MULTILINE)

MOD_VERSION_RE = _re.compile(r'^__version__ = [\'"](?P<version>[^\'"]*)[\'"]$',
                             _re.MULTILINE)


def file_abspath_from_parts(*relpath_parts):
    return _os.path.join(_os.path.abspath(_os.path.dirname(__file__)),
                         *relpath_parts)


def shortdoc_from_doc(doc):
    def iter_shortdoc_lines():
        for line in doc.split(_os.linesep):
            if not line.strip():
                return

            if line[-1] in '.?!':
                line += ' '

            yield line
    return ' '.join(iter_shortdoc_lines())


def read_doc(mod_filepath):

    mod_text = _io.open(mod_filepath).read()
    match = MOD_DOC_RE.search(mod_text)

    if not match:
        raise RuntimeError('cannot find module docstring in file {!r} with'
                            ' pattern {!r}'
                            .format(mod_filepath, MOD_DOC_RE.pattern))

    return match.group('doc')


def read_version(mod_filepath):

    mod_text = _io.open(mod_filepath).read()
    mod_version_match = MOD_VERSION_RE.search(mod_text)

    if not mod_version_match:
        raise RuntimeError('cannot find module version string in file {!r}'
                            ' with pattern {!r}'
                            .format(mod_filepath, MOD_VERSION_RE.pattern))

    return mod_version_match.group('version')


# basics ----------------------------------------------------------------------

NAME = 'rdb2rdf'

ROOT_PKG_NAME = _re.sub(r'[^\d\w]', '_', _re.sub(r'^[^\w]', '_', NAME))

ROOT_PKG_ABSPATH = file_abspath_from_parts(*(ROOT_PKG_NAME.split('.')
                                              + ['__init__.py']))

VERSION = read_version(ROOT_PKG_ABSPATH)

SITE_URI = ''

DOWNLOAD_URI = 'https://github.com/nisavid/pyrdb2rdf'

DESCRIPTION = shortdoc_from_doc(read_doc(ROOT_PKG_ABSPATH))

README_FILE = 'README.rst'
README = _io.open(README_FILE, 'r').read()

CHANGES_FILE = 'CHANGES.rst'
CHANGES = _io.open(CHANGES_FILE, 'r').read()

LICENSE_FILE = 'LICENSE'
LICENSE = _io.open(LICENSE_FILE, 'r').read()

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
                'spruce-iri', 'spruce-types', 'sqlalchemy >=0.9.1')

EXTRAS_DEPS = {}

TESTS_DEPS = ()

DEPS_SEARCH_URIS = ()


# packages --------------------------------------------------------------------

NAMESPACE_PKGS_NAMES = ()

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
           namespace_packages=NAMESPACE_PKGS_NAMES,
           packages=_find_packages(),
           test_suite=TESTS_PKG_NAME,
           include_package_data=True,
           entry_points=ENTRY_POINTS)
