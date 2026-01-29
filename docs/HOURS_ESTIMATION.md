# Migration Hours Estimation

## How We Calculate Hours

The v2 estimate provides defensible hours ranges based on component analysis.
Ranges are designed to be **tight and realistic** - the high estimate is capped at 2x the low estimate.

### 1. Repository Transfer Baseline (0.5 - 2.5h)

| Repo Type | Hours |
|-----------|-------|
| Archived | 0.5 - 0.75h |
| Active (small, <20 branches) | 1.0 - 1.5h |
| Active (medium, 20-50 branches) | 1.5 - 2.0h |
| Active (large, >50 branches) | 2.0 - 2.5h |

**Additional factors:**
- Git Submodules: +0.5-1h buffer (requires manual verification)
- Git LFS: +0.5-1h (data migration)

### 2. CI Conversion (0 - 22h)

| Complexity | Criteria | Hours |
|------------|----------|-------|
| None | No CI | 0h |
| Simple | Basic jobs only | 2-3h |
| Medium | rules, artifacts, cache, variables | 4-6h |
| Complex | needs (DAG), matrix, custom runners | 8-12h |
| Extreme | triggers, DinD, heavy includes | 15-22h |

**Complexity markers:**
- \`includes\` / \`extends\` templates
- \`needs\` (DAG dependencies)
- \`parallel\` / \`matrix\`
- \`trigger\` (child pipelines)
- \`services\` with docker-in-docker
- Custom runner \`tags\`

### 3. Metadata Migration (0 - 3h per type)

Migration of issues and MRs is mostly automated via GitHub's importer.

**Issues:**
| Volume | Hours |
|--------|-------|
| < 100 total | 0 - 0.25h |
| 100 - 500 | 0.25 - 0.5h |
| 500 - 2000 | 0.5 - 1.5h |
| > 2000 | 1.5 - 3h |

**Merge Requests:**
| Volume | Hours |
|--------|-------|
| < 50 total | 0 - 0.25h |
| 50 - 200 | 0.25 - 0.5h |
| 200 - 1000 | 0.5 - 1.5h |
| > 1000 | 1.5 - 3h |

### 4. Governance Hardening (0 - 1.5h)

| Feature | Hours |
|---------|-------|
| Protected branches | 0.5 - 1h |
| CODEOWNERS file | 0.25 - 0.5h |

### 5. Integrations (0 - 7h)

| Integration | Hours |
|-------------|-------|
| Webhooks | 0.5 - 1h |
| GitLab Pages | 1.5 - 2.5h |
| Container Registry | 1 - 2h |
| Wiki | 0.5 - 1h |
| Releases | 0.25 - 0.5h |

### 6. Unknowns Buffer

For each unknown value (permissions denied, API limits exceeded):
- **+8%** added to the high estimate (capped at 25% total)
- Confidence level decreases

### 7. Range Cap

To ensure realistic estimates, the **high estimate is capped at 2x the low estimate**.
This prevents unrealistic spreads like "5h - 50h".

---

## Confidence Levels

| Level | Criteria |
|-------|----------|
| **High** | All data collected, no permission issues |
| **Medium** | 1-2 unknowns or minor permission gaps |
| **Low** | CI/variables/protections unknown, repeated 403s |

---

## Permissions Needed for High Confidence

To achieve "high" confidence estimates, the API token needs these permissions:

| Permission | Why Needed |
|------------|-----------|
| \`read_repository\` | Read .gitlab-ci.yml, .gitmodules, CODEOWNERS |
| \`read_api\` | Basic project/group listing |
| \`api\` (full) | CI variables count, protected branches |
| Project Maintainer+ | Webhooks count |

---

## Example Calculations

### Simple Repository (Archived)
- Baseline: 0.5h - 0.75h
- No CI, no integrations
- **Total: 0.5h - 0.75h** (1.5x range)

### Medium Repository (Active, with CI)
- Baseline: 1h - 1.5h
- CI (medium): 4h - 6h
- Issues (small): 0h - 0.25h
- MRs (small): 0h - 0.25h
- Protected branches: 0.5h - 1h
- **Total: 5.5h - 9h** (1.6x range)

### Complex Repository (Enterprise)
- Baseline: 2h - 2.5h
- CI (extreme): 15h - 22h
- Issues (huge): 1.5h - 3h
- MRs (large): 0.5h - 1.5h
- Governance: 0.75h - 1.5h
- Registry: 1h - 2h
- Pages: 1.5h - 2.5h
- **Subtotal: 22.25h - 35h**
- Range cap applied: **22.25h - 44.5h** (2x cap)

---

## Performance: Parallel Analysis

Deep analysis can run in parallel for faster results. Set the environment variable:

\`\`\`bash
# Default: 4 workers
export DISCOVERY_PARALLEL_WORKERS=8
\`\`\`

Higher values = faster, but may hit API rate limits.

---

## Usage in SOW

The hours estimate should be used for:
1. **Fixed-price quotes**: Use the high estimate + 10% buffer
2. **T&M estimates**: Use the range as-is
3. **Risk assessment**: Projects with "low" confidence need discovery phase

Remember: These are **migration hours only** - they don't include:
- Testing and validation
- Team training
- Documentation updates
- Production cutover planning
