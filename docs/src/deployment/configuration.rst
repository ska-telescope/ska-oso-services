.. _configuration:

Configuration
======================

The following environment variables are used to configure the application. They are set via a Kubernetes ConfigMap
with values coming from the Helm values.yaml. See :doc:`deployment_to_kubernetes`

Generally, if an variable default can be set in the application it will be. There are then also some defaults in the Helm values.
For more dynamic values that depend on the release name or namespace, the environment variables have a sensible default in the ConfigMap
but also can be overwritten via the values.yaml.

The ODA connection is configured these environment variables and corresponding Helm values, or a Kubernetes Secret - see :doc:`secret_management`.


.. list-table:: Environment variables used by ska-oso-services
   :widths: 10 10 10 10 10
   :header-rows: 1

   * - Environment variable
     - Description
     - Required/optional in the application
     - Corresponding Helm value
     - Required/optional in the Helm chart
   * - SKUID_URL
     - The Kubernetes service address of a running SKUID service
     - Required
     - ``ska-oso-services.rest.skuid.url``
     - Optional - will fall back on: ``ska-ser-skuid-{{ .Release.Name }}-svc.{{ .Release.Namespace }}.svc.{{ .Values.global.cluster_domain }}:9870``
   * - PGHOST
     - The address of the PostgreSQL instance that the postgres ODA will connect to.
     - Required
     - ``global.oda.postgres.host``
     - Optional - will fall back on: ``{{.Values.postgres.cluster}}.{{.Values.postgres.clusterNamespace}}.svc.{{ .Values.global.cluster_domain }}``
   * - PGUSER
     - The admin user of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``oda_admin``
     - ``global.oda.postgres.user``
     - Optional - no default in chart
   * - PGPASSWORD
     - The admin password of the PostgreSQL instance that the postgres ODA will connect to.
     - Required
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - PGPORT
     - The port of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``5432``
     - ``global.oda.postgres.port``
     - Optional -  default: ``5432``
   * - PGDATABASE
     - The name of the database within a PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``oda``
     - ``global.oda.postgres.database``
     - Optional - no default in chart (overwritten in the Makefile)
   * - AWS_SERVER_PUBLIC_KEY
     - The aws server public key used to connect to the AWS account. Used by PHT to work with S3.
     - Required
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - AWS_SERVER_SECRET_KEY
     - The aws server secret key used to connect to the AWS account. Used by PHT to work with S3.
     - Required
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - AWS_PHT_BUCKET_NAME
     - The aws S3 buket name used by PHT.
     - Required
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - SMTP_PASSWORD
     - The SMTP password to connect to SKAO server. Used by PHT to send emails.
     - Required
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - OSO_CLIENT_SECRET
     - client secret for oso services
     - Required
     - Pulled from Vault - see :doc:`secret_management`
     -