.. _persistence:

Persistence in the ODA
==============================

The service uses the `OSO Data Archive (ODA) <https://developer.skao.int/projects/ska-db-oda/en/latest/index.html>`_ for persistence.

The OSO Data Archive (ODA) contains ``Repository`` and ``UnitOfWork`` interfaces which abstract over database access. 

These interfaces connect directly to the ODA Postgres instance, using values set from the environment variables.




