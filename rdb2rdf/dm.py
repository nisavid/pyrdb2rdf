# -*- coding: utf-8 -*-
"""Direct mapping

.. _direct mapping: http://www.w3.org/TR/rdb-direct-mapping/

.. _RDF: http://www.w3.org/TR/rdf11-concepts/

.. _SQLAlchemy: http://www.w3.org/TR/rdf11-concepts/

"""

__copyright__ = "Copyright (C) 2014 Ivan D Vasin"
__docformat__ = "restructuredtext"

import rdflib as _rdf
import rdflib.resource as _rdf_res
import sqlalchemy as _sqla
import sqlalchemy.orm as _sqla_orm
import sqlalchemy.ext.automap as _sqla_automap
import sqlalchemy.ext.declarative as _sqla_decl

from . import _common


def orm_automap_base(name='Base', base_iri=None, mapper=None,
                     use_pseudo_primary_keys=True, declarative_base=None,
                     **kwargs):

    """

    .. note:: **WARNING:**
        Tables without primary keys are treated with some mangling of the
        metadata.

    """

    DeclarativeBase = \
        orm_declarative_base(name='{}_DeclarativeBase'.format(name),
                             base_iri=base_iri,
                             cls=(declarative_base or object),
                             mapper=mapper,
                             **kwargs)
    AutomapBase = \
        _sqla_automap.automap_base(DeclarativeBase,
                                   name=('{}_AutomapBase'.format(name)
                                         if use_pseudo_primary_keys else name))

    if not use_pseudo_primary_keys:
        return AutomapBase

    prepare_base = AutomapBase.prepare

    @classmethod
    def prepare(cls, engine=None, reflect=False, **kwargs):

        if reflect:
            cls.metadata.reflect(bind=engine)

        pseudo_pkey_tables_names = set()
        for table in cls.metadata.tables.values():
            if not table.primary_key:
                if table.indexes:
                    pseudo_pkey_index = \
                        min((index for index in table.indexes if index.unique),
                            key=(lambda index: len(index.columns)))
                    pseudo_pkey_cols = pseudo_pkey_index.columns
                else:
                    pseudo_pkey_cols = table.columns

                table.primary_key = \
                    PseudoPrimaryKeyConstraint(*pseudo_pkey_cols)
                pseudo_pkey_tables_names.add(table.key)

        prepare_base(engine=engine, reflect=False, **kwargs)

        for class_ in cls.classes:
            class_.__mapper__.has_pseudo_primary_key = \
                class_.__table__.key in pseudo_pkey_tables_names

    AutomapBase.prepare = prepare
    return AutomapBase


def orm_declarative_base(name='OrmBase', base_iri=None, mapper=None,
                         metaclass=_sqla_decl.DeclarativeMeta, **kwargs):
    DeclarativeBaseMeta = type('{}_DeclarativeBaseMeta'.format(name),
                               (OrmDeclarativeMetaMixin, metaclass), {})
    DeclarativeBase = \
        _sqla_decl.declarative_base(name=name,
                                    mapper=(mapper or _sqla_orm.mapper),
                                    metaclass=DeclarativeBaseMeta, **kwargs)
    DeclarativeBase.__base_iri__ = base_iri
    return DeclarativeBase


class OrmDeclarativeMetaMixin(type):
    def __new__(cls, name, bases, attrs):

        if all(name not in attrs for name in ('__str__', '__unicode__')):
            attrs['__unicode__'] = _orm_object_str

        class_ = super(OrmDeclarativeMetaMixin, cls).__new__(cls, name, bases,
                                                             attrs)

        try:
            rdf_mapper = attrs['__rdf_mapper__']
        except KeyError:
            attrs['__rdf_mapper__'] = None
        else:
            if rdf_mapper is None:
                class_.__rdf_mapper__ = OrmRdfMapper(class_)

        return class_


class OrmRdfMapper(object):

    def __init__(self, class_):
        self._class = class_

    @property
    def base_iri(self):
        return self.class_.__base_iri__

    @property
    def class_(self):
        return self._class

    @property
    def node(self):
        try:
            return self._node
        except AttributeError:
            if self.has_pseudo_primary_key:
                self._node = None
            else:
                pkey_rdf_items = \
                    [(_common.iri_safe(col.name),
                      _common.iri_safe
                       (_common.rdf_literal_from_sql(getattr(self, col.name),
                                                     sql_type=col.type)))
                     for col in self.__table__.primary_key.columns]
                self._node = \
                    _rdf.URIRef('/'.join((self.table_iri(),
                                          ';'.join('{}={}'.format(name, value)
                                                   for name, value
                                                   in pkey_rdf_items))))
            return self._node
            self._rdf_id = self.node if self.node is not None else _rdf.BNode()

    @property
    def has_pseudo_primary_key(self):
        return self.class_.__mapper__.has_pseudo_primary_key

    @property
    def rdf(self):
        try:
            return self._rdf
        except AttributeError:
            rdf = _rdf_res.Resource(self.rdf_graph, self.rdf_id)

            rdf.set(_rdf.RDF.type, self.table_iri())

            fkeys_colnames_by_target_tablename = {}
            for fkey in self.__table__.foreign_keys:
                fkeys_colnames_by_target_tablename\
                 .setdefault(fkey.column.table.name, fkey.constraint.columns)
            for target_tablename, colnames \
                    in fkeys_colnames_by_target_tablename.items():
                predicate_iri = \
                    _rdf.URIRef('{}#ref-{}'.format(self.table_iri(),
                                                   ';'.join(colnames)))
                try:
                    object_id = \
                        getattr(self, fkey.column.table.name.lower()).rdf_id
                except AttributeError:
                    pass
                else:
                    rdf.add(predicate_iri, object_id)

            for col in self.__table__.columns:
                predicate_iri = \
                    _rdf.URIRef('{}#{}'.format(self.table_iri(),
                                               _common.iri_safe(col.name)))
                value = getattr(self, col.name)
                if value is not None:
                    value_rdf = _common.rdf_literal_from_sql(value,
                                                             sql_type=col.type)
                    rdf.add(predicate_iri, value_rdf)

            self._rdf = rdf

            return self._rdf

    @property
    def rdf_graph(self):
        try:
            return self._rdf_graph
        except AttributeError:
            # FIXME
            self._rdf_graph = _rdf.Graph()
            return self._rdf_graph

    @property
    def rdf_id(self):
        try:
            return self._rdf_id
        except AttributeError:
            self._rdf_id = self.node if self.node is not None else _rdf.BNode()
            return self._rdf_id

    @classmethod
    def table_iri(cls):
        try:
            return cls._table_iri
        except AttributeError:
            cls._table_iri = \
                cls._prefixed_iri\
                 (_rdf.URIRef(_common.iri_safe(cls.__table__.name)))
            return cls._table_iri

    @classmethod
    def _prefixed_iri(cls, rel_iri):
        if cls.base_iri is not None:
            return _rdf.URIRef(''.join((cls.base_iri, rel_iri)))
        else:
            return rel_iri


class PseudoPrimaryKeyConstraint(_sqla.PrimaryKeyConstraint):
    pass


def _orm_object_str(self):
    return u'<{}>'.format(self.rdf_id)
