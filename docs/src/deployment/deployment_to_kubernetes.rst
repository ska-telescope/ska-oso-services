.. _deployment_to_kubernetes:

Deployment to Kubernetes
=========================

The ``ska-oso-services`` Helm chart will deploy the application with environment variables from a ConfigMap and an
Ingress rule.

The ``ska-oso-services-umbrella`` Helm chart will deploy ``ska-oso-services`` and all its dependencies, namely the ODA and SKUID.

To deploy the charts, the standard SKAO make targets are used - for example ``make k8s-install-chart``

To set environment variables, the Helm values.yaml can be used. For example, the ``ODA_BACKEND_TYPE`` variable is set from the following:

.. code-block:: yaml

    rest:
      ...
      oda:
        backendType: postgres
      ...