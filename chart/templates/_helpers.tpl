{{/*
Expand the name of the chart.
*/}}
{{- define "orchestrator-core.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Create a default fully qualified app name.
We truncate at 63 chars because some Kubernetes name fields are limited to this (by the DNS naming spec).
If release name contains chart name it will be used as a full name.
*/}}
{{- define "orchestrator-core.fullname" -}}
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
Create chart name and version as used by the chart label.
*/}}
{{- define "orchestrator-core.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" }}
{{- end }}

{{/*
Common labels
*/}}
{{- define "orchestrator-core.labels" -}}
helm.sh/chart: {{ include "orchestrator-core.chart" . }}
{{ include "orchestrator-core.selectorLabels" . }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end }}

{{/*
Selector labels of the API. The scheduler and workers use their own name (see componentSelectorLabels),
so the API selector does not match their pods.
*/}}
{{- define "orchestrator-core.selectorLabels" -}}
app.kubernetes.io/name: {{ include "orchestrator-core.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end }}

{{/*
Selector labels of a component other than the API: "<name>-<component>". Selectors are immutable,
so these never change between chart versions.
Usage: include "orchestrator-core.componentSelectorLabels" (list $ "scheduler")
*/}}
{{- define "orchestrator-core.componentSelectorLabels" -}}
{{- $root := index . 0 -}}
app.kubernetes.io/name: {{ include "orchestrator-core.name" $root }}-{{ index . 1 }}
app.kubernetes.io/instance: {{ $root.Release.Name }}
{{- end }}

{{/*
The env ConfigMap: what the enabled components need, overridden by .Values.env. Every later envFrom
source (secretEnv, existingSecrets) overrides it in turn.
*/}}
{{- define "orchestrator-core.envConfig" -}}
{{- $defaults := dict -}}
{{- if .Values.celery.enabled -}}
{{- $defaults = dict "EXECUTOR" "celery" "DISTLOCK_BACKEND" "redis" -}}
{{- end -}}
{{- if .Values.mcp.enabled -}}
{{- $_ := set $defaults "MCP_ENABLED" "true" -}}
{{- end -}}
{{- /* orchestrator-core before 5.5 defaults TESTING to true, which makes the API wait for every workflow to finish. */}}
{{- $_ := set $defaults "TESTING" "false" -}}
{{- merge (deepCopy .Values.env) $defaults | toYaml }}
{{- end }}

{{/*
An orchestrator container: image, environment and mounts, shared by every process.
Usage: include "orchestrator-core.container" (list $ "name" (list "command" "args"))
*/}}
{{- define "orchestrator-core.container" -}}
{{- $root := index . 0 -}}
{{- $values := $root.Values -}}
- name: {{ index . 1 }}
  {{- with $values.securityContext }}
  securityContext:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  image: {{ printf "%s:%s" (required "image.repository is required: build an image FROM the orchestrator-core image with your code" $values.image.repository) (required "image.tag is required" $values.image.tag) }}
  imagePullPolicy: {{ $values.image.pullPolicy }}
  {{- with index . 2 }}
  command: {{ toJson . }}
  {{- end }}
  {{- with $values.extraEnv }}
  env:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  envFrom:
    - configMapRef:
        name: {{ include "orchestrator-core.fullname" $root }}-env
    {{- if $values.secretEnv }}
    - secretRef:
        name: {{ include "orchestrator-core.fullname" $root }}-env
    {{- end }}
    {{- range $values.existingSecrets }}
    - secretRef:
        name: {{ tpl . $root }}
    {{- end }}
  {{- with $values.volumeMounts }}
  volumeMounts:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}

{{/*
Pod template metadata and pod-level settings shared by every orchestrator pod.
Usage: include "orchestrator-core.podTemplate" (list $ (selector labels) "component")
*/}}
{{- define "orchestrator-core.podTemplate" -}}
{{- $root := index . 0 -}}
{{- $values := $root.Values -}}
metadata:
  annotations:
    checksum/env: {{ list (include "orchestrator-core.envConfig" $root) $values.secretEnv | toJson | sha256sum }}
    {{- with $values.podAnnotations }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
  labels:
    {{- index . 1 | nindent 4 }}
    app.kubernetes.io/component: {{ index . 2 }}
    {{- with $values.podLabels }}
    {{- toYaml . | nindent 4 }}
    {{- end }}
spec:
  {{- with $values.imagePullSecrets }}
  imagePullSecrets:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $values.serviceAccountName }}
  serviceAccountName: {{ . }}
  {{- end }}
  automountServiceAccountToken: {{ $values.automountServiceAccountToken }}
  {{- with $values.podSecurityContext }}
  securityContext:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $values.volumes }}
  volumes:
    {{- tpl (toYaml .) $root | nindent 4 }}
  {{- end }}
  {{- with $values.nodeSelector }}
  nodeSelector:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $values.affinity }}
  affinity:
    {{- toYaml . | nindent 4 }}
  {{- end }}
  {{- with $values.tolerations }}
  tolerations:
    {{- toYaml . | nindent 4 }}
  {{- end }}
{{- end }}
