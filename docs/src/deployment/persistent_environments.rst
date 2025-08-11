.. _persistent_environments:

Persistent Environments
=========================

Similar to other applications, there are several deployments of the application via CICD pipelines.

Integration
------------

The integration environment deploys the **latest main branch version** of the application, and is triggered by every
commit to the main branch. It should always be available at

https://k8s.stfc.skao.int/integration-ska-oso-services/oso/api/v2/ui/

Staging
--------

The integration environment deploys the **latest released branch version** of the application, and is triggered by every
commit to the main branch. It should always be available at

https://k8s.stfc.skao.int/staging-ska-oso-services/oso/api/v1/ui/

ska-oso-integration
---------------------

`ska-oso-integration <https://developer.skao.int/projects/ska-oso-integration/en/latest/?badge=latest>`_ is a separate environment
deployed by its own pipeline for stable, released versions of OSO services that are integrated with the other OSO applications.

