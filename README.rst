#########
PyRDB2RDF
#########

PyRDB2RDF provides RDFLib_ with an interface to relational databases as
RDF_ stores_, accessed via SQLAlchemy_, and mapped to RDF according to
the specifications of RDB2RDF_.

Translating from relational data to RDF via `direct mapping`_ is
currently supported.  Translating in the other direction and mapping via
R2RML_ are planned but not yet supported.

.. _direct mapping: http://www.w3.org/TR/rdb-direct-mapping/

.. _R2RML: http://www.w3.org/TR/r2rml/

.. _RDB2RDF: http://www.w3.org/2001/sw/rdb2rdf/

.. _RDF: http://www.w3.org/TR/rdf11-concepts/

.. _RDFLib: http://rdflib.readthedocs.org/

.. _SQLAlchemy: http://www.sqlalchemy.org/

.. _stores: http://rdflib.readthedocs.org/en/latest/univrdfstore.html


************
Installation
************

.. code-block:: bash

    pip install rdb2rdf


********
Examples
********

Serializing a database as N-Triples
===================================

Suppose the local PostgreSQL_ database ``test_dm`` contains data that
we want to translate to RDF and serialize as N-Triples_.  The following
code achieves that.

.. _N-Triples: http://www.w3.org/TR/n-triples/

.. _PostgreSQL: http://www.postgresql.org/

.. code-block:: python

    import rdflib as _rdf
    import sqlalchemy as _sqla

    dm_db = _sqla.create_engine('postgresql://test:test@localhost/test_dm')
    dm_graph = _rdf.Graph('rdb2rdf_dm')
    dm_graph.open(dm_db)

    print(dm_graph.serialize(format='nt'))
