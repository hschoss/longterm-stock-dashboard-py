# Kubernetes-Deployment fuer Findash

Kurzanleitung. Ausfuehrliche Erlaeuterungen: `docs/deployment.md`.

## 1. Image bauen

```bash
# Beispiel: lokaler Registry oder GitHub Container Registry
IMAGE=ghcr.io/<owner>/findash:0.1.0
docker build -f docker/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"
```

Dann `image:` in `k8s/deployment.yaml` auf `$IMAGE` setzen (oder per `kubectl set image` patchen).

## 2. Namespace & Secret

```bash
kubectl apply -f k8s/namespace.yaml

# Secret NICHT aus dem Beispiel-Yaml (Passwort!), sondern imperativ:
kubectl -n dashboard create secret generic dataserver-credentials \
  --from-literal=DATASERVER_URL='postgresql+psycopg://readonly_user:<PW>@<MAC_MINI_IP>:5432/dataserver'
```

## 3. Deployment & Service

```bash
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
# optional, wenn ein Ingress-Controller vorhanden ist:
kubectl apply -f k8s/ingress.yaml
```

## 4. Rollout beobachten

```bash
kubectl -n dashboard rollout status deploy/findash
kubectl -n dashboard get pods -l app.kubernetes.io/name=findash
```

## 5. Zugriff pruefen

```bash
kubectl -n dashboard port-forward svc/findash 5000:5000
curl -s http://localhost:5000/healthz | jq
curl -s http://localhost:5000/readyz  | jq   # 503, wenn dataserver nicht erreichbar
```

Danach `http://localhost:5000/etf` im Browser oeffnen.

## Netzwerk-Voraussetzung

Der Dataserver akzeptiert `readonly_user` nur aus `192.168.179.0/24` (pg_hba.conf).
Der Cluster muss aus diesem Subnetz nach `192.168.179.x:5432` heraus verbinden koennen,
oder die pg_hba wird um das Cluster-Subnetz erweitert. Ohne Netzwerkzugang liefert
`/readyz` dauerhaft 503 und die ETF-Seiten zeigen Warnhinweise (keine erfundenen Daten).
