# Security Configuration and Best Practices

## Overview

This document outlines security configurations, best practices, and hardening measures for the Discovery Agent.

## Security Headers

### HTTP Security Headers

Configure these headers for any web interfaces:

```python
# Security headers configuration
SECURITY_HEADERS = {
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1; mode=block",
    "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
    "Content-Security-Policy": "default-src 'self'",
    "Referrer-Policy": "strict-origin-when-cross-origin",
    "Permissions-Policy": "geolocation=(), microphone=(), camera=()",
}
```

### CORS Configuration

```python
# CORS configuration for API endpoints
CORS_CONFIG = {
    "allowed_origins": [
        "https://your-domain.com",
    ],
    "allowed_methods": ["GET", "OPTIONS"],
    "allowed_headers": ["Content-Type", "Authorization"],
    "max_age": 3600,
    "allow_credentials": False,
}
```

## Secrets Management

### Environment Variables

**Never commit secrets to version control**

```bash
# Good - Use environment variables
GITLAB_TOKEN=${GITLAB_TOKEN}

# Bad - Hardcoded secrets
GITLAB_TOKEN="glpat-xxx..."  # NEVER DO THIS
```

### Docker Secrets

```yaml
# docker-compose.yml
services:
  discovery-agent:
    secrets:
      - gitlab_token
    environment:
      GITLAB_TOKEN_FILE: /run/secrets/gitlab_token

secrets:
  gitlab_token:
    external: true
```

### Kubernetes Secrets

```bash
# Create secret from file
kubectl create secret generic discovery-agent-secrets \
  --from-file=gitlab-token=./gitlab-token.txt \
  -n discovery-agent

# Reference in deployment
env:
  - name: GITLAB_TOKEN
    valueFrom:
      secretKeyRef:
        name: discovery-agent-secrets
        key: gitlab-token
```

### External Secrets Management

Use external secret managers for production:

**HashiCorp Vault**:
```hcl
path "secret/discovery-agent/*" {
  capabilities = ["read", "list"]
}
```

**AWS Secrets Manager**:
```bash
aws secretsmanager create-secret \
  --name discovery-agent/gitlab-token \
  --secret-string "glpat-xxx"
```

**Azure Key Vault**:
```bash
az keyvault secret set \
  --vault-name discovery-agent-kv \
  --name gitlab-token \
  --value "glpat-xxx"
```

## Token Security

### Token Requirements

1. **Use minimal scopes**:
   - `read_api` - For reading GitLab data
   - `read_repository` - For reading repository files
   - Do NOT use `write_*` scopes

2. **Set expiration**:
   - Maximum: 90 days
   - Recommended: 30 days
   - Auto-rotate before expiry

3. **Use project/group tokens** instead of personal tokens when possible

### Token Rotation

```bash
# Automated token rotation script
#!/bin/bash
set -e

OLD_TOKEN="${GITLAB_TOKEN}"
NEW_TOKEN="${NEW_GITLAB_TOKEN}"

# Verify new token works
curl -f -H "PRIVATE-TOKEN: ${NEW_TOKEN}" https://gitlab.com/api/v4/user

# Update secrets
kubectl create secret generic discovery-agent-secrets \
  --from-literal=GITLAB_TOKEN="${NEW_TOKEN}" \
  --dry-run=client -o yaml | kubectl apply -f -

# Restart service
kubectl rollout restart deployment/discovery-agent -n discovery-agent

# Revoke old token after verification
# curl -X DELETE -H "PRIVATE-TOKEN: ${NEW_TOKEN}" \
#   "https://gitlab.com/api/v4/personal_access_tokens/${OLD_TOKEN_ID}"
```

### Token Storage

**Never log tokens**:
```python
# Good - Mask secrets in logs
logger.info(f"Using token: {token[:8]}...")

# Bad - Full token in logs
logger.info(f"Using token: {token}")  # NEVER DO THIS
```

## Network Security

### TLS/SSL Configuration

