.. _validation:

Validation
==========================

The ``ska_oso_services.validation`` package contains semantic validation of OSO entities.

Each piece of validation is defined in an ``Validator`` function. These functions can then
all be applied to an entity and result of the validation is the collection of the results from
all the individual functions.

The ``ska_oso_services.model`` module defines the ``Validator`` function type, along with
some helper functions for applying and combining ``Validator``.

The other modules define validation for specific entities, with higher level entities using
combining validation for their elements.

The validation is exposed via the REST API - see the SwaggerUI for documentation.

.. toctree::
    :maxdepth: 1

    validation_python_docs/model
    validation_python_docs/sbdefinition
    validation_python_docs/target
    validation_python_docs/scans
