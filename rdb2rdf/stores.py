# -*- coding: utf-8 -*-
"""RDFLib stores

.. seealso:: :mod:`rdflib.store`, :mod:`rdflib.plugins.stores`

"""

__copyright__ = "Copyright (C) 2014 Ivan D Vasin"
__docformat__ = "restructuredtext"

from collections import deque as _deque
from functools import partial as _partial, reduce as _reduce
import json as _json
from operator import add as _add
import re as _re
from urllib import unquote as _pct_decoded

import rdflib as _rdf
from spruce.collections import frozendict as _frozendict
from spruce.types import require_isinstance as _require_isinstance
import spruce.iri.goose as _iri_goose
import sqlalchemy as _sqla
_sqlaf = _sqla.func
import sqlalchemy.orm as _sqla_orm

from . import _common
from . import dm as _dm


class DirectMapping(_rdf.store.Store):

    """SQLAlchemy RDB2RDF Direct Mapping store

    :param configuration:
        If non-null, this store's initialization will call
        :samp:`open({configuration})`.
    :type configuration:
        :class:`sqlalchemy.engine.interfaces.Connectable`
        or (~[object], ~{:obj:`str`: :obj:`object`} or null)
        or null

    :param id:
        The IRI of this store.
    :type id: ~~\ :class:`spruce.uri.duck.Uri` or null

    :param base_iri:
        The base IRI of this store's resources.  The default is
        :samp:`{id}/`.
    :type base_iri: ~~\ :class:`spruce.uri.duck.Uri` or null

    :param orm_classes:
        The ORM classes that constitute the domain of this mapping, indexed
        by IRI reference relative to the *base_iri*.  The default is the set
        of classes produced by :func:`rdf2rdb.dm.rdbconn2orm` using the
        connection produced by :meth:`open` with the given *configuration*,
        the *rdb_metadata*, and the *base_iri*, indexed by underlying table
        name.
    :type orm_classes: {:obj:`str`: :obj:`type`}

    :param orm:
        An ORM session.
    :type orm: :class:`sqlalchemy.orm.Session` or null

    .. _direct mapping: http://www.w3.org/TR/rdb-direct-mapping/

    .. _RDF: http://www.w3.org/TR/rdf11-concepts/

    .. _SQLAlchemy: http://www.w3.org/TR/rdf11-concepts/

    """

    def __init__(self, configuration=None, id=None, base_iri=None, rdb_metadata=None,
                 orm_classes=None, orm=None):

        self._id = id
        self._base_iri = base_iri if base_iri is not None else id

        self._namespaces = {}
        self._prefix_by_namespace = {}

        self._rdb = configuration
        self._rdb_metadata = rdb_metadata
        self._rdb_transaction = None

        self._orm = orm
        self.OrmBase = None
        self._orm_classes = orm_classes
        self._orm_mappers = None
        self._orm_columns_properties = None
        self._orm_columns_rdf_datatypes = None
        self._orm_relationships = None
        self._orm_bnode_tables = None

        if configuration:
            self.open(configuration)

    def __len__(self, context=None):

        if context is not None:
            return 0

        len_ = 0

        for subject_table_iri, subject_class in self._orm_classes.items():
            subject_cols_props = self._orm_columns_properties[subject_table_iri]
            subject_rels = self._orm_relationships[subject_table_iri]

            # sum:
            #   * 1 for each class statement (1 for each row)
            #   * 1 for each literal property statement (1 for each non-null
            #     attribute of each row)
            #   * 1 for each reference property statement (1 for each totally
            #     non-null foreign key value tuple of each row)
            len_ += \
                self._orm.query\
                 (_sqla.func.count(subject_class.__mapper__.primary_key[0])
                   + _reduce
                      (_add,
                       (_sqlaf.sum
                         (_sqla.case(((prop.class_attribute == None,
                                       _sqla.literal(0)),),
                                     else_=_sqla.literal(1)))
                        for prop in subject_cols_props.values()),
                       _sqla.literal(0))
                   + _reduce
                      (_add,
                       (_sqlaf.sum
                         (_sqla.case
                           (((_reduce
                               (_sqla.and_,
                                (subject_cols_props[colname].class_attribute
                                  != None
                                 for colname in colnames),
                                _sqla.literal(True)),
                              _sqla.literal(1)),
                             ),
                            else_=_sqla.literal(0)))
                        for colnames in subject_rels.keys()),
                       _sqla.literal(0)))\
                 .scalar()

        return len_

    def add(self, (subject, predicate, object), context=None, quoted=False):

        # FIXME

        super(DirectMapping, self).add((subject, predicate, object),
                                       context=context, quoted=quoted)

    def addN(self, quads):
        for subject, predicate, object, context in quads:
            self.add((subject, predicate, object), context=context)

    def add_graph(self, graph):
        # FIXME
        pass

    @property
    def base_iri(self):
        """The base IRI of this store.

        This IRI is used as a prefix for the class, resource, and property IRIs
        generated by this store's implementation of `direct mapping`_.

        .. _direct mapping: http://www.w3.org/TR/rdb-direct-mapping/

        :type: :obj:`str`

        """
        return self._base_iri

    @base_iri.setter
    def _(self, value):
        _require_isinstance(value, _iri_goose.UriReference)
        self._base_iri = value

    def bind(self, prefix, namespace):
        self._namespaces[prefix] = namespace
        self._prefix_by_namespace[namespace] = prefix

    def close(self, commit_pending_transaction=False):

        if self.is_open:
            if commit_pending_transaction:
                self.commit()
            else:
                self.rollback()

        self._orm.close_all()

    def commit(self):
        self._rdb_transaction.commit()
        self._rdb_transaction = self._rdb.begin().transaction

    context_aware = False

    def contexts(self, triple=None):
        return ()

    def create(self, configuration):
        rdb = self._rdb_from_configuration(configuration)
        self._rdb_metadata.create_all(bind=rdb, checkfirst=True)

    def destroy(self, config):
        # FIXME
        pass

    formula_aware = False

    graph_aware = False

    @property
    def id(self):
        return self._id

    @property
    def is_open(self):
        return self._rdb_transaction.is_active

    def namespace(self, prefix):
        try:
            return self._namespaces[prefix]
        except KeyError:
            return None

    def namespaces(self):
        return self._namespaces.items()

    def open(self, configuration, create=False, reflect=True):

        self._rdb = self._rdb_from_configuration(configuration)

        if create and self._rdb_metadata:
            self.create(self._rdb)

        if self._orm_classes is None:
            self.OrmBase = _dm.orm_automap_base(name='OrmBase',
                                                base_iri=self.base_iri,
                                                bind=self._rdb,
                                                metadata=self._rdb_metadata)
            self.OrmBase.prepare(reflect=reflect)
            self._rdb_metadata = self.OrmBase.metadata
            self._orm_classes = \
                _frozendict((self._table_iri(class_.__table__.name), class_)
                            for class_ in self.OrmBase.classes)

        if self._orm_mappers is None:
            mappers_items = []
            colprops_items = []
            cols_datatypes_items = []
            rels_items = []
            bnode_tables = set()
            for table_iri, class_ in self._orm_classes.items():
                class_mapper = _sqla.inspect(class_)
                props = _orm_column_property_by_name(mapper=class_mapper)

                mappers_items.append((table_iri, class_mapper))
                colprops_items.append((table_iri, props))
                cols_datatypes_items\
                 .append((table_iri,
                          {colname: _common.canon_rdf_datatype_from_sql
                                     (prop.columns[0].type)
                           for colname, prop in props.items()}))
                rels_items\
                 .append((table_iri,
                          _orm_relationship_by_local_column_names
                           (mapper=class_mapper)))
                if class_mapper.has_pseudo_primary_key:
                    bnode_tables.add(table_iri)
            self._orm_mappers = _frozendict(mappers_items)
            self._orm_columns_properties = _frozendict(colprops_items)
            self._orm_columns_rdf_datatypes = _frozendict(cols_datatypes_items)
            self._orm_relationships = _frozendict(rels_items)
            self._orm_bnode_tables = frozenset(bnode_tables)

        if self._orm is None:
            self._orm = _sqla_orm.sessionmaker(bind=self._rdb)()
        self._rdb_transaction = self._rdb.begin().transaction

    @property
    def orm_classes(self):
        return self._orm_classes

    def prefix(self, namespace):
        try:
            return self._prefix_by_namespace[namespace]
        except KeyError:
            return None

    def remove(self, (subject, predicate, object), context=None):

        # FIXME

        super(DirectMapping, self).remove((subject, predicate, object),
                                          context=context)

    def rollback(self):
        self._rdb_transaction.rollback()

    transaction_aware = True

    def triples(self, (subject_pattern, predicate_pattern, object_pattern),
                context=None):

        """Match triples.

        :param subject_pattern:
            Match triples' subjects against this pattern as follows:

              value of type :class:`rdflib.URIRef`
                Match the subject with this identifier.

              :obj:`None`
                Match any subject.

              else
                Match nothing.
        :type subject_pattern: object

        :param predicate_pattern:
            Match triples' predicates against this pattern as follows:

              value of type :class:`rdflib.URIRef`
                Match the predicate with this identifier.

              :obj:`None`
                Match any predicate.

              else
                Match nothing.
        :type predicate_pattern: object

        :param object_pattern:
            Match triples' objects against this pattern as follows:

              value of type :class:`rdflib.URIRef`
                Match the object with this identifier.

              value of type :class:`rdflib.Literal` or :class:`rdflib.Date` or
              :class:`rdflib.DateRange`
                Match this literal value.

              value of type :class:`rdflib.REGEXTerm`
                Match any literal value that matches this pattern.

              :obj:`None`
                Match any object.

              else
                Match nothing.
        :type object_pattern: object

        :param context:
            Match triples in this context as follows:

              :obj:`None`
                Match triples in the default context.

              else
                Match nothing.
        :type context: object

        :return:
            The matching triples.
        :rtype: ~[(:class:`rdflib.URIRef` or :class:`rdflib.BNode`,
                   :class:`rdflib.URIRef`,
                   :class:`rdflib.URIRef` or :class:`rdflib.BNode`
                     or :class:`rdflib.Literal` or :class:`rdflib.Date`
                     or :class:`rdflib.DateRange`)]

        """

        if context is not None \
               and not (isinstance(context, _rdf.Graph)
                        and isinstance(context.identifier, _rdf.BNode)):
            return

        if subject_pattern is None:
            if predicate_pattern is None:
                for subject_table_iri in self._orm_classes.keys():
                    for triple \
                            in self._table_allpredicates_triples\
                                (subject_table_iri, object_pattern):
                        yield triple, None

            elif predicate_pattern == _rdf.RDF.type:
                if object_pattern is None:
                    for subject_table_iri in self._orm_classes.keys():
                        for triple \
                                in self._table_type_triples(subject_table_iri):
                            yield triple, None
                elif isinstance(object_pattern, _rdf.URIRef):
                    for triple in self._table_type_triples(object_pattern):
                        yield triple, None
                else:
                    return

            elif isinstance(predicate_pattern, _rdf.URIRef):
                try:
                    predicate_attr = \
                        self._predicate_orm_attr(predicate_pattern)
                except ValueError:
                    return
                predicate_prop = predicate_attr.property
                subject_table_iri = \
                    self._table_iri(predicate_prop.parent.mapped_table)

                for triple in self._table_predicate_triples(subject_table_iri,
                                                            predicate_pattern,
                                                            object_pattern):
                    yield triple, None

            else:
                return

        elif isinstance(subject_pattern, (_rdf.URIRef, _rdf.BNode)):
            for triple in self._subject_triples(subject_pattern,
                                                predicate_pattern,
                                                object_pattern):
                yield triple, None

        else:
            return

    transaction_aware = True

    def _literal_property_iri(self, table_iri, colname):
        return _rdf.URIRef(u'{}#{}'.format(table_iri,
                                           _common.iri_safe(colname)))

    def _parse_row_node(self, node):

        try:
            table_iri_str, _, pkeyspec = node.rpartition('/')
        except AttributeError:
            raise TypeError(u'invalid row node {!r}: not a string'
                             .format(node))

        if not table_iri_str or '=' not in pkeyspec:
            raise ValueError\
                   (u'invalid row node {!r}: does not match format {!r}'
                     .format(node, 'table/colname=value[;colname=value]...'))

        table_iri = _rdf.URIRef(table_iri_str)

        if table_iri in self._orm_bnode_tables:
            if not isinstance(node, _rdf.BNode):
                raise ValueError('invalid node type {!r} for blank node table'
                                  ' {!r}: not blank node'
                                  .format(node.__class__, table_iri))
        else:
            if not isinstance(node, _rdf.URIRef):
                raise ValueError('invalid node type {!r} for IRI node table'
                                  ' {!r}: not IRI node'
                                  .format(node.__class__, table_iri))

        pkey = {}
        cols_props = self._orm_columns_properties[table_iri]
        cols_datatypes = self._orm_columns_rdf_datatypes[table_iri]
        for name_irisafe, value_irisafe in (item.split('=')
                                            for item in pkeyspec.split(';')):
            colname = _pct_decoded(name_irisafe)
            value_rdf = _rdf.Literal(_pct_decoded(value_irisafe),
                                     datatype=cols_datatypes[colname])
            pkey[cols_props[colname].class_attribute] = \
                _common.sql_literal_from_rdf(value_rdf)

        return table_iri, pkey

    def _predicate_orm_attr(self, iri):

        try:
            table_iri_str, _, colspec = iri.partition('#')
        except AttributeError:
            raise TypeError(u'invalid predicate IRI {!r}: not a string'
                             .format(iri))

        if not table_iri_str or not colspec:
            raise ValueError(u'invalid predicate IRI {!r}:'
                              u' does not match either format {!r}'
                              .format(iri,
                                      ('table#colname',
                                       'table#ref-colname[;colname]...')))

        table_iri = _rdf.URIRef(table_iri_str)

        if colspec.startswith('ref-'):
            cols = frozenset(_pct_decoded(colname)
                             for colname in colspec[4:].split(';'))
            try:
                prop = self._orm_relationships[table_iri][cols]
            except KeyError:
                raise ValueError('unknown reference property {!r}'.format(iri))

        else:
            col = _pct_decoded(colspec)
            try:
                prop = self._orm_columns_properties[table_iri][col]
            except KeyError:
                raise ValueError('unknown literal property {!r}'.format(iri))

        return prop.class_attribute

    def _prefixed_iri(self, rel_iri):

        if self.base_iri is not None:
            return _rdf.URIRef(u'{}{}'.format(self.base_iri, rel_iri))

        return _rdf.URIRef(rel_iri)

    def _rdb_from_configuration(self, configuration):

        if isinstance(configuration, _sqla.engine.interfaces.Connectable):
            return configuration

        elif isinstance(configuration, basestring):
            try:
                parts = _json.loads(configuration)
            except TypeError as exc:
                raise TypeError('invalid configuration type {!r}: {}'
                                 .format(type(configuration), exc))
            except ValueError as exc:
                raise ValueError('invalid configuration {!r}: {}'
                                  .format(configuration, exc))

            if len(parts) > 2:
                raise ValueError('invalid configuration {!r}: expecting a JSON'
                                  ' sequence of two or less items'
                                  .format(configuration))

            if parts:
                rdb_args = parts[0]
            else:
                rdb_args = ()

            if len(parts) == 2:
                rdb_kwargs = parts[1]
            else:
                rdb_kwargs = {}

        else:
            try:
                rdb_args, rdb_kwargs = configuration
            except TypeError as exc:
                raise TypeError('invalid configuration type {!r}: {}'
                                 .format(type(configuration), exc))
            except ValueError as exc:
                raise ValueError('invalid configuration {!r}: {}'
                                  .format(configuration, exc))

        return _sqla.create_engine(*rdb_args, **rdb_kwargs)

    def _ref_property_iri(self, table_iri, fkey_colnames):
        return _rdf.URIRef(u'{}#ref-{}'
                            .format(table_iri,
                                    ';'.join(_common.iri_safe(colname)
                                             for colname
                                             in fkey_colnames)))

    def _row_bnode_from_sql(self, table_iri, pkey_items):
        return _rdf.BNode(self._row_str_from_sql(table_iri, pkey_items))

    def _row_iri_from_sql(self, table_iri, pkey_items):
        return _rdf.URIRef(self._row_str_from_sql(table_iri, pkey_items))

    def _row_node_from_sql(self, table_iri, pkey_items):
        return self._row_node_from_sql_func(table_iri)(pkey_items)

    def _row_node_from_sql_func(self, table_iri):
        if table_iri in self._orm_bnode_tables:
            return _partial(self._row_bnode_from_sql, table_iri)
        else:
            return _partial(self._row_iri_from_sql, table_iri)

    def _row_str_from_sql(self, table_iri, pkey_items):
        return u'{}/{}'\
                .format(table_iri,
                        ';'.join(u'{}={}'
                                  .format(_common.iri_safe(col.name),
                                          _common.iri_safe
                                           (_common.rdf_literal_from_sql
                                             (value, sql_type=col.type)))
                                 for col, value in pkey_items))

    def _subject_triples(self, subject_node, predicate_pattern,
                         object_pattern):

        try:
            subject_table_iri, subject_pkey = \
                self._parse_row_node(subject_node)
        except (TypeError, ValueError):
            return
        subject_class = self._orm_classes[subject_table_iri]
        subject_cols_props = \
            self._orm_columns_properties[subject_table_iri]

        query = self._orm.query(subject_class)\
                         .filter(*(attr == value
                                   for attr, value
                                   in subject_pkey.items()))

        if predicate_pattern is None:
            if object_pattern is None:
                # IRI, *, *

                subject_mapper = self._orm_mappers[subject_table_iri]
                subject_cols = subject_mapper.columns
                subject_cols_props = \
                    self._orm_columns_properties[subject_table_iri]
                subject_rels = \
                    self._orm_relationships[subject_table_iri].values()

                query = query.with_entities()

                for predicate_col in subject_cols:
                    predicate_colname = predicate_col.name
                    predicate_iri = \
                        self._literal_property_iri(subject_table_iri,
                                                   predicate_colname)
                    predicate_prop = subject_cols_props[predicate_colname]
                    predicate_attr = predicate_prop.class_attribute

                    query = query.add_columns(predicate_attr)

                for predicate_prop in subject_rels:
                    object_table = predicate_prop.target
                    object_table_iri = self._table_iri(object_table.name)
                    object_cols_props = \
                        self._orm_columns_properties[object_table_iri]
                    object_pkey_attrs = \
                        [object_cols_props[col.name].class_attribute
                         for col
                         in object_table.primary_key.columns]

                    query = query.outerjoin(predicate_prop.class_attribute)\
                                 .add_columns(*object_pkey_attrs)

                query_result_values = query.first()
                query_result_values_pending = _deque(query_result_values)
                subject_cols_values = \
                    [query_result_values_pending.popleft()
                     for _ in range(len(subject_cols))]

                yield (subject_node, _rdf.RDF.type, subject_table_iri)

                for predicate_col, object_value \
                        in zip(subject_cols, subject_cols_values):

                    if object_value is None:
                        continue

                    predicate_iri = \
                        self._literal_property_iri(subject_table_iri,
                                                   predicate_col.name)

                    yield (subject_node,
                           predicate_iri,
                           _common.rdf_literal_from_sql
                            (object_value,
                             sql_type=predicate_col.type))

                for predicate_prop in subject_rels:
                    object_table = predicate_prop.target
                    object_pkey_cols = object_table.primary_key.columns
                    object_pkey_values = \
                        [query_result_values_pending.popleft()
                         for _ in range(len(object_pkey_cols))]
                    object_node_from_sql = \
                        self._row_node_from_sql_func\
                         (self._table_iri(object_table.name))

                    if any(value is None for value in object_pkey_values):
                        continue

                    predicate_iri = \
                        self._ref_property_iri\
                         (subject_table_iri,
                          (col.name
                           for col in predicate_prop.local_columns))

                    yield (subject_node,
                           predicate_iri,
                           object_node_from_sql(zip(object_pkey_cols,
                                                    object_pkey_values)))

            elif isinstance(object_pattern, _rdf.Literal):
                # IRI, *, literal

                subject_mapper = self._orm_mappers[subject_table_iri]
                subject_cols_props = \
                    self._orm_columns_properties[subject_table_iri]
                object_sql_types = \
                    _common.sql_literal_types_from_rdf\
                     (object_pattern.datatype)

                for predicate_col in subject_mapper.columns:
                    predicate_sql_type = predicate_col.type
                    if isinstance(predicate_sql_type, object_sql_types):
                        predicate_colname = predicate_col.name
                        predicate_prop = \
                            subject_cols_props[predicate_colname]
                        predicate_attr = predicate_prop.class_attribute
                        object_sql_literal = \
                            _common.sql_literal_from_rdf(object_pattern)
                        query_cand = \
                            query.filter(predicate_attr
                                          == object_sql_literal)

                        if self._orm.query(query_cand.exists()).scalar():
                            predicate_iri = \
                                self._literal_property_iri\
                                 (subject_table_iri, predicate_colname)
                            yield (subject_node, predicate_iri, object_pattern)

            elif isinstance(object_pattern, _rdf.URIRef):
                # IRI, *, IRI

                if object_pattern == subject_table_iri:
                    if self._orm.query(query.exists()).scalar():
                        yield (subject_node, _rdf.RDF.type, subject_table_iri)
                    return

                try:
                    object_table_iri, object_pkey = \
                        self._parse_row_node(object_pattern)
                except (TypeError, ValueError):
                    return

                subject_rels = self._orm_relationships[subject_table_iri]
                object_cols_props = \
                    self._orm_columns_properties[object_table_iri]

                for predicate_prop in subject_rels.values():
                    query_cand = \
                        query.join(predicate_prop.class_attribute)\
                             .filter(*(attr == value
                                       for attr, value
                                       in object_pkey.items()))
                    if self._orm.query(query_cand.exists()).scalar():
                        predicate_iri = \
                            self._ref_property_iri\
                             (subject_table_iri,
                              (col.name
                               for col in predicate_prop.local_columns))
                        yield (subject_node, predicate_iri, object_pattern)

            else:
                return

        elif predicate_pattern == _rdf.RDF.type:
            if object_pattern is None \
                   or (isinstance(object_pattern, _rdf.URIRef)
                       and object_pattern == subject_table_iri):
                if self._orm.query(query.exists()).scalar():
                    yield (subject_node, _rdf.RDF.type, subject_table_iri)

        elif isinstance(predicate_pattern, _rdf.URIRef):
            try:
                predicate_attr = \
                    self._predicate_orm_attr(predicate_pattern)
            except ValueError:
                return
            predicate_prop = predicate_attr.property

            if isinstance(predicate_prop, _sqla_orm.RelationshipProperty):
                if object_pattern is None:
                    # IRI, ref IRI, *

                    object_table = predicate_prop.target
                    object_table_iri = self._table_iri(object_table.name)
                    object_pkey_cols = object_table.primary_key.columns

                    query = \
                        query.join(predicate_attr)\
                             .with_entities(*object_pkey_cols)
                    for object_pkey_values in query.all():
                        yield (subject_node,
                               predicate_pattern,
                               self._row_iri_from_sql(object_table_iri,
                                                      zip(object_pkey_cols,
                                                          object_pkey_values)))

                elif isinstance(object_pattern, _rdf.URIRef):
                    # IRI, ref IRI, IRI

                    try:
                        object_table_iri, object_pkey = \
                            self._parse_row_node(object_pattern)
                    except (TypeError, ValueError):
                        return

                    object_cols_props = \
                        self._orm_columns_properties[object_table_iri]

                    query = query.join(predicate_attr)\
                                 .filter(*(attr == value
                                           for attr, value
                                           in object_pkey.items()))

                    if self._orm.query(query.exists()).scalar():
                        yield (subject_node, predicate_pattern, object_pattern)
                    else:
                        return

                else:
                    return

            else:
                predicate_col, = predicate_attr.property.columns

                if object_pattern is None:
                    # IRI, non-ref IRI, *
                    query = query.with_entities(predicate_attr)\
                                 .filter(predicate_attr != None)
                    for value, in query.all():
                        yield (subject_node, predicate_pattern,
                               _common.rdf_literal_from_sql
                                (value, sql_type=predicate_col.type))

                elif isinstance(object_pattern, _rdf.Literal):
                    # IRI, non-ref IRI, literal

                    if object_pattern.datatype \
                           not in _common.rdf_datatypes_from_sql\
                                   (predicate_col.type):
                        return

                    object_sql_literal = \
                        _common.sql_literal_from_rdf(object_pattern)
                    query = \
                        query.filter(predicate_attr != None,
                                     predicate_attr == object_sql_literal)

                    if self._orm.query(query.exists()).scalar():
                        yield (subject_node, predicate_pattern, object_pattern)

                else:
                    return

        else:
            return

    def _table_iri(self, tablename):
        return self._prefixed_iri(_common.iri_safe(tablename))

    def _table_allpredicates_triples(self, table_iri, object_pattern):

        subject_mapper = self._orm_mappers[table_iri]
        subject_pkey_cols = subject_mapper.primary_key
        subject_node_from_sql = self._row_node_from_sql_func(table_iri)

        query = self._orm.query(*subject_pkey_cols)

        if object_pattern is None:
            # *(IRI), *, *

            subject_mapper = self._orm_mappers[table_iri]
            subject_cols = subject_mapper.columns
            subject_cols_props = self._orm_columns_properties[table_iri]
            subject_rels = self._orm_relationships[table_iri].values()

            query = query.with_entities()

            for predicate_col in subject_cols:
                predicate_prop = subject_cols_props[predicate_col.name]
                predicate_attr = predicate_prop.class_attribute

                query = query.add_columns(predicate_attr)

            for predicate_prop in subject_rels:
                object_table = predicate_prop.target
                object_table_iri = self._table_iri(object_table.name)
                object_cols_props = \
                    self._orm_columns_properties[object_table_iri]
                predicate_attr = predicate_prop.class_attribute

                query = \
                    query.outerjoin(predicate_attr)\
                         .add_columns(*(object_cols_props[col.name]
                                         .class_attribute
                                        for col
                                        in object_table.primary_key.columns))

            for query_result_values in query.all():
                query_result_values_pending = _deque(query_result_values)
                subject_cols_values = [query_result_values_pending.popleft()
                                       for _ in range(len(subject_cols))]
                subject_pkey_values = (subject_cols_values[i]
                                       for i, col in enumerate(subject_cols)
                                       if col in subject_pkey_cols)
                subject_node = subject_node_from_sql(zip(subject_pkey_cols,
                                                         subject_pkey_values))

                yield (subject_node, _rdf.RDF.type, table_iri)

                for predicate_col, object_value in zip(subject_cols,
                                                       subject_cols_values):

                    if object_value is None:
                        continue

                    predicate_iri = \
                        self._literal_property_iri(table_iri,
                                                   predicate_col.name)

                    yield (subject_node, predicate_iri,
                           _common.rdf_literal_from_sql
                            (object_value, sql_type=predicate_col.type))

                for predicate_prop in subject_rels:
                    object_table = predicate_prop.target
                    object_pkey_cols = object_table.primary_key.columns
                    object_pkey_values = \
                        [query_result_values_pending.popleft()
                         for _ in range(len(object_pkey_cols))]

                    if any(value is None for value in object_pkey_values):
                        continue

                    predicate_iri = \
                        self._ref_property_iri\
                         (table_iri,
                          (col.name for col in predicate_prop.local_columns))

                    yield (subject_node,
                           predicate_iri,
                           self._row_node_from_sql\
                            (self._table_iri(object_table.name),
                             zip(object_pkey_cols, object_pkey_values)))

        elif isinstance(object_pattern, _rdf.Literal):
            # *(IRI), *, literal

            subject_cols_props = \
                self._orm_columns_properties[table_iri]
            object_sql_types = \
                _common.sql_literal_types_from_rdf(object_pattern.datatype)

            for predicate_col in subject_mapper.columns:
                predicate_sql_type = predicate_col.type
                if isinstance(predicate_sql_type, object_sql_types):
                    predicate_colname = predicate_col.name
                    predicate_iri = \
                        self._literal_property_iri(table_iri,
                                                   predicate_colname)
                    predicate_prop = subject_cols_props[predicate_colname]
                    predicate_attr = predicate_prop.class_attribute
                    object_sql_literal = \
                        _common.sql_literal_from_rdf(object_pattern)
                    query_cand = \
                        query.filter(predicate_attr == object_sql_literal)

                    for subject_pkey_values in query_cand.all():
                        yield (subject_node_from_sql(zip(subject_pkey_cols,
                                                         subject_pkey_values)),
                               predicate_iri, object_pattern)

        elif isinstance(object_pattern, (_rdf.URIRef, _rdf.BNode)):
            # *(IRI), *, IRI

            if object_pattern == table_iri:
                for subject_pkey_values in query.all():
                    yield (subject_node_from_sql(zip(subject_pkey_cols,
                                                     subject_pkey_values)),
                           _rdf.RDF.type, table_iri)
                return

            try:
                object_table_iri, object_pkey = \
                    self._parse_row_node(object_pattern)
            except (TypeError, ValueError):
                return

            subject_rels = self._orm_relationships[table_iri]
            object_cols_props = self._orm_columns_properties[object_table_iri]

            for predicate_prop in subject_rels.values():
                predicate_iri = \
                    self._ref_property_iri(table_iri,
                                           (col.name
                                            for col
                                            in predicate_prop.local_columns))

                query_cand = \
                    query.join(predicate_prop.class_attribute)\
                         .filter(*(attr == value
                                   for attr, value in object_pkey.items()))
                for subject_pkey_values in query_cand.all():
                    yield (subject_node_from_sql(zip(subject_pkey_cols,
                                                     subject_pkey_values)),
                           predicate_iri, object_pattern)

        else:
            return

    def _table_predicate_triples(self, table_iri, predicate_iri,
                                 object_pattern):

        subject_mapper = self._orm_mappers[table_iri]
        subject_pkey_cols = subject_mapper.primary_key
        subject_pkey_len = len(subject_pkey_cols)
        subject_node_from_sql = self._row_node_from_sql_func(table_iri)
        try:
            predicate_attr = self._predicate_orm_attr(predicate_iri)
        except ValueError:
            return
        predicate_prop = predicate_attr.property

        query = self._orm.query(*subject_pkey_cols)

        if isinstance(predicate_prop, _sqla_orm.RelationshipProperty):
            if object_pattern is None:
                # *, ref IRI, *

                object_table = predicate_prop.target
                object_pkey_cols = object_table.primary_key.columns
                object_node_from_sql = \
                    self._row_node_from_sql_func\
                     (self._table_iri(object_table.name))

                query = query.join(predicate_attr)\
                             .add_columns(*object_pkey_cols)

                for result_values in query.all():
                    subject_pkey_values = result_values[:subject_pkey_len]
                    object_pkey_values = result_values[subject_pkey_len:]
                    yield (subject_node_from_sql(zip(subject_pkey_cols,
                                                     subject_pkey_values)),
                           predicate_iri,
                           object_node_from_sql(zip(object_pkey_cols,
                                                    object_pkey_values)))

            elif isinstance(object_pattern, (_rdf.URIRef, _rdf.BNode)):
                # *, ref IRI, node

                try:
                    object_table_iri, object_pkey = \
                        self._parse_row_node(object_pattern)
                except (TypeError, ValueError):
                    return

                query = query.join(predicate_attr)\
                             .filter(*(attr == value
                                       for attr, value
                                       in object_pkey.items()))

                for subject_pkey_values in query.all():
                    yield (subject_node_from_sql(zip(subject_pkey_cols,
                                                     subject_pkey_values)),
                           predicate_iri,
                           object_pattern)

            else:
                return

        else:
            predicate_col, = predicate_attr.property.columns
            object_sql_type = predicate_col.type

            query = query.add_columns(predicate_attr)\
                         .filter(predicate_attr != None)

            if isinstance(object_pattern, _rdf.Literal):
                # *(IRI), non-ref IRI, literal

                if object_pattern.datatype \
                       not in _common.rdf_datatypes_from_sql(object_sql_type):
                    return

                object_sql_literal = \
                    _common.sql_literal_from_rdf(object_pattern)
                query = query.filter(predicate_attr == object_sql_literal)

            if object_pattern is None \
                 or isinstance(object_pattern, _rdf.Literal):
                # *(IRI), non-ref IRI, *
                query = query.add_columns(predicate_attr)
                for result_values in query.all():
                    yield (subject_node_from_sql
                            (zip(subject_pkey_cols,
                                 result_values[:subject_pkey_len])),
                           predicate_iri,
                           _common.rdf_literal_from_sql
                            (result_values[-1], sql_type=predicate_col.type))

            else:
                return

    def _table_type_triples(self, table_iri):

        try:
            table_orm_mapper = self._orm_mappers[table_iri]
        except KeyError:
            return

        subject_pkey_cols = table_orm_mapper.primary_key
        subject_node_from_sql = self._row_node_from_sql_func(table_iri)

        query = self._orm.query(*subject_pkey_cols)
        for subject_pkey_values in query.all():
            yield (subject_node_from_sql(zip(subject_pkey_cols,
                                             subject_pkey_values)),
                   _rdf.RDF.type, table_iri)

    def _unprefixed_iri(self, iri):

        if self.base_iri is not None:
            base_iri_match = \
                _re.match('{}(.*)'.format(_re.escape(self.base_iri)))
            if base_iri_match:
                return _rdf.URIRef(base_iri_match.group(1))

        return _rdf.URIRef(iri)


def _orm_column_property_by_name(mapper):
    return _frozendict((prop.key, prop) for prop in mapper.column_attrs)


def _orm_relationship_by_local_column_names(mapper):
    return _frozendict((frozenset(col.name for col in rel.local_columns),
                        rel)
                       for rel in mapper.relationships
                       if not rel.collection_class)


def _orm_relationship_remote_column_name_by_local_name(mapper):
    return _frozendict((rel, _frozendict((local_col.name, remote_col.name)
                                         for local_col, remote_col
                                         in rel.local_remote_pairs))
                        for rel in mapper.relationships
                        if not rel.collection_class)
