.. _pht_rest_api:

Proposal Handling Tool REST API
=================================

A SwaggerUI for the latest main branch of the API is available at

https://k8s.stfc.skao.int/integration-ska-oso-services/oso/api/v2/ui/


The API provides proposal preparation and management resources, including proposal creation, submission, review, and decision processes. 
Outlined below endpoints grouped by resources.

Proposal Preparation:
==========================

* Proposals:

.. openapi:: ./_static/proposal_only_openapi.json



Proposal Management:
==========================

- Panel Management:

.. openapi:: ./_static/panels_only_openapi.json


- Review Management:

.. openapi:: ./_static/reviews_only_openapi.json


- Decision Management:
  
.. openapi:: ./_static/panel_decision_only_openapi.json

- Reviewer Management:

.. openapi:: ./_static/reviewers_only_openapi.json


PHT Report:
==========================

- Proposal Management Report:

.. openapi:: ./_static/report_only_openapi.json