```python
# Enforce TLS 1.2+
import ssl
import requests

session = requests.Session()
session.mount('https://', requests.adapters.HTTPAdapter(
    max_retries=3,
    ssl_context=ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
))
```

### Firewall Rules

**Outbound Rules** (whitelist):
```bash
# Allow HTTPS to GitLab only
iptables -A OUTPUT -d gitlab.com -p tcp --dport 443 -j ACCEPT
iptables -A OUTPUT -p tcp --dport 443 -j DROP
```

**Inbound Rules**:
```bash
# Allow health checks and metrics
iptables -A INPUT -p tcp --dport 8080 -s 10.0.0.0/8 -j ACCEPT  # Health
iptables -A INPUT -p tcp --dport 9090 -s 10.0.0.0/8 -j ACCEPT  # Metrics
iptables -A INPUT -p tcp -j DROP
```

### Network Policies (Kubernetes)

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: discovery-agent-netpol
  namespace: discovery-agent
spec:
  podSelector:
    matchLabels:
      app: discovery-agent
  policyTypes:
    - Ingress
    - Egress
  ingress:
    - from:
        - namespaceSelector:
            matchLabels:
              name: monitoring
      ports:
        - protocol: TCP
          port: 9090
    - from:
        - namespaceSelector:
            matchLabels:
              name: kube-system
      ports:
        - protocol: TCP
          port: 8080
  egress:
    - to:
        - namespaceSelector: {}
      ports:
        - protocol: TCP
          port: 443
    - to:
        - namespaceSelector: {}
          podSelector:
            matchLabels:
              k8s-app: kube-dns
      ports:
        - protocol: UDP
          port: 53
```

## Audit Logging

### Log All API Calls

```python
import logging
import hashlib

def audit_log_api_call(
    endpoint: str,
    method: str,
    status_code: int,
    user_token_hash: str,
    duration_ms: float,
):
    """Log API call for audit purposes."""
    logger.info(
        "API_AUDIT",
        extra={
            "event_type": "api_call",
            "endpoint": endpoint,
            "method": method,
            "status_code": status_code,
            "user_token_hash": user_token_hash,
            "duration_ms": duration_ms,
            "timestamp": datetime.utcnow().isoformat(),
        },
    )

# Hash token for identification without exposing it
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()[:16]
```

### Audit Log Format

```json
{
  "timestamp": "2024-01-29T12:00:00Z",
  "event_type": "api_call",
  "endpoint": "/api/v4/projects",
  "method": "GET",
  "status_code": 200,
  "user_token_hash": "a1b2c3d4e5f6g7h8",
  "duration_ms": 123.45,
  "source_ip": "10.0.1.5",
  "user_agent": "discovery-agent/0.1.0"
}
```

## Container Security

### Run as Non-Root

```dockerfile
# Dockerfile
RUN groupadd -r discovery && useradd -r -g discovery -u 1000 discovery
USER discovery
```

### Read-Only Root Filesystem

```yaml
# k8s/deployment.yaml
securityContext:
  readOnlyRootFilesystem: true
  runAsNonRoot: true
  runAsUser: 1000
  allowPrivilegeEscalation: false
  capabilities:
    drop:
      - ALL
```

### Scan Images for Vulnerabilities

```bash
# Using Trivy
trivy image discovery-agent:latest

# Using Grype
grype discovery-agent:latest

# Using Snyk
snyk container test discovery-agent:latest
```

## Dependency Security

### Pin Dependencies

```toml
# pyproject.toml
dependencies = [
    "requests==2.31.0",  # Pin exact versions
    "python-dotenv==1.0.0",
    "jsonschema==4.20.0",
]
```

### Scan Dependencies

```bash
# Using pip-audit
pip-audit

# Using Safety
safety check

# Using Snyk
snyk test --file=pyproject.toml
```

### Update Dependencies Regularly

```bash
# Check for updates
pip list --outdated

# Update dependencies
pip install --upgrade requests python-dotenv

# Re-run security scans after updates
```

## RBAC (Kubernetes)

### Principle of Least Privilege

```yaml
# k8s/rbac.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: discovery-agent
  namespace: discovery-agent
