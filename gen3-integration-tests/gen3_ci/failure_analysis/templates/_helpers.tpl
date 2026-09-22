{{/*
Return the fully qualified app name
*/}}
{{- define "failure-analysis.fullname" -}}
{{- printf "%s" .Release.Name -}}
{{- end }}
