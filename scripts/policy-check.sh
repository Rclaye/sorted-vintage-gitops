#!/usr/bin/env bash
# Policy check (T026, FR-027): the same Kyverno policies that run at admission, run here on every
# pull request (checks workflow, job "policy"). Needs kyverno, kustomize and kubeconform on PATH.
#   1. kyverno test: every manifest in tests/policy/bad fails its rule, tests/policy/good passes.
#   2. Render every overlay under services/ and platform/; each must set namespace: sv-<env>.
#   3. kubeconform: rendered overlays and test manifests are valid Kubernetes objects.
#   4. kyverno apply: every rendered overlay passes every policy.
# Every overlay is rendered, not only the changed ones: it takes seconds and also catches a
# policy change that breaks a manifest nobody touched.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"

out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT

echo "== kyverno test"
kyverno test tests/policy

echo "== render overlays"
shopt -s nullglob
rendered=()
for dir in services/*/overlays/* platform/*/overlays/*; do
  env="$(basename "$dir")"
  if ! grep -Eq "^namespace: sv-${env}\$" "$dir/kustomization.yaml"; then
    echo "::error file=$dir/kustomization.yaml::overlay must set 'namespace: sv-${env}'"
    exit 1
  fi
  file="$out/$(echo "$dir" | tr / _).yaml"
  kustomize build "$dir" > "$file"
  rendered+=("$file")
  echo "$dir"
done

echo "== kubeconform"
kubeconform -strict -summary -ignore-missing-schemas \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json' \
  "${rendered[@]}" tests/policy/good tests/policy/bad

echo "== kyverno apply"
args=()
for f in "${rendered[@]}"; do args+=(--resource "$f"); done
kyverno apply policies/ --values-file tests/policy/values.yaml "${args[@]}"
