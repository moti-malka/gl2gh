# Package Migration Guide

This guide explains how to migrate GitLab packages to GitHub Packages and configure your projects to consume them.

## Overview

The gl2gh platform now supports migrating packages from GitLab to GitHub Packages. This includes:
- **Supported Package Types**: npm, Maven, NuGet (automatically migrated)
- **Unsupported Package Types**: PyPI, Composer, Conan, Generic (require manual migration)

## Migration Process

### 1. Export Phase

During export, the tool will:
- Download package files from GitLab Package Registry
- Create an inventory of all packages with types and sizes
- Store packages in the export directory structure:
  ```
  export/packages/
  ├── packages.json          # Metadata for all packages
  ├── inventory.json         # Summary report
  ├── npm/
  │   └── package-name/
  │       └── 1.0.0/
  │           └── package-name-1.0.0.tgz
  ├── maven/
  │   └── artifact-name/
  │       └── 2.0.0/
  │           ├── artifact-name-2.0.0.jar
  │           └── artifact-name-2.0.0.pom
  └── nuget/
      └── PackageName/
          └── 3.0.0/
              └── PackageName.3.0.0.nupkg
  ```

### 2. Apply Phase

During the apply phase, the tool will generate actions for each package:
- **Supported packages**: Provide manual setup instructions with authentication
- **Unsupported packages**: Report as gaps requiring alternative solutions

## Supported Package Types

### npm Packages

#### GitHub Packages Setup

1. **Authenticate with GitHub Packages**
   ```bash
   npm login --registry=https://npm.pkg.github.com
   # Username: YOUR_GITHUB_USERNAME
   # Password: YOUR_GITHUB_TOKEN (with write:packages scope)
   ```

2. **Configure .npmrc** in your project:
   ```
   @OWNER:registry=https://npm.pkg.github.com
   ```

3. **Publish Package**
   ```bash
   npm publish path/to/package.tgz
   ```

#### Consumer Configuration

Update `package.json`:
```json
{
  "name": "@OWNER/package-name",
  "version": "1.0.0"
}
```

Create/update `.npmrc`:
```
@OWNER:registry=https://npm.pkg.github.com
//npm.pkg.github.com/:_authToken=${NPM_TOKEN}
```

Install packages:
```bash
export NPM_TOKEN=your_github_token
npm install @OWNER/package-name
```

### Maven Packages

#### GitHub Packages Setup

1. **Configure Maven settings** (`~/.m2/settings.xml`):
   ```xml
   <settings>
     <servers>
       <server>
         <id>github</id>
         <username>YOUR_GITHUB_USERNAME</username>
         <password>YOUR_GITHUB_TOKEN</password>
       </server>
     </servers>
   </settings>
   ```

2. **Update pom.xml** for publishing:
   ```xml
   <distributionManagement>
     <repository>
       <id>github</id>
       <name>GitHub Packages</name>
       <url>https://maven.pkg.github.com/OWNER/REPO</url>
     </repository>
   </distributionManagement>
   ```

3. **Publish Package**
   ```bash
   mvn deploy
   ```

#### Consumer Configuration

Add to `pom.xml`:
```xml
<repositories>
  <repository>
    <id>github</id>
    <url>https://maven.pkg.github.com/OWNER/REPO</url>
  </repository>
</repositories>

<dependencies>
  <dependency>
    <groupId>com.example</groupId>
    <artifactId>package-name</artifactId>
    <version>2.0.0</version>
  </dependency>
</dependencies>
```

Configure authentication in `~/.m2/settings.xml` (see above).

### NuGet Packages

#### GitHub Packages Setup

1. **Authenticate with GitHub**
   ```bash
   dotnet nuget add source https://nuget.pkg.github.com/OWNER/index.json \
     -n github \
     -u YOUR_GITHUB_USERNAME \
     -p YOUR_GITHUB_TOKEN \
     --store-password-in-clear-text
   ```

2. **Publish Package**
   ```bash
   dotnet nuget push path/to/package.nupkg --source github
   ```

#### Consumer Configuration

Add to `nuget.config`:
```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <add key="github" value="https://nuget.pkg.github.com/OWNER/index.json" />
  </packageSources>
  <packageSourceCredentials>
    <github>
      <add key="Username" value="YOUR_GITHUB_USERNAME" />
      <add key="ClearTextPassword" value="YOUR_GITHUB_TOKEN" />
    </github>
  </packageSourceCredentials>
</configuration>
```

Install packages:
```bash
dotnet add package PackageName --source github
```

