Changelog
==========

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

11.4.0
**********
* Updated /configuration end point to return all the basic capabilities in the OSD for Low 

11.3.0
**********
* Update generated SBDs to have scan intents
* Update OSD to v5.2.0
* Update /configuration endpoint to include `Low-ITF`, `AA2_SV` and `Mid_ITF` and to also return `available_bandwidth_hz`,
  `number_pst_beams` and `number_fsps` for both Mid and Low and `number_substations` and `number_subarray_beams` for Low only
* Fixed precision of the Galactic look-up response
* [BUGFIX] make channel_width_hz optional in OSD response model for PHT

11.2.0
**********
* Update ODA to v14.3.0

11.1.0
**********
* Adds ``validation`` package with an API to validate ``SBDefinition``
* Adds project purpose to projects generated from proposals and constrains it to be 'Science'

11.0.0
**********
* [BUGFIX] Updates `/coordinates/galactic` to return a PDM target with a galactic coordinate object

10.1.0
**********
* Update OSD version to 5.1.0 and change ObservatoryPolicy, CyclePolicies, and TelescopeCapabilities models.

10.0.2
**********
* Update ODA to v14.0.4

10.0.1
***********
* [BUGFIX] Nest continuum-imaging script parameters inside 'continuum_imaging' key and retrieve script version from SDP TMData

10.0.0
***********
* [BREAKING] Updates ODA version to 14.0.0 and OSD version to 5.0.0
* [BUGFIX] Fix index error when generating SBDs from Observation Info without calibration strategy notes
* [BUGFIX] Update to ODA 13.1.1 with better error handling of postgres connections
* [BUGFIX] Set `PGUSER` to `<.Values.global.oda.postgres.database>_admin` if `.Values.global.oda.postgres.user` isn't set
* Adds SDP configurations to Scheduling Blocks generated from Proposals
* Changes the SDP TMData source Helm configuration key from `ska-oso-services.rest.sdp.tmdata` to `global.oso.sdp_tmdata`
* Updates SBD generation from Project to handle additional script parameters
* Improvements to target catalog error handling and logging
* Update the target catalog lookup response to return a PDM object with an extra `equatorial`/`galactic` deprecated field from the old response. 
  This means the change is backwards compatible, giving chance for users to update to migrate to use the Target object.
  * Adds visibility plot endpoint to common
  * Updates panel assignment to also create reviews and decisions
  * Updates report to show all statuses and return location fo the PI


9.2.0
***********
* Adds the AA2 to the list of array assemblies that are retrieved from the OSD
* Adds function to find the appropriate calibrator given Target and an Observing Strategy
* Adds applying calibration strategy to LOW Scheduling Blocks generated from Proposals
* Updates ODA to v13.1.0

9.1.0
***********
* Adds a `/calibrators` endpoint that returns a list of approved LOW Calibrator targets

9.0.0
***********
* Add calibration strategy module with default observatory strategy and lookup
* [BREAKING] Removes `/panels/auto-create` and Adds `/panels/assignments` and `panels/generate`
* Updates ODA to v12.1.1
* Removes review_submitted_on from report

8.0.0
***********
* [BREAKING] Update to ODA v12.0.0 which deploys Postgres via the operators. This involves some updates to the global Helm values used by the chart. 
* Adds API for retrieving SDP script versions and script parameters 
* [BREAKING] Update error handlers to all return same format details

7.0.0
***********
* [BREAKING] Update to ODA v11.8.0 which pulls in PDM v23.0.0
* [BREAKING] Updates `pht/prsl/create` to return the created proposal instead of the proposal id (prsl_id).
* Adds PI details to the proposal when created.
* Updates `/panel/decision/{decision_id}` to update proposal status when decision is decided
* Updates `/reviewable` endpoint to allow access by admin, reviewers, sw_eng and review_chair but with restrictions based on roles
* Updates the `/reviews` so review chair can retrieve reviews
* Updates proposal status to `under review` when the panel is updated

6.0.0
***********
* Updates permissions for panel decisions
* [BREAKING] Updates `pht/panel/users/{user_id}/decision` to `pht/panel/decision` so user id is pulled from token.
* Update to ODA v11.7.1 which pulls in PDM v22.1.1

5.2.0
***********
* Update to OSD v4.2.1 and add the Band 5b sub-bands to the ODT /configuration endpoint response
* Update to ODA v11.7.0 which pulls in PDM v22.1.0

