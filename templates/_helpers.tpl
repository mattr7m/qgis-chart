{{/*
Expand the name of the chart.
*/}}
{{- define "qgis.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "qgis.labels" -}}
app.kubernetes.io/name: {{ include "qgis.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}
