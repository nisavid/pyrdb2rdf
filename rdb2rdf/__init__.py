# -*- coding: utf-8 -*-
"""PyRDB2RDF"""

__version__ = "0.1.2"
__copyright__ = "Copyright (C) 2014 Ivan D Vasin"
__credits__ = ["Ivan D Vasin"]
__maintainer__ = "Ivan D Vasin"
__email__ = "nisavid@gmail.com"
__docformat__ = "restructuredtext"

import logging as _log

from ._common import *


_log.getLogger('rdb2rdf').addHandler(_log.NullHandler())
