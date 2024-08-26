SKA OSO Common Services
========================================

This project provides common services used across OSO, accessible via RESTful APIs.
These will mainly be used by the Proposal Handling Tool (PHT) and the Observation Design Tool (ODT).

For an overview of the applications and functionality within OSO, see `Solution Intent <https://confluence.skatelescope.org/pages/viewpage.action?pageId=159387040>`_.

For information on deploying and configuring the application in a given Kubernetes or local environment, see the 'Deploying and configuring' section.

For user information for a deployed instance of this application, see the 'User Guide'.

For developer information, application internals, and information about interactions with other OSO applications, see the 'Application internals and developer information' section

For instructions on developing the application, see the `README <https://gitlab.com/ska-telescope/oso/ska-oso-services/-/blob/main/README.md>`_

.. toctree::
   :maxdepth: 1
   :caption: Releases
   :hidden:

   CHANGELOG.rst


.. toctree::
    :maxdepth: 2
    :caption: General
    :hidden:

    general/background.rst


.. toctree::
    :maxdepth: 2
    :caption: Deploying and configuring
    :hidden:

    deployment/environment_variables.rst
    deployment/deployment_to_kubernetes.rst
    deployment/persistent_environments.rst


.. toctree::
    :maxdepth: 2
    :caption: User Guide
    :hidden:

    external/odt_rest_api.rst


.. toctree::
    :maxdepth: 2
    :caption: Application internals and developer information
    :hidden:

    internal/module_view.rst
    internal/persistence.rst
    internal/prj_and_sbd.rst


