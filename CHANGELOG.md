Changelog
==========

All notable changes to this project will be documented in this file.
This project adheres to [Semantic Versioning](http://semver.org/).

Unreleased
**********

0.3.1
**********
* Remove validation of dish config from mid

0.3.0
**********
* Updated - Saving a Low SB using ODT services no longer causes dish validation error
* Updated ODA to v6.1.0 which brings in PDM v15.4.0

0.2.0

***********

* Updated ODA to v6.0.0 which no longer supports REST Repository. Added config to ska-oso-services to enable direct Postgres connection.
* Converted from Flask application into FastAPI

0.1.0

*****

* Copied existing functionality from ska-oso-odt-services into this repository. This means the ska-oso-services will offer the same API as ska-oso-odt-services v1.0.4. For the rationale behind this, see https://confluence.skatelescope.org/pages/viewpage.action?pageId=265844480.