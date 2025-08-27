.. _deployment_to_kubernetes:

Deployment to Kubernetes
=========================

The ``ska-oso-services`` Helm chart will deploy the application with environment variables from a ConfigMap and an
Ingress rule.

The ``ska-oso-services-umbrella`` Helm chart will deploy ``ska-oso-services`` and all its dependencies, namely the ODA and SKUID.

To deploy the charts, the standard SKAO make targets are used - for example ``make k8s-install-chart``

To set environment variables to different values from the defaults, the Helm values.yaml can be used. Some values may need to
be set dynamically - see :doc:`configuration`.