.. _secret_management:

Secret Management
=========================

``ska-oso-services`` requires secret values to connect to the ODA PostgreSQL instance.

The deployment is configured to set the ``ADMIN_POSTGRES_PASSWORD`` environment variable from the Kubernetes
Secret that is the password to the PostgreSQL isntance that the ``ska-db-oda-umbrella`` chart deploys.

To use a different Secret, the ``.Values.rest.oda.postgres.password.secret`` value can be overwritten with the Kubernetes Secret
resource name and the ``.Values.rest.oda.postgres.password.key`` with the key within that Secret.

PHT secrets
------------

PHT uses the following secrets:
  - AWS_SERVER_PUBLIC_KEY: SKAO AWS account's public key
  - AWS_SERVER_SECRET_KEY: SKAO AWS account's secret ket key
  - AWS_PHT_BUCKET_NAME: S3 bucket name to be used
  - SMTP_PASSWORD. SKAO SMTP password to use.

These secrets are currently configured to be retrieved from HashiCorp Vault from under https://vault.skao.int/ui/vault/secrets/dev/kv/stargazers%2Foso-services/details?version=2
No provisions are made yet for higher environments (subject to the further discussions withing OSO and AVIV).

When developing locally, you can override them by changing `\ska-oso-services\charts\ska-oso-services\templates\all_secrets.yaml` and then `stringData.*`. Make sure you uninstall the chart when doing so and do not commit these secrets.
