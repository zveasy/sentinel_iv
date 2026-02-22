{{/*
Expand the name of the chart.
*/}}
{{- define "sentinel-hb.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "sentinel-hb.fullname" -}}
{{- if .Values.fullnameOverride }}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- $name := default .Chart.Name .Values.nameOverride }}
{{- if contains $name .Release.Name }}
{{- .Release.Name | trunc 63 | trimSuffix "-" }}
{{- else }}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" }}
{{- end }}
{{- end }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "sentinel-hb.labels" -}}
helm.sh/chart: {{ include "sentinel-hb.name" . }}
app.kubernetes.io/name: {{ include "sentinel-hb.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels
*/}}
{{- define "sentinel-hb.selectorLabels" -}}
app.kubernetes.io/name: {{ include "sentinel-hb.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
