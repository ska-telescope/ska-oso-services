Changelog
==========

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

Unreleased
***********

1.3.0
***********
* Updated OSD data endpoint and introduced a model to OSD dict
* Updated `/reports/{user_id}` to `/reports/` so no user_id is required
* Updated `/reviews/{panel_id}` to `/reviews/{prsl_id}` to query by proposal id and not panel_id
* Added `/status/{status}` so Proposal management admin/coordinator can get all submitted proposals
* Added `/batch` to retrieve a list of proposals based on supplied list of proposal ids

1.2.0
***********
* Added ska-ser-xray as a dev dependency
* Added documentation for proposal endpoints
* Updated docker base images to ska-build-python v0.3.1 and ska-python v0.2.3 and regenerated poetry.lock
* Added PHT GET endpoint to retrieve osd data by cycle
* Added a POST `/odt/prsls/{prsl_id}/generateProject` API endpoint 
* Added a GET API endpoint `/report` to retrieve needed data for admin PHT dashboard
* Added a API endpoints to create, retrieve and update `panels` for the PHT
* Added a API endpoints to create, retrieve and update `reviews` for the PHT
* Added a API endpoints to create, retrieve and update `panel decision` for the PHT
* Added API `/odt/prjs/{prj_id}/generateSBDefinitions` & `/odt/prjs/{prj_id}/{obs_block_id}/generateSBDefinitions` 
  endpoints to generates SBDefinitions from Projects
* Added a GET `/reviews/{panel_id}` endpoint to retrieve all the reviews for a particular panel

1.1.0
****** 
* Added all pht endpoints:
  - Updated the ska-oso-oda version to v8.0.0
  - POST endpoint to create a proposal
  - PUT endpoint to update a proposal
  - GET endpoint to retrieve a proposal by proposal ID
  - GET endpoint to retrieve a list proposal by user
  - Validate POST endpoint to validate a proposal
  - POST Email and pdfs endpoints to send emails and generate signed urls for upload, download and delete actions.

1.0.1
****** 
* Add 'api://' prefix to the audience used by AAA

1.0.0
***********
* [BREAKING] AAA now enforced on all API resources. A valid JWT token with the correct scope, audience and group membership must be sent in the Authorization
  header for all requests. See ``ska-aaa-authhelpers`` and Solution Intent for more details.
* Update the docker base images (BTN-2661)

0.8.0
**********
* Update to ODA v7.4.0 and fastapi v0.115.8

0.7.0
**********
* Added AA0.5 and AA1 subarray information /configuration endpoint response for both mid and low telescopes
* Updated to OSD v3.1.1

0.6.0
**********
* Create Projects and SBDefinitions with a default READY status. (Note: no other status updates are implemented yet)

0.5.0
**********
* Update the Helm charts so that they have better defaults and require minimal changes in the makefile. See the docs
  Deployment > Configuration page.
* Pull the ODA password from a k8s secret
* Update to ODA v7.3.0 and handle new ODA errors

0.4.1
*****
* Upgraded to astroquery 0.4.9
* Changed coordinateslookup.py to work with Pydantic even when the source doesn't have a velocity or redshift
* For SIMBAD, the velocity or the redshift is set, depending on which is the master value
* The redshift is now set if the source is found via NED
* Test file renamed to test_coordinates.py so that tests will run
* More tests were added for e.g. source in NED and not SIMBAD, as well as source not found at all
* [BREAKING]: No source found returns a 404 error 

0.4.0
*****
* Update to ODA v7.2.0 with PDM v17.1.2
* New API endpoint: Added /configuration to fetch static information from the OSD and return in a format required by the ODT UI
* New API endpoint: Copy the /coordinates end point from the PHT to resolve target coordinates
* Added a request body to /api/v0/odt/prjs/{identifier}/{obs_block_id}/sbds so can add some SBDefintion data in same request

0.3.1
*****
* Remove validation of dish config from mid

0.3.0
*****
* Updated - Saving a Low SB using ODT services no longer causes dish validation error
* Updated ODA to v6.1.0 which brings in PDM v15.4.0

0.2.0
*****

* Updated ODA to v6.0.0 which no longer supports REST Repository. Added config to ska-oso-services to enable direct Postgres connection.
* Converted from Flask application into FastAPI

0.1.0
*****

* Copied existing functionality from ska-oso-odt-services into this repository. This means the ska-oso-services will offer the same API as ska-oso-odt-services v1.0.4. For the rationale behind this, see https://confluence.skatelescope.org/pages/viewpage.action?pageId=265844480.