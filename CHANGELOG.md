Changelog
==========

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

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