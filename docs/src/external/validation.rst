.. _validation:

Validation
==========================

The ``ska_oso_services.validation`` package contains semantic validation of OSO entities.

Each piece of validation is defined in an ``Validator`` function. These functions can then
be applied in turn to an entity and result of the validation is the collection of the results from
all the individual functions. Each ``Validator`` returns one or more ``ValidationIssue`` that contains a
validation message and the JSONPath of for the part of the input that is invalid.

The ``ska_oso_services.validation.model`` module defines the ``Validator`` function type, along with
some helper functions for applying and combining ``Validator``.

The other modules define validation for specific entities, with higher-level entities reusing
validation for their individual elements. For example ``ska_oso_services.validation.target`` and ``ska_oso_services.validation.csp_configuration``
contains validation of individual PDM ``Target`` and ``CSPConfiguration`` objects, respectively. Then ``ska_oso_services.validation.sbdefinition``
reuses the validation of each ``Target`` and ``CSPConfiguration`` it contains, while also defining new validation that
arises by combining the individual elements into scans.

The validation is exposed via the REST API - see the SwaggerUI for documentation.

.. toctree::
    :maxdepth: 1

    validation_python_docs/model
    validation_python_docs/sbdefinition
    validation_python_docs/target
    validation_python_docs/scans
