# mock-passport-broker

![Type: application](https://img.shields.io/badge/Type-application-informational?style=flat-square) ![AppVersion: 3.13-pythonbase](https://img.shields.io/badge/AppVersion-3.13--pythonbase-informational?style=flat-square)

A test-only GA4GH passport broker. It signs the passport defined in
[files/generate_passport.py](files/generate_passport.py), a RAS-style passport with
`ras_dbgap_permissions` for RAS test datasets, and serves the JWKS that verifies it.
This lets the CI exercise fence's RFC 8693 token exchange without depending on RAS
staging.

**This chart is a test fixture with no authentication. Do not deploy it to a production commons.**

## How the CI uses it

1. [prepare_ci_environment.py](../../scripts/prepare_ci_environment.py) sets
   `MOCK_PASSPORT_BROKER_ISSUER`, which [setup_ci_env.sh](../../scripts/setup_ci_env.sh)
   uses to add the broker to fence's `GA4GH_VISA_ISSUER_ALLOWLIST` and
   `TOKEN_EXCHANGE.allowed_subject_token_issuers`.
2. When its tests run, [test_token_exchange.py](../../../tests/test_token_exchange.py)
   installs this chart as the `mock-passport-broker` release in the environment's
   namespace. It is not installed when the tests are deselected (e.g. by PR test
   labels) or skipped (e.g. fence does not support token exchange).
3. The test gets a passport from the broker, exchanges it at fence's `/oauth2/token` endpoint, and checks the
   access token grants exactly the passport's dbGaP permissions. Fence fetches the
   broker's JWKS to validate the passport and its visas; the chart's NetworkPolicy lets
   it through gen3's default-deny network policies. The test itself requests the
   passport from inside the broker's pod (`kubectl exec`).
4. The test uninstalls the release when it finishes, including when its setup fails.
   If the run is interrupted before then, the release is removed with the
   environment's namespace when the environment is torn down.

## Endpoints

| Path | Description |
|------|-------------|
| `/openid/connect/v1.1/userinfo` | `{"sub": ..., "passport_jwt_v11": <passport>}`, the RAS userinfo format fence uses for `RAS_USERINFO_ENDPOINT`. A freshly minted passport on every request. |
| `/.well-known/openid-configuration` | OIDC discovery document; fence finds the JWKS through its `jwks_uri` |
| `/.well-known/jwks.json` | RFC 7517 JWKS |
| `/jwt/keys` | The same key in the fence format, `{"keys": [[kid, pem]]}` |
| `/_status` | Health check |

The server, signing and passport code use only the Python standard library, so the
chart needs no image build. To print a passport locally, signed with the pyjwt
example key or your own:

```bash
python files/generate_passport.py --issuer https://example.org --kid my-kid [--private-key /abs/path/key.pem]
```

## Values

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| affinity | object | `{}` |  |
| containerPort | int | `8080` | Port the server listens on inside the pod. |
| fullnameOverride | string | `""` | Name used for every resource in this chart. Defaults to the chart name so the in-cluster DNS name (and therefore the issuer URL) is stable and does not depend on the release name. |
| image.pullPolicy | string | `"IfNotPresent"` |  |
| image.repository | string | `"quay.io/cdis/amazonlinux-base"` |  |
| image.tag | string | `"3.13-pythonbase"` |  |
| issuer | string | `""` | The `iss` of every passport and visa this broker signs, and the base URL it builds `jwks_uri` from. Leave empty to use `http://<fullname>.<namespace>.svc.cluster.local`, which matches the Service below when `service.port` is 80. Fence must trust exactly this value, in both GA4GH_VISA_ISSUER_ALLOWLIST and TOKEN_EXCHANGE.allowed_subject_token_issuers. |
| kid | string | `""` | Key ID advertised in the JWKS and set in the header of every token. Leave empty to use the RFC 7638 thumbprint of the signing key, so the key ID changes whenever the key does and fence never validates against a stale cached key. |
| nodeSelector | object | `{}` |  |
| netPolicy.enabled | bool | `true` | Create a NetworkPolicy that allows ingress from `ingressApps`. Gen3 network policies deny all traffic by default when `global.netPolicy.enabled` is set in the commons, and fence must be able to fetch the broker's JWKS. The broker makes no outbound requests, so it needs no egress. |
| netPolicy.ingressApps | list | `["fence","presigned-url-fence"]` | Values of the `app` label of the pods allowed to reach the broker. |
| podAnnotations | object | `{}` |  |
| podLabels | object | `{}` |  |
| replicaCount | int | `1` |  |
| resources.limits.cpu | string | `"500m"` |  |
| resources.limits.memory | string | `"128Mi"` |  |
| resources.requests.cpu | string | `"10m"` |  |
| resources.requests.memory | string | `"32Mi"` |  |
| revisionHistoryLimit | int | `2` |  |
| service.port | int | `80` | Service port. Keep this at 80 so the issuer URL needs no port suffix. |
| service.type | string | `"ClusterIP"` |  |
| signingKey.existingSecret | string | `""` | Name of an existing secret holding the RSA private key (PKCS#1 or PKCS#8 PEM) to sign with. Leave empty to have this chart generate a key on install and keep it across upgrades. |
| signingKey.existingSecretKey | string | `"private_key.pem"` | Key within `existingSecret` containing the PEM private key. |
| tolerations | list | `[]` |  |
