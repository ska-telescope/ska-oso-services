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

Application Secrets
--------------------

There are a number of secrets defined on :doc:`configuration` that the application needs for various PHT functionality.

By default the Helm chart will pull these from Vault into a Kubernetes Secret, using the path and keys defined in the values.
This Secret is then used to set environment variables for the application.

Alternatively, the Helm value ``vault.enabled`` can be set to ``false`` and an externally managed Secret used with the value
``existingApplicationSecret.name``