rules:
  # Only allow reading configmaps and secrets
  - apiGroups: [""]
    resources: ["configmaps", "secrets"]
    verbs: ["get", "list"]
    
  # Do NOT allow:
  # - Creating/updating/deleting resources
  # - Accessing other namespaces
  # - Cluster-wide permissions
```

## Data Protection

### Encrypt Data at Rest

**Docker Volumes**:
```bash
# Use encrypted filesystem
cryptsetup luksFormat /dev/sdb
cryptsetup luksOpen /dev/sdb discovery-data
mkfs.ext4 /dev/mapper/discovery-data
mount /dev/mapper/discovery-data /var/lib/docker/volumes/discovery-data
```

**Kubernetes PVC**:
```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: discovery-agent-data
spec:
  storageClassName: encrypted-ssd  # Use encrypted storage class
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 10Gi
```

### Encrypt Data in Transit

All communications use HTTPS/TLS:
- GitLab API: HTTPS only
- Internal services: TLS for production
- Metrics/health: Consider TLS termination at ingress

### Data Retention

```bash
# Automated cleanup script
#!/bin/bash
# Remove data older than 90 days
find /data/output -type f -mtime +90 -delete

# Archive old data
tar czf /backup/archive-$(date +%Y%m%d).tar.gz \
  $(find /data/output -type f -mtime +30 -mtime -90)
```

## Incident Response

### Security Incident Checklist

1. **Detect**: Alert triggered or suspicious activity noticed
2. **Contain**: Isolate affected systems
3. **Investigate**: Collect logs and evidence
4. **Remediate**: Fix vulnerability, rotate secrets
5. **Recover**: Restore service
6. **Review**: Postmortem and improvements

### Security Contact

- **Security Team**: security@example.com
- **PagerDuty**: Security on-call
- **Vulnerability Disclosure**: security@example.com (PGP key available)

## Compliance

### GDPR Compliance

- **Data Minimization**: Only collect necessary data
- **Purpose Limitation**: Use data only for discovery
- **Storage Limitation**: Delete data after retention period
- **Right to Erasure**: Provide data deletion mechanism

### SOC 2 Compliance

- **Access Controls**: RBAC, MFA, least privilege
- **Audit Logging**: All access logged
- **Encryption**: Data encrypted at rest and in transit
- **Monitoring**: 24/7 monitoring and alerting
- **Incident Response**: Documented procedures

## Security Checklist

### Pre-Deployment

- [ ] All secrets stored securely (not in code)
- [ ] Dependencies scanned for vulnerabilities
- [ ] Container images scanned
- [ ] RBAC configured with least privilege
- [ ] Network policies defined
- [ ] Security headers configured
- [ ] TLS/SSL certificates valid
- [ ] Audit logging enabled
- [ ] Backup and recovery tested

### Post-Deployment

- [ ] Monitor security alerts
- [ ] Review audit logs regularly
- [ ] Rotate secrets on schedule
- [ ] Update dependencies monthly
- [ ] Scan for vulnerabilities weekly
- [ ] Review access logs
- [ ] Test incident response quarterly
- [ ] Security training for team

## Security Tools

### Recommended Tools

1. **Vulnerability Scanning**:
   - Trivy: Container image scanning
   - Snyk: Dependency scanning
   - OWASP Dependency-Check

2. **Secret Detection**:
   - git-secrets: Prevent committing secrets
   - TruffleHog: Find secrets in git history
   - detect-secrets: Pre-commit hook

3. **Code Analysis**:
   - Bandit: Python security linter
   - Semgrep: Static analysis
   - CodeQL: Security queries

4. **Runtime Protection**:
   - Falco: Runtime security
   - AppArmor/SELinux: Mandatory access control
   - Seccomp: System call filtering

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [CIS Docker Benchmark](https://www.cisecurity.org/benchmark/docker)
- [CIS Kubernetes Benchmark](https://www.cisecurity.org/benchmark/kubernetes)
- [NIST Cybersecurity Framework](https://www.nist.gov/cyberframework)
