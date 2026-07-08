{{/* vim: set filetype=mustache: */}}
{{/*
Expand the name of the chart.
*/}}
{{- define "ska-oso-services.name" -}}
{{- if .Values.nameOverride -}}
{{- .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{/*
Standardise the name pattern for resources created by the chart
*/}}
{{- define "ska-oso-services.resource-name" -}}
{{- $name := include "ska-oso-services.name" .}}
{{- printf "%s-%s" $name .Release.Name -}}
{{- end -}}

{{/*
Common labels
*/}}
{{- define "ska-oso-services.labels" }}
app: {{ template "ska-oso-services.name" . }}
chart: {{ template "ska-oso-services.chart" . }}
release: {{ .Release.Name }}
subsystem: oso
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "ska-oso-services.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "ska-oso-services.oda-secret-name" -}}
{{- $resourceName := include "ska-oso-services.resource-name" .}}
{{- printf "%s-%s" $resourceName "secret-oda"  -}}
{{- end -}}

{{- define "ska-oso-services.application-secret-name" -}}
{{- $resourceName := include "ska-oso-services.resource-name" .}}
{{- printf "%s-%s" $resourceName "secret"  -}}
{{- end -}}

{{/*
Get the major version of the chart release
*/}}
{{- define "ska-oso-services.major-version" }}
{{- with $x := printf "%s" .Chart.Version | split "."}}{{index $x "_0"}}{{end}}
{{- end -}}

{{/*
Gets the Service address for the postgres instance deployed by the Stackgres Operator
*/}}
{{- define "ska-oso-services.postgres-host" -}}
{{- printf "%s.%s.svc.%s" .Values.global.oda.postgres.cluster .Values.global.oda.postgres.clusterNamespace .Values.global.cluster_domain -}}
{{- end -}}

{{/*
Returns the standard OSO application API path of the form
/<NAMESPACE>/oso/api/v<MAJOR_VERSION>
unless an override is given.
*/}}
{{- define "ska-oso-services.api-path" -}}
{{- if .Values.ingress.pathOverride -}}
{{- .Values.ingress.pathOverride -}}
{{- else -}}
{{- $majorVersion := include "ska-oso-services.major-version" .}}
{{- printf "/%s/oso/api/v%s" .Release.Namespace $majorVersion  -}}
{{- end -}}
{{- end -}}