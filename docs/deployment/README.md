# Deployment Guide

## Table of Contents

1. [Prerequisites](#prerequisites)
2. [Deployment Options](#deployment-options)
3. [Docker Deployment](#docker-deployment)
4. [Kubernetes Deployment](#kubernetes-deployment)
5. [Configuration](#configuration)
6. [Security](#security)
7. [Monitoring](#monitoring)

## Prerequisites

### System Requirements

- **CPU**: 2+ cores recommended
- **Memory**: 2GB+ RAM recommended
- **Storage**: 10GB+ for data and logs
- **Network**: Outbound HTTPS access to GitLab instance

### Software Requirements

- Python 3.10+ (for local deployment)
- Docker 20.10+ and Docker Compose 2.0+ (for Docker deployment)
- Kubernetes 1.24+ (for Kubernetes deployment)
- kubectl configured with cluster access

### GitLab Access

- GitLab Personal Access Token with scopes:
  - `read_api`
  - `read_repository`

## Deployment Options

### Option 1: Local Development

```bash
# Clone repository
git clone https://github.com/your-org/gl2gh.git
cd gl2gh

# Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -e ".[all]"

# Configure environment
cp .env.example .env
# Edit .env with your GitLab credentials

# Run discovery agent
python -m discovery_agent
```

### Option 2: Docker Compose (Recommended for Production)

See [Docker Deployment](#docker-deployment) section below.

### Option 3: Kubernetes

See [Kubernetes Deployment](#kubernetes-deployment) section below.

## Docker Deployment

### Quick Start

```bash
# Clone repository
git clone https://github.com/your-org/gl2gh.git
cd gl2gh

# Create environment file
cat > .env << EOF
GITLAB_BASE_URL=https://gitlab.com
GITLAB_TOKEN=glpat-xxxxxxxxxxxxxxxxxxxx
GITLAB_ROOT_GROUP=my-organization
LOG_LEVEL=INFO
JSON_LOGGING=true
ENVIRONMENT=production
EOF

# Start services
docker-compose -f docker-compose.production.yml up -d

# Check status
docker-compose -f docker-compose.production.yml ps

# View logs
docker-compose -f docker-compose.production.yml logs -f discovery-agent
```

### Services

The production Docker Compose setup includes:

1. **discovery-agent**: Main application
2. **prometheus**: Metrics collection
3. **grafana**: Visualization dashboards
4. **alertmanager**: Alert routing and management

### Accessing Services

- **Grafana**: http://localhost:3000 (admin/changeme)
- **Prometheus**: http://localhost:9091
- **AlertManager**: http://localhost:9093
- **Metrics**: http://localhost:9090/metrics
- **Health Check**: http://localhost:8080/health

### Stopping Services

```bash
docker-compose -f docker-compose.production.yml down
```

### Backup Data

```bash
# Backup volumes
docker-compose -f docker-compose.production.yml down
docker run --rm -v gl2gh_discovery-data:/data -v $(pwd)/backup:/backup ubuntu tar czf /backup/discovery-data-$(date +%Y%m%d).tar.gz /data

# Restore
docker run --rm -v gl2gh_discovery-data:/data -v $(pwd)/backup:/backup ubuntu tar xzf /backup/discovery-data-YYYYMMDD.tar.gz -C /
```

## Kubernetes Deployment

### Prerequisites

```bash
# Verify kubectl access
kubectl cluster-info
kubectl get nodes
```

### Deploy

```bash
# Create namespace
kubectl apply -f k8s/namespace.yaml

# Create secrets (update with your values first!)
kubectl apply -f k8s/secret.yaml

# Create configmap
kubectl apply -f k8s/configmap.yaml

# Create RBAC
kubectl apply -f k8s/rbac.yaml

# Create PVC
kubectl apply -f k8s/pvc.yaml

# Create service
kubectl apply -f k8s/service.yaml

# Create deployment
kubectl apply -f k8s/deployment.yaml

# Verify deployment
kubectl get pods -n discovery-agent
kubectl get svc -n discovery-agent
```

### Check Status

```bash
# View pods
kubectl get pods -n discovery-agent

# View logs
kubectl logs -f deployment/discovery-agent -n discovery-agent

# Check health
kubectl exec -it deployment/discovery-agent -n discovery-agent -- curl localhost:8080/health
```

### Update Deployment

```bash
# Update image
kubectl set image deployment/discovery-agent \
  discovery-agent=discovery-agent:v0.2.0 \
  -n discovery-agent

# Monitor rollout
kubectl rollout status deployment/discovery-agent -n discovery-agent

# Rollback if needed
kubectl rollout undo deployment/discovery-agent -n discovery-agent
```

### Delete Deployment

```bash
# Delete all resources
kubectl delete -f k8s/ -n discovery-agent

# Delete namespace (WARNING: deletes all data)
kubectl delete namespace discovery-agent
```

## Configuration

### Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GITLAB_BASE_URL` | Yes | - | GitLab instance URL |
| `GITLAB_TOKEN` | Yes | - | Personal access token |
| `GITLAB_ROOT_GROUP` | No | - | Root group to scan |
| `OUTPUT_DIR` | No | `/data/output` | Output directory |
| `MAX_API_CALLS` | No | `5000` | Max total API calls |
| `MAX_PER_PROJECT_CALLS` | No | `200` | Max calls per project |
| `LOG_LEVEL` | No | `INFO` | Log level |
| `JSON_LOGGING` | No | `false` | Enable JSON logging |
| `ENVIRONMENT` | No | `development` | Environment name |

### Secrets Management

#### Docker Secrets

```bash
# Create secrets
echo "glpat-xxx" | docker secret create gitlab_token -

# Update docker-compose.yml to use secrets
secrets:
  - gitlab_token
```

#### Kubernetes Secrets

```bash
# Create from literal
kubectl create secret generic discovery-agent-secrets \
  --from-literal=GITLAB_TOKEN=glpat-xxx \
  --from-literal=GITLAB_BASE_URL=https://gitlab.com \
  -n discovery-agent

# Create from file
kubectl create secret generic discovery-agent-secrets \
  --from-env-file=.env \
  -n discovery-agent

# View secret (base64 decoded)
kubectl get secret discovery-agent-secrets -n discovery-agent -o jsonpath='{.data.GITLAB_TOKEN}' | base64 -d
```

#### External Secrets (Recommended)

Use [External Secrets Operator](https://external-secrets.io/) with HashiCorp Vault, AWS Secrets Manager, or Azure Key Vault.

## Security

### Network Security

1. **Firewall Rules**: Only allow outbound HTTPS (443) to GitLab
2. **Internal Network**: Run on private network, expose only necessary ports
3. **TLS/SSL**: Use TLS for all external communications

### Access Control

1. **GitLab Token**: Use least-privilege token (read-only scopes)
2. **Token Rotation**: Rotate tokens regularly (90 days)
3. **Service Account**: Run as non-root user (UID 1000)

### Security Headers

The application sets the following security headers:

- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Strict-Transport-Security: max-age=31536000`

### Audit Logging

All API calls are logged with:
- Timestamp
- Endpoint
- Status code
- Duration
- User/token identifier (hashed)

## Monitoring

### Health Checks

- **Liveness**: `GET /health/live` - Is the service running?
- **Readiness**: `GET /health/ready` - Is the service ready to accept requests?
- **Health**: `GET /health` - Full health status with dependencies

### Metrics

Prometheus metrics are exposed at `/metrics`:

```bash
# View metrics
curl http://localhost:9090/metrics
```

Key metrics:
- `gitlab_api_requests_total` - Total API requests
- `gitlab_api_request_duration_seconds` - API latency
- `discovery_projects_total` - Projects discovered
- `discovery_errors_total` - Discovery errors

### Alerts

Configure AlertManager for critical events:

1. **ServiceDown**: Service is unavailable
2. **HighErrorRate**: Error rate > 10%
3. **APIRateLimitExhausted**: GitLab rate limit hit
4. **HighAPILatency**: p95 latency > 2s

See `monitoring/alerts.yml` for full alert definitions.

## Troubleshooting

### Common Issues

**Connection refused to GitLab**
```bash
# Test connectivity
curl -I https://gitlab.com/api/v4/version

# Check token
curl -H "PRIVATE-TOKEN: your-token" https://gitlab.com/api/v4/user
```

**Rate limit errors**
- Reduce `MAX_API_CALLS` or `MAX_PER_PROJECT_CALLS`
- Wait for rate limit to reset
- Use multiple tokens (not recommended)

**Out of memory**
- Increase memory limits in deployment
- Reduce concurrent operations
- Process fewer projects per run

### Getting Help

1. Check logs: `docker-compose logs -f` or `kubectl logs -f`
2. Check metrics: Open Grafana dashboard
3. Check health: `curl http://localhost:8080/health`
4. Review [Troubleshooting Guide](../operations/troubleshooting.md)
