# Security Advisory - Dependency Updates

## Date: 2024-01-29
**Last Updated**: 2026-01-29

## Summary
Updated multiple dependencies to address security vulnerabilities and compatibility issues identified in the initial dependency set.

## Compatibility Issues Fixed

### bcrypt Version Pinning (Pinned to 4.0.1)

#### Compatibility Issue: bcrypt 4.1.0+ breaks passlib 1.7.4
- **Severity**: High (breaks authentication)
- **Affected Versions**: bcrypt >= 4.1.0 with passlib 1.7.4
- **Fix**: Pin bcrypt to 4.0.1
- **Description**: bcrypt version 4.1.0 and later introduced stricter password length validation and removed internal attributes that passlib 1.7.4 depends on. This causes `ValueError: password cannot be longer than 72 bytes` and `AttributeError: module 'bcrypt' has no attribute '__about__'` errors during authentication operations.
- **Impact**: Complete authentication failure - users cannot log in, password hashing fails.
- **Root Cause**: 
  - bcrypt 4.1.0+ enforces strict 72-byte password limit (per bcrypt specification)
  - bcrypt 4.1.0+ removed the `__about__.__version__` attribute that passlib uses for version detection
  - passlib 1.7.4 (last official release) was written before these changes and doesn't handle them gracefully
- **Solution Applied**: Added explicit `bcrypt==4.0.1` pin to `backend/requirements.txt`
- **Long-term Options**:
  1. **Wait for official passlib update** (none available as of 2026-01-29)
  2. **Consider community forks** like `notypecheck/passlib` that support bcrypt 4.1+
  3. **Migrate to direct bcrypt usage** or modern alternatives like argon2id
  4. **Keep current pin** (safest option for production stability)

## Vulnerabilities Fixed

### 1. cryptography (41.0.7 → 42.0.4)

#### CVE-2024-XXXX: NULL Pointer Dereference
- **Severity**: High
- **Affected Versions**: >= 38.0.0, < 42.0.4
- **Patched Version**: 42.0.4
- **Description**: NULL pointer dereference with `pkcs12.serialize_key_and_certificates` when called with a non-matching certificate and private key and an hmac_hash override.
- **Impact**: Could cause application crashes or denial of service.

#### CVE-2023-XXXX: Bleichenbacher Timing Oracle Attack
- **Severity**: High
- **Affected Versions**: < 42.0.0
- **Patched Version**: 42.0.0 (updated to 42.0.4)
- **Description**: Python Cryptography package vulnerable to Bleichenbacher timing oracle attack.
- **Impact**: Could allow attackers to decrypt RSA ciphertext through timing analysis.

### 2. fastapi (0.109.0 → 0.109.1)

#### CVE-2024-XXXX: Content-Type Header ReDoS
- **Severity**: Medium
- **Affected Versions**: <= 0.109.0
- **Patched Version**: 0.109.1
- **Description**: FastAPI vulnerable to Regular Expression Denial of Service (ReDoS) via Content-Type header parsing.
- **Impact**: Could cause excessive CPU usage and service degradation through malicious Content-Type headers.

### 3. python-multipart (0.0.6 → 0.0.22)

#### CVE-2024-XXXX: Arbitrary File Write
- **Severity**: Critical
- **Affected Versions**: < 0.0.22
- **Patched Version**: 0.0.22
- **Description**: Arbitrary file write vulnerability via non-default configuration in multipart/form-data handling.
- **Impact**: Could allow attackers to write arbitrary files to the server filesystem.

#### CVE-2024-XXXX: Denial of Service (DoS)
- **Severity**: High
- **Affected Versions**: < 0.0.18
- **Patched Version**: 0.0.18 (updated to 0.0.22)
- **Description**: DoS via malformed multipart/form-data boundary.
- **Impact**: Could cause application crashes or resource exhaustion.

#### CVE-2023-XXXX: Content-Type Header ReDoS
- **Severity**: Medium
- **Affected Versions**: <= 0.0.6
- **Patched Version**: 0.0.7 (updated to 0.0.22)
- **Description**: ReDoS vulnerability in Content-Type header parsing.
- **Impact**: Could cause excessive CPU usage through malicious headers.

## Actions Taken

1. **Pinned bcrypt**: 4.0.1 (compatibility fix)
   - Prevents authentication failures with passlib 1.7.4
   - Blocks automatic upgrade to incompatible bcrypt 4.1+
   - Maintains stable password hashing functionality

2. **Updated cryptography**: 41.0.7 → 42.0.4
   - Fixes NULL pointer dereference
   - Fixes Bleichenbacher timing oracle attack

3. **Updated fastapi**: 0.109.0 → 0.109.1
   - Fixes Content-Type header ReDoS

4. **Updated python-multipart**: 0.0.6 → 0.0.22
   - Fixes arbitrary file write vulnerability
   - Fixes DoS via malformed boundary
   - Fixes Content-Type header ReDoS

## Verification

After updating, verify the changes:

```bash
# Rebuild Docker containers
./start.sh stop
./start.sh build
./start.sh up

# Verify no vulnerabilities
pip-audit  # If available

# Check application functionality
./health-check.sh
```

## Recommendations

### For Development
1. Always use the latest stable versions of dependencies
2. Regularly run security audits: `pip-audit` or `safety check`
3. Subscribe to security advisories for critical dependencies
4. Use Dependabot or Renovate for automated dependency updates

### For Production
1. Rebuild all Docker images with updated dependencies
2. Deploy updated containers to all environments
3. Monitor application logs for any issues after update
4. Conduct security scan after deployment

## Testing

These updates have been tested for:
- ✅ Compatibility with existing code
- ✅ No breaking API changes
- ✅ Docker build succeeds
- ✅ Application starts correctly

## References

- [cryptography changelog](https://cryptography.io/en/latest/changelog/)
- [FastAPI security advisories](https://github.com/tiangolo/fastapi/security/advisories)
- [python-multipart releases](https://github.com/andrew-d/python-multipart/releases)

## Impact Assessment

### Low Risk Updates
These updates are **backward compatible** and do not introduce breaking changes:
- cryptography 42.0.4 is a patch release
- fastapi 0.109.1 is a patch release
- python-multipart 0.0.22 maintains API compatibility

### No Code Changes Required
All updates are drop-in replacements. No application code changes are needed.

## Future Prevention

1. **Add dependency scanning to CI/CD**:
   ```yaml
   # .github/workflows/security.yml
   - name: Run pip-audit
     run: pip-audit --requirement backend/requirements.txt
   ```

2. **Enable Dependabot**:
   ```yaml
   # .github/dependabot.yml
   version: 2
   updates:
     - package-ecosystem: "pip"
       directory: "/backend"
       schedule:
         interval: "weekly"
   ```

3. **Regular Security Reviews**:
   - Weekly automated scans
   - Monthly manual review of dependencies
   - Immediate response to critical CVEs

## Status

✅ **All vulnerabilities addressed**
✅ **Updated to patched versions**
✅ **Backward compatible updates**
✅ **No code changes required**
✅ **bcrypt compatibility issue resolved**
✅ **Ready for deployment**

---

**Last Updated**: 2026-01-29
**Next Review**: 2026-02-29
