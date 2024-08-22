.. _environment_variables:

Environment Variables
======================

The following environment variables are used to configure the application.

Generally, they are set via a Kubernetes ConfigMap with values coming from the Helm values.yaml. See :doc:`deployment_to_kubernetes`

Required/optional means whether they are required by the application code or whether a default is set within the application.
They may be listed as required here for the application, but have a default set within the Helm chart.


.. list-table:: Environment variables used by ska-oso-services
   :widths: 23 40 30
   :header-rows: 1

   * - Environment variable
     - Description
     - Required/optional
   * - SKUID_URL
     - The Kubernetes service address of a running SKUID service
     - Required
   * - ODA_BACKEND_TYPE
     - Defines whether the ODA interfaces should connect to a Postgresql instance or use the filesystem.
     - Optional - default: ``filesystem``
   * - ODA_DATA_DIR
     - The base filesystem location that the filesystem ODA will use to store and retrieve entities.
     - Optional - default: ``/var/lib/oda``
   * - POSTGRES_HOST
     - The address of the PostgreSQL instance that the postgres ODA will connect to.
     - Required if ``ODA_BACKEND_TYPE`` is ``postgres``
   * - ADMIN_POSTGRES_USER
     - The admin user of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``postgres``
   * - ADMIN_POSTGRES_PASSWORD
     - The admin password of the PostgreSQL instance that the postgres ODA will connect to.
     - Required if ``ODA_BACKEND_TYPE`` is ``postgres``
   * - POSTGRES_PORT
     - The port of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``5432``
   * - POSTGRES_DB_NAME
     - The name of the database within a PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``postgres``
   * - POSTGRES_DB_NAME
     - The name of the database within a PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``postgres``
