{{/*
Name used for every resource in this chart. Deliberately independent of the
release name so the in-cluster DNS name (and therefore the issuer URL) stays
predictable.
*/}}
{{- define "mock-passport-broker.fullname" -}}
{{- default .Chart.Name .Values.fullnameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{- define "mock-passport-broker.labels" -}}
app.kubernetes.io/name: {{ include "mock-passport-broker.fullname" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app: {{ include "mock-passport-broker.fullname" . }}
{{- end }}

{{- define "mock-passport-broker.selectorLabels" -}}
app: {{ include "mock-passport-broker.fullname" . }}
{{- end }}

{{/*
The issuer of every token the broker signs. Defaults to the cluster-local
Service DNS name; a port suffix is only added when the Service is not on port 80.
*/}}
{{- define "mock-passport-broker.issuer" -}}
{{- if .Values.issuer }}
{{- .Values.issuer | trimSuffix "/" }}
{{- else if eq (int .Values.service.port) 80 }}
{{- printf "http://%s.%s.svc.cluster.local" (include "mock-passport-broker.fullname" .) .Release.Namespace }}
{{- else }}
{{- printf "http://%s.%s.svc.cluster.local:%d" (include "mock-passport-broker.fullname" .) .Release.Namespace (int .Values.service.port) }}
{{- end }}
{{- end }}

{{/*
Where the signing key comes from: an existing secret, or otherwise the secret
this chart generates.
*/}}
{{- define "mock-passport-broker.secretName" -}}
{{- if .Values.signingKey.existingSecret }}
{{- .Values.signingKey.existingSecret }}
{{- else }}
{{- printf "%s-signing-key" (include "mock-passport-broker.fullname" .) }}
{{- end }}
{{- end }}

{{- define "mock-passport-broker.secretKey" -}}
{{- if .Values.signingKey.existingSecret }}
{{- required "set signingKey.existingSecretKey" .Values.signingKey.existingSecretKey }}
{{- else }}
{{- "private_key.pem" }}
{{- end }}
{{- end }}
