.. _pht_rest_api:

Proposal Handling Tool REST API
=================================

The PHT Services are made accessible via a RESTful API using FastAPI.

A SwaggerUI for the latest main branch of the API is available at

https://k8s.stfc.skao.int/integration-ska-oso-services/oso/api/v1/ui/

The API supports resources for: 

* Creating a Proposal
* Retrieve an existing Proposal
* Update an existing Proposal
* Retrieve a list of proposals for a specified user
* Validate a proposal
* Send SKAO email asynchronously via SMTP
* Upload PDF
* Download PDF
* Delete PDF
* Retrieve a list of reviewers