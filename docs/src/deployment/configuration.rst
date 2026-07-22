.. _configuration:

Configuration
======================

The following environment variables are used to configure the application. They are set by Kubernetes ConfigMaps and Secrets,
with values coming from the Helm chart. See :doc:`deployment_to_kubernetes`.

Some settings are optional because defaults are defined in the application code.
Settings without code defaults must be provided by Helm values, Vault-backed secrets,
or an existing Kubernetes Secret. See :doc:`secret_management`.


.. list-table:: Environment variables used by ska-oso-services
   :widths: 10 10 10 10 10
   :header-rows: 1

   * - Environment variable
     - Description
     - Required/optional in the application
     - Corresponding Helm value
     - Required/optional in the Helm chart
   * - PGHOST
     - The address of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``localhost``
     - ``global.oda.postgres.host``
     - Optional - will fall back on: ``{{.Values.postgres.cluster}}.{{.Values.postgres.clusterNamespace}}.svc.{{ .Values.global.cluster_domain }}``
   * - PGPORT
     - The port of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``5432``
     - ``global.oda.postgres.port``
     - Optional - default: ``5432``
   * - PGDATABASE
     - The name of the database within a PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``oda``
     - ``global.oda.postgres.database``
     - Optional - no chart default (typically set by deployment tooling)
   * - PGUSER
     - The admin user of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``oda_admin``
     - ``global.oda.postgres.user``
     - Optional - no default in chart
   * - PGPASSWORD
     - The admin password of the PostgreSQL instance that the postgres ODA will connect to.
     - Optional - default: ``""``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - SKA_AUTH_AUDIENCE
     - Comma-separated list of accepted JWT audience values.
     - Optional - default: ``live:pht,live:odt,api://e4d6bb9b-cdd0-46c4-b30a-d045091b501b``
     - ``rest.authAudiences``
     - Optional - chart default provided
   * - PIPELINE_TESTS_DEPLOYMENT
     - Enables pipeline test auth behavior.
     - Optional - default: ``False``
     - ``pipeline_test_deployment``
     - Optional - default: ``false``
   * - OSO_CLIENT_SECRET
     - Client secret used by oso-services.
     - Optional - default: ``OSO_CLIENT_SECRET``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - USER_PORTAL_BASE_URL
     - The base URL for the SKAO User Portal in this environment.
     - Required
     - ``rest.userPortalBaseUrl``
     - Required - default: ``"https://userportal.skao.int.example"``
   * - USER_PORTAL_API_KEY
     - API key used to authenticate to the SKAO User Portal API.
     - Optional - default: ``""``
     - ``rest.userPortalApiKey``
     - Optional - default: ``""``
   * - USER_PORTAL_TIMEOUT
     - How long to wait (in seconds) before User Portal API requests time out.
     - Optional - default: ``10``
     - ``rest.userPortalTimeout``
     - Optional - default: ``10``
   * - LOG_LEVEL
     - Application log level.
     - Optional - default: ``INFO``
     - ``rest.logLevel``
     - Optional - default: ``INFO``
   * - PRODUCTION
     - Whether the application is running in production mode.
     - Optional - default: ``False``
     -
     -
   * - API_PATH_PREFIX
     - Prefix for the API path.
     - Optional - default: ``""``
     - Computed from ingress values
     - Optional
   * - ENGINEERING_API_ENABLED
     - Whether the engineering API is enabled.
     - Optional - default: ``True``
     - ``rest.engineeringApiEnabled``
     - Optional - default: ``true``
   * - SDP_SCRIPT_TMDATA
     - TMData source URL for SDP Script metadata.
     - Optional - default: ``None``
     - ``global.oso.sdp_tmdata``
     - Optional - chart default provided
   * - AWS_ACCESS_KEY_ID
     - The aws server public key used to connect to the AWS account. Used by PHT to work with S3.
     - Optional - default: ``None``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - AWS_SECRET_ACCESS_KEY
     - The aws server secret key used to connect to the AWS account. Used by PHT to work with S3.
     - Optional - default: ``None``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - AWS_SESSION_TOKEN
     - Optional AWS session token when temporary credentials are used.
     - Optional - default: ``None``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - AWS_PHT_BUCKET_NAME
     - The S3 bucket name used by PHT.
     - Required
     - ``rest.awsPhtBucketName``
     - Required - default: ``"pht-bucket"``
   * - AWS_REGION
     - The S3 region used by PHT.
     - Required
     - ``rest.awsRegion``
     - Required - default: ``"us-west-2"``
   * - PHT_EMAIL_USER
     - The address used by the PHT to send email with invitations to proposals.
     - Optional - default: ``None``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - PHT_EMAIL_PASSWORD
     - The password to for the PHT_EMAIL_USER.
     - Optional - default: ``None``
     - Pulled from Vault - see :doc:`secret_management`
     -
   * - PRESIGNED_URL_EXPIRY_TIME
     - Expiry time for S3 presigned URLs in seconds
     - Optional - default: ``60``
     -
     - Optional