## Unsupported Package Types

The following GitLab package types do not have direct GitHub Packages equivalents:

### PyPI (Python)

**Alternatives:**
1. Use PyPI.org for public packages
2. Use private PyPI server (e.g., devpi, Nexus)
3. Use GitHub Releases with wheel/sdist files

**Manual Steps:**
```bash
# Build package
python -m build

# Upload to PyPI
python -m twine upload dist/*
```

### Composer (PHP)

**Alternatives:**
1. Use Packagist.org for public packages
2. Use private Composer repository
3. Use GitHub with composer.json in repository

**Manual Steps:**
Add to `composer.json`:
```json
{
  "repositories": [
    {
      "type": "vcs",
      "url": "https://github.com/OWNER/REPO"
    }
  ]
}
```

### Conan (C++)

**Alternatives:**
1. Use ConanCenter for public packages
2. Use private Artifactory/Nexus
3. Use GitHub Releases

**Manual Steps:**
```bash
# Upload to remote
conan upload package/version@user/channel --remote=your-remote
```

### Generic Packages

**Alternatives:**
1. Use GitHub Releases
2. Use external artifact storage (S3, Azure Blob)

**Manual Steps:**
```bash
# Create release with gh CLI
gh release create v1.0.0 path/to/artifact.zip
```

## CI/CD Integration

### GitHub Actions for npm

```yaml
name: Publish Package
on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-node@v3
        with:
          node-version: '18'
          registry-url: 'https://npm.pkg.github.com'
      - run: npm publish
        env:
          NODE_AUTH_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### GitHub Actions for Maven

```yaml
name: Publish Package
on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-java@v3
        with:
          java-version: '11'
          distribution: 'temurin'
      - run: mvn -B deploy
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

### GitHub Actions for NuGet

```yaml
name: Publish Package
on:
  release:
    types: [created]

jobs:
  publish:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write
    steps:
      - uses: actions/checkout@v3
      - uses: actions/setup-dotnet@v3
        with:
          dotnet-version: '7.0.x'
      - run: dotnet pack -c Release
      - run: dotnet nuget push **/*.nupkg --source https://nuget.pkg.github.com/${{ github.repository_owner }}/index.json --api-key ${{ secrets.GITHUB_TOKEN }}
```

## Authentication Best Practices

### Token Scopes Required

Your GitHub Personal Access Token (PAT) needs the following scopes:
- `read:packages` - Download packages
- `write:packages` - Upload packages
- `delete:packages` - Delete package versions (optional)

### Security Recommendations

1. **Use Environment Variables**: Never hardcode tokens in code or config files
2. **Rotate Tokens**: Regularly rotate your PATs
3. **Least Privilege**: Use tokens with minimal required scopes
4. **CI/CD Secrets**: Store tokens in GitHub Secrets, not in repository
5. **Fine-grained PATs**: Use fine-grained PATs when possible for better security

## Troubleshooting

### Common Issues

#### "401 Unauthorized" when downloading packages

**Solution**: Ensure your token has `read:packages` scope and you're authenticated:
```bash
# For npm
npm login --registry=https://npm.pkg.github.com

# For Maven
# Check ~/.m2/settings.xml credentials

# For NuGet
dotnet nuget add source ... (see above)
```

#### Packages not found after migration

**Solution**: 
1. Verify packages were published to correct repository
2. Check package visibility (private packages require authentication)
3. Confirm repository name matches in configuration

#### Large packages timing out

**Solution**:
1. Increase timeout in CI/CD pipeline
2. Consider splitting large packages
3. Use GitHub Releases for very large artifacts

## Migration Checklist

- [ ] Review inventory.json for all packages to migrate
- [ ] Identify unsupported package types
- [ ] Set up GitHub Packages authentication
- [ ] Configure package repositories (Maven, npm, NuGet)
- [ ] Publish supported packages to GitHub Packages
- [ ] Update consumer project configurations
- [ ] Test package installation from new registries
- [ ] Update CI/CD pipelines for automatic publishing
- [ ] Document alternative solutions for unsupported types
- [ ] Update team documentation with new registry URLs
- [ ] Decommission GitLab package registry (after verification)

## Support and Documentation

- [GitHub Packages Documentation](https://docs.github.com/en/packages)
- [npm GitHub Packages Guide](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-npm-registry)
- [Maven GitHub Packages Guide](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-apache-maven-registry)
- [NuGet GitHub Packages Guide](https://docs.github.com/en/packages/working-with-a-github-packages-registry/working-with-the-nuget-registry)
