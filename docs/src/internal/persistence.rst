.. _persistence:

Persistence in the ODA
==============================

The service uses the `OSO Data Archive (ODA) <https://developer.skao.int/projects/ska-db-oda/en/latest/index.html>`_ for persistence.

The OSO Data Archive (ODA) contains ``Repository`` and ``UnitOfWork`` interfaces which abstract over database access. 
There are different implementations of these interfaces, namely ``filesystem`` and ``postgres``, each of which are configured through environment variables.

The ``postgres`` implementation will connect directly with a PostgreSQL instance, using values set from environment variables.

The ``filesystem`` implementation uses the filesystem of the OSO Services pod to persist data.
This means by default it does not persist beyond the lifetime of the pod. It is intended to be used as a simple development environment.
Entities can also be manually added to a mounted filesystem and accessed through the API.

The important thing for the OSO Services is that the implementation can be configured at deploy time, by setting the ``ODA_BACKEND_TYPE`` environment variable.

See TODO for information on setting this via a Helm deployment.



