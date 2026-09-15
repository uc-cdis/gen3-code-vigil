{{/*
Return the fully qualified app name
*/}}
{{- define "kubectl-ai.fullname" -}}
{{- printf "%s" .Release.Name -}}
{{- end }}
