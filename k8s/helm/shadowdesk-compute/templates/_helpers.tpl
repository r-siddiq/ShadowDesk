{{/*
Expand the name of the chart.
*/}}
{{- define "shadowdesk-compute.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "shadowdesk-compute.fullname" -}}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- .Release.Namespace }}
{{- end }}

{{/*
Create chart name and version as used by the chart label.
*/}}
{{- define "shadowdesk-compute.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}
