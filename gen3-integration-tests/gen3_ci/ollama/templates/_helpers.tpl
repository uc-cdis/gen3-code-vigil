{{/*
Return the fully qualified app name
*/}}
{{- define "ollama.fullname" -}}
{{- printf "%s" .Release.Name -}}
{{- end }}
