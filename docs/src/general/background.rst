.. _background:

Background
===========

OSO Services provides the back end functionality for the Proposal Handling Tool and the Observation Design Tool.

The reasoning behind a single service is that a lot of functionality will be shared - for example validating astronomical input
or looking up information from astronomy data sources. Sharing a single repository also means less maintenance overhead and more
opportunity for collaboration between the OSO teams.

The application offers a RESTful API split by `/common`, `/pht` and `/odt` paths.

For more information on the OSO workflow and how this application fits in the architecture, see `Solution Intent <https://confluence.skatelescope.org/pages/viewpage.action?pageId=159387040>`_

