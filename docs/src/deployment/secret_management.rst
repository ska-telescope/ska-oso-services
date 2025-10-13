.. _secret_management:

Secret Management
=========================

ODA Secret
-------------

``ska-oso-services`` requires secret values to connect to the ODA PostgreSQL instance.

The application uses the ``PGPASSWORD`` environment variable which is injected in the chart from a Kubernetes
Secret. The Secret resource should pull the value from Vault on creation, using the standard VaultStaticSecret.

By default, the ``ska-oso-services`` chart will create a Secret that contains the ODA password for use by the application, without
the need for any user configuration.

To use a different Secret, set the ``.Values.global.oda.postgres.secret.existingSecret`` value with the Secret name.

See :doc:`configuration` for more details on the ODA connection.

Using a Secret for the full Postgres connection
................................................

The chart is configured in such a way that it pulls the ``PG_`` environment variables from a ConfigMap and the ``PGPASSWORD`` from a Secret (as the host, etc
are dynamic and can't be pulled from Vault).

However, if the ``ska-oso-services`` application is connecting to an externally managed Postgres, and a Secret is available in the namespace with the full ``PG_``
variables, these will be taken over the ConfigMap if the Secret is passed via ``.Values.global.oda.postgres.secret.existingSecret``.

PHT secrets
------------

PHT uses the following secrets:
  - AWS_SERVER_PUBLIC_KEY: SKAO AWS account's public key
  - AWS_SERVER_SECRET_KEY: SKAO AWS account's secret ket key
  - AWS_PHT_BUCKET_NAME: S3 bucket name to be used
  - SMTP_PASSWORD. SKAO SMTP password to use.

These secrets are currently configured to be retrieved from HashiCorp Vault from under https://vault.skao.int/ui/vault/secrets/dev/kv/stargazers%2Foso-services/details?version=2
No provisions are made yet for higher environments (subject to the further discussions withing OSO and AVIV).

When developing locally, you can override them by changing `\ska-oso-services\charts\ska-oso-services\templates\pht_secrets.yaml` and then `stringData.*`. Make sure you uninstall the chart when doing so and do not commit these secrets.
