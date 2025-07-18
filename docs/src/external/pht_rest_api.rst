.. _pht_rest_api:

Proposal Handling Tool REST API
=================================

The PHT Services are made accessible via a RESTful API using FastAPI.

A SwaggerUI for the latest main branch of the API is available at

https://k8s.stfc.skao.int/integration-ska-oso-services/oso/api/v1/ui/

The API supports resources for: 

* Proposal Preparation: 

  - Creating a Proposal: 
    POST `/prsls` "The request body contains the proposal information. Returns the created proposal ID."
  - Retrieve an existing Proposal: 
    GET `/prsls/{prsl_id}` "Returns the proposal information including ID, title, status, and other details."
  - Update an existing Proposal: 
    PUT `/prsls/{prsl_id}` "The request body contains the updated proposal information. Returns the updated proposal."
  - Retrieve a list of proposals for a specified user: 
    GET `/prsls/{user_id}` "The response includes proposal IDs, titles, and statuses for each proposal."
  - Validate a submitted proposal: 
    POST `/validate` "The request body contains the proposal information to be submitted. Returns validation results."
  - Send SKAO email asynchronously: 
    POST `/email` "The request body contains the email information. Returns the send status."
  - Generate presigned S3 upload URL for the given filename: 
    POST `/presigned-url/upload` "The request body contains the filename. Returns the presigned URL for upload."
  - Generate presigned S3 download URL for the given filename: 
    POST `/presigned-url/download` "The request body contains the filename. Returns the presigned URL for download."
  - Generate presigned S3 delete URL for the given filename: 
    POST `/presigned-url/delete` "The request body contains the filename. Returns the presigned URL for deletion."
  - Retrieve a list of reviewers (Currently mocked):
    GET `/reviewers` "Returns a list of reviewers with their IDs and names."
  - GET `/osd/{cycle}` "Get OSD data per cycle""

* Proposal Management:
  
  - Creating proposal Reviews: 
    POST `/reviews` "The request body contains the review information. Returns the created review ID."
  - Retrieve an existing proposal Reviews: 
    GET `/reviews/{review_id}` "Returns the review information including proposal ID, reviewer ID, and review status."
  - Update an existing proposal Reviews: 
    PUT `/reviews/{review_id}` "The request body contains the updated review information. Returns the updated review."
  - Retrieve a list of proposal Reviews for a specified user:
    GET `/reviews/{user_id}` "The response includes review IDs, proposal IDs, and review statuses for each review."
  - Creating a proposal Decision: 
    POST `/panel-decisions` "The request body contains the decision information. Returns the created decision ID."
  - Retrieve an existing proposal Decision: 
    GET `/panel-decisions/{decision_id}`"
  - Update an existing proposal Decision: 
    PUT `/panel-decisions/{decision_id}` "The request body contains the updated decision information. Returns the updated decision."
  - Retrieve a list of proposal Decisions for a specified user: 
    GET `/panel-decisions/{user_id}` "The response includes decision IDs, proposal IDs, and decision statuses for each decision."
  - Creating a panel or updating an existing panel : POST `/panels` "Validation prevents duplicates in reviewers and proposals collections. Additionally, proposals and reviewers must have valid and existing IDs Returns the panel_id."
  - Retrieve an existing panel
  - Retrieve a list of panels for a specified user:
    GET `/panels/{user_id}` "The response includes panel IDs, names, reviewer IDs, and proposal IDs for each panel."
  - Retrieve a report for the PHT admin dashboard: GET `/report` "Returns a list of proposals with their associated panels, reviews, and decisions. The response includes proposal IDs, titles, panel IDs, review statuses, and decision statuses for each proposal. This endpoint is intended for administrative use to monitor proposal handling activities."

