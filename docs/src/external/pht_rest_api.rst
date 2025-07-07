.. _pht_rest_api:

Proposal Handling Tool REST API
=================================

The PHT Services are made accessible via a RESTful API using FastAPI.

A SwaggerUI for the latest main branch of the API is available at

https://k8s.stfc.skao.int/integration-ska-oso-services/oso/api/v1/ui/

Existing endpoints:

Proposal management panel:

POST /panels
"Create a new panel or update the existing panel. Validation prevents duplicates in reviewers and proposals collections. Also, proposals and reviewers must have valid and existing IDs
Returns the panel_id."
