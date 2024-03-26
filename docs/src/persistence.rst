Persistence in the ODA
==============================

The service uses an implementation of the OSO Data Archive (ODA) for persistence.

The OSO Data Archive (ODA) contains ``Repository`` and ``UnitOfWork`` interfaces which abstract over
database access. There are different implementations of these interfaces, namely ``memory``, ``filesystem``, ``postgres`` and ``rest``.
For more details, see the `ska-db-oda <https://developer.skao.int/projects/ska-db-oda/en/latest/index.html>`_ project.

The important thing for the OSO Services is that the implementation can be configured at deploy time, by setting an environment variable through the Helm value:

.. code-block:: yaml

    rest:
      ...
      oda:
        backendType: filesystem
        url:
      ...

The ``filesystem`` implementation uses the filesystem of the OSO Services pod to persist data.
This means by default is does not persist past the lifetime of the pod. It is intended to be used as a simple development environment.
Entities can also be manually added to a mounted filesystem and accessed through the API.

Setting the value to ``rest`` will use an implementation which accesses a remote instance of the ODA REST Client.
The ``url`` value must also be set to the URL for the API, eg ``http://ska-db-oda-rest-test:5000/ska-oso-services/odt/api/v1``.
The pod will access the URL from within the Kubernetes cluster, so can use the ODA service address if they are deployed to the same namespace.

The ``memory`` implementation serves a similar purpose to the filesystem, acting as an even more lightweight development environment.

The ``postgres`` implementation should not be used, as the applications won't be connecting directly to the PostgreSQL instance.