5.1.0
***********
* Adds `/pht/prsls/member/{email}` to search user by email
* Updates the put panel endpoint to create proposal decisions.
* Update ingress rule and add Values.nameOverride so that multiple major versions of the chart can be deployed into the same namespace
* Updates `/pht/prsls/reviewers` to retrieve users with science/technical reviewer roles
* Update to ODA v11.6.0 which pulls in PDM v22.0.0

5.0.0
***********
* Allows multiple technical reviews creation for a panel
* Adds the `created_by` for panels
* [BREAKING] Updates the `/users/{user_id}/panels` to `/` to return all panels regardless the user
* [BREAKING] Updates `/users/{user_id}/reviews` to `/users/reviews` to retriev user from token
* [BREAKING] Updates `/status/{status}` to `/reviewable` and no user input
* Adds PHT specific roles

4.0.4
***********
* Return only the latest version of projects and proposals from `prsls/project-view` endpoint
* Return only proposals that are not in DRAFT from `prsls/project-view` endpoint

4.0.3
***********
* Updates ODA version to 11.5.1 

4.0.2
***********
* Updates Roles to ANY for Validate endpoint

4.0.1
***********
* Updates email, pdfs endpoints for the PHT to use Role.Any

4.0.0
***********
* Fixes the issue when a technical review already exists so a new one is not created
* [BREAKING] Updates the PHT endpoints such that they are coherent e,g `POST entity/create`
* [BREAKING] Updates the retrieval of entities endpoint from `entity/list/{id}` to be `entity/users/{id}/entity`
* Panel `auto-create` can now update the submitted proposals for `Science Verification`
* Fixes the bug with the report endpoint.
* Creates Science reviews as part of the panel update endpoint.
* Updates ODA version to 11.5.0
* Add `/odt/prsls/project-view` endpoint which returns a view for the UI of an outer join of the Proposals and Projects
* Write user from auth context to entity metadata for ODT endpoints
* [BREAKING] Use Helm global values for ODA configuration rather than ska-oso-services chart ones
* Deploy Secret for ODA password rather than relying on external one from ODA chart

3.1.1
***********
* Allow ODT read scope on proposal search
* Copy name when generating Project from Proposal

3.1.0
***********
* Auto technical review creation using the `PUT panel update` endpoint
* Allow OPERATIONS_SCIENTIST role to use the ODT API endpoints

3.0.0
***********
* [BREAKING] Adds AAA protection to PHT endpoints
* [Breaking] Upgraded `OSD` to version `4.0.0`
* [Breaking] Updates ODA version to 11.3.0
* Updated ODA to v11.1.0
* Adds auto-panel creation `POST` endpoint based on cycle description
* Adds separate `PUT` endpoint to update panels
* Updates ska-aaa-authhelpers version to 1.1.0
* Updates `POST` reviews endpoint to check if a review already exist under a different id before creating new review
* Added POST `/pht/proposal-access/create` for pht
* Added GET `/pht/proposal-access/user` for pht
* Added GET `/pht/proposal-access/user/{prsl_id}` for pht
* Added PUT `/pht/proposal-access/user/{access_id}` for pht
* Adds module_view page and diagrams to documentation
* Adds the functionality to create permission when a proposal is created 
* Adds the functionality to check permission when a user gets a proposal by user_id from auth and prsl_id
* Adds the functionality to check permission when a user submit/update a proposal

2.0.3
***********
* Set Observing Block name when generating a Project
* Set CSP config and Target name when generating SBDefinitions

2.0.2
***********
* NOTE: Due to a pipeline concurrency issue, this release wrongly includes BREAKING changes compared to 2.0.0 (namely PHT endpoint AAA). Please do not use this release, 
  and instead use 2.0.3

2.0.1
***********
* NOTE: Due to a pipeline concurrency issue, this release wrongly includes BREAKING changes compared to 2.0.0 (namely PHT endpoint AAA). Please do not use this release, 
  and instead use 2.0.3

2.0.0
***********
* [BREAKING] Updated ODA to version 11.0.0 (python package and helm chart)
* [BREAKING] Updated ODT's SBD generator to populate scan sequence within MCCS/Dish allocation instead of at root SBD level (as implemented in PDM v19.0.0)
* Added LOW/MID_TELESCOPE_OPERATOR roles to all ODT endpoints
* Updated `/reports/` endpoint to pull proposals of all statuses except withdrawn and draft
* Updated the status of a submitted proposal to be changed on assignment to a panel

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