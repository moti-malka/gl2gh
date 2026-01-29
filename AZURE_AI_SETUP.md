# Azure AI Setup Guide for Microsoft Agent Framework

This guide explains how to set up Azure AI to use the Microsoft Agent Framework with the gl2gh platform.

## Overview

The gl2gh platform now uses the **actual Microsoft Agent Framework** library instead of custom agent implementations. This provides:

- ✅ Production-ready agent runtime from Microsoft
- ✅ LLM-powered intelligence (optional)
- ✅ Streaming responses
- ✅ Function calling and tools
- ✅ Thread management for conversations

## Two Modes of Operation

### Mode 1: Local/Deterministic (No Azure AI Required)

**Use Case**: Development, testing, offline environments, or when you don't need LLM features.

**Configuration**: None required. Just don't set Azure AI environment variables.

**Behavior**: Agents use deterministic local implementations.

**Pros**:
- ✅ No cloud dependency
- ✅ Faster execution
- ✅ Deterministic results
- ✅ No Azure costs

**Cons**:
- ❌ No LLM intelligence
- ❌ No adaptive behavior
- ❌ No natural language understanding

### Mode 2: Azure AI/MAF (LLM-Powered Agents)

**Use Case**: Production, when you want intelligent LLM-powered agents.

**Configuration**: Requires Azure AI project and environment variables (see below).

**Behavior**: Agents use Microsoft Agent Framework with Azure OpenAI.

**Pros**:
- ✅ LLM-powered intelligence
- ✅ Adaptive behavior
- ✅ Natural language understanding
- ✅ Advanced MAF features

**Cons**:
- ❌ Requires Azure subscription
- ❌ API costs for model usage
- ❌ Requires network connectivity

---

## Setup Instructions

### Prerequisites

1. **Azure Subscription**: You need an active Azure subscription
2. **Azure CLI**: Install from [https://learn.microsoft.com/en-us/cli/azure/install-azure-cli](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli)
3. **Azure AI Project**: Create an Azure AI project in Azure AI Studio

### Step 1: Create Azure AI Project

1. Go to [Azure AI Studio](https://ai.azure.com/)
2. Create a new project or use existing
3. Note your project endpoint (e.g., `https://your-project.region.api.azureml.ms`)

### Step 2: Deploy a Model

1. In Azure AI Studio, go to your project
2. Navigate to **Deployments**
3. Create a new deployment:
   - **Model**: gpt-4o-mini (or gpt-4, gpt-3.5-turbo)
   - **Deployment name**: Note this name (e.g., `gpt-4o-mini`)
4. Wait for deployment to complete

### Step 3: Authenticate with Azure CLI

```bash
az login
```

Follow the browser prompt to authenticate.

**Verify authentication:**
```bash
az account show
```

### Step 4: Configure Environment Variables

#### Option A: Using .env file (Recommended)

1. Copy the example:
   ```bash
   cp .env.example .env
   ```

2. Edit `.env` and add your Azure AI settings:
   ```bash
   # Microsoft Agent Framework / Azure AI Configuration
   AZURE_AI_PROJECT_ENDPOINT=https://your-project.eastus2.api.azureml.ms
   AZURE_AI_MODEL_DEPLOYMENT_NAME=gpt-4o-mini
   ```

3. Important: Keep other required variables:
   ```bash
   SECRET_KEY=your-secret-key-change-this
   APP_MASTER_KEY=your-master-key-change-this
   ```

#### Option B: Using environment variables directly

```bash
export AZURE_AI_PROJECT_ENDPOINT="https://your-project.eastus2.api.azureml.ms"
export AZURE_AI_MODEL_DEPLOYMENT_NAME="gpt-4o-mini"
```

### Step 5: Start the Platform

```bash
./start.sh
```

### Step 6: Verify MAF Integration

Check the logs to verify Azure AI client initialization:

```bash
./start.sh logs backend
```

Look for:
```
INFO: Azure AI client initialized successfully
INFO: Endpoint: https://your-project.eastus2.api.azureml.ms
INFO: Model: gpt-4o-mini
```

---

## Authentication Methods

### Method 1: Azure CLI (Default - Recommended for Development)

**Setup:**
```bash
az login
```

**Pros**:
- ✅ Easy to set up
- ✅ Works locally
- ✅ Good for development

**Cons**:
- ❌ Requires interactive login
- ❌ Not suitable for automated deployments

**Configuration**: No additional environment variables needed.

### Method 2: Service Principal (Recommended for Production)

**Setup:**

1. Create a service principal:
   ```bash
   az ad sp create-for-rbac --name "gl2gh-service-principal" \
     --role "Cognitive Services OpenAI User" \
     --scopes /subscriptions/{subscription-id}/resourceGroups/{resource-group}
   ```

2. Note the output:
   ```json
   {
     "appId": "...",
     "password": "...",
     "tenant": "..."
   }
   ```

3. Add to `.env`:
   ```bash
   AZURE_TENANT_ID=your-tenant-id
   AZURE_CLIENT_ID=your-app-id
   AZURE_CLIENT_SECRET=your-password
   ```

**Pros**:
- ✅ Suitable for production
- ✅ No interactive login
- ✅ Works in CI/CD

**Cons**:
- ❌ More complex setup
- ❌ Requires managing secrets

### Method 3: Managed Identity (For Azure-hosted deployments)

If running on Azure (VM, App Service, AKS), use managed identity:

1. Enable managed identity for your resource
2. Grant permissions to Azure AI project
3. No additional configuration needed - DefaultAzureCredential handles it

---

## Testing Your Setup

### Test 1: Check Configuration

```bash
# Inside backend container
./start.sh shell-backend

python3 << EOF
from app.config import settings
print(f"Endpoint: {settings.AZURE_AI_PROJECT_ENDPOINT}")
print(f"Model: {settings.AZURE_AI_MODEL_DEPLOYMENT_NAME}")
EOF
```

### Test 2: Test Azure AI Client

```bash
# Inside backend container
python3 << EOF
import asyncio
from app.agents.azure_ai_client import AgentClientFactory

async def test():
    client = await AgentClientFactory.get_azure_ai_client()
    if client:
        print("✅ Azure AI client initialized successfully")
        agent = client.as_agent(instructions="You are a helpful assistant")
        result = await agent.run("Say hello")
        print(f"Agent response: {result.text}")
    else:
        print("❌ Azure AI client not available")
    await AgentClientFactory.cleanup()

asyncio.run(test())
EOF
```

Expected output:
```
✅ Azure AI client initialized successfully
Agent response: Hello! How can I help you today?
```

### Test 3: Test Agent with MAF

```python
import asyncio
from app.agents.discovery_agent import DiscoveryAgent

async def test():
    agent = DiscoveryAgent()
    await agent.initialize_maf_agent()
    
    if agent.maf_agent:
        print("✅ Discovery agent using MAF")
    else:
        print("ℹ️  Discovery agent using local mode")

asyncio.run(test())
```

---

## Troubleshooting

### Issue: "Azure AI client not available"

**Causes:**
1. Environment variables not set
2. Azure CLI not authenticated
3. Incorrect endpoint or model name

**Solutions:**
```bash
# Check environment variables
echo $AZURE_AI_PROJECT_ENDPOINT
echo $AZURE_AI_MODEL_DEPLOYMENT_NAME

# Re-authenticate
az login

# Verify Azure CLI works
az account show
```

### Issue: "Failed to initialize Azure AI client"

**Causes:**
1. No network connectivity
2. Invalid credentials
3. Model not deployed
4. Insufficient permissions

**Solutions:**
```bash
# Test network connectivity
curl -I $AZURE_AI_PROJECT_ENDPOINT

# Verify model deployment in Azure AI Studio
az ml online-deployment list --project-name your-project

# Check permissions
az role assignment list --assignee $(az account show --query user.name -o tsv)
```

### Issue: "SSL Certificate Error"

**Solution:**
```bash
# Set environment variable
export REQUESTS_CA_BUNDLE=/etc/ssl/certs/ca-certificates.crt
```

### Issue: Agent using local mode instead of MAF

**Check:**
1. Verify environment variables are set correctly
2. Check logs for initialization errors
3. Ensure `initialize_maf_agent()` is called
4. Verify Azure CLI authentication

---

## Cost Considerations

### Azure OpenAI Pricing

Using Azure AI with MAF incurs costs based on:
- **Model used**: gpt-4o-mini (cheapest), gpt-4 (most expensive)
- **Tokens consumed**: Input tokens + output tokens
- **Frequency**: Number of agent executions

**Estimate for gl2gh:**
- Discovery: ~500 tokens per project
- Transform: ~2000 tokens per project  
- Plan: ~1000 tokens per project

**Example costs (gpt-4o-mini):**
- 100 projects: ~$0.50 - $2.00
- 1000 projects: ~$5.00 - $20.00

**To minimize costs:**
1. Use local mode for development/testing
2. Use gpt-4o-mini instead of gpt-4
3. Cache results when possible
4. Use deterministic agents for simple tasks

---

## Best Practices

### Development
1. ✅ Use local mode (no Azure AI) for development
2. ✅ Use Azure CLI authentication
3. ✅ Test with small batches first

### Production
1. ✅ Use service principal or managed identity
2. ✅ Set up monitoring and alerts
3. ✅ Implement rate limiting
4. ✅ Cache agent results
5. ✅ Use cost management tools

### Security
1. ✅ Never commit credentials to git
2. ✅ Use Key Vault for secrets in production
3. ✅ Rotate credentials regularly
4. ✅ Use least-privilege access

---

## FAQ

**Q: Do I need Azure AI to use gl2gh?**
A: No! The platform works in local mode without Azure AI. Azure AI is optional for LLM-powered features.

**Q: Can I use a different LLM provider?**
A: Currently only Azure AI is supported. However, local mode doesn't use LLMs at all.

**Q: What's the difference between local and Azure AI modes?**
A: Local mode uses deterministic, rule-based agents. Azure AI mode uses LLM-powered agents that can understand natural language and adapt.

**Q: Can I mix local and Azure AI agents?**
A: Yes! Each agent checks Azure AI availability independently and falls back gracefully.

**Q: How much does it cost?**
A: Depends on usage. See "Cost Considerations" section above. Development/testing in local mode is free.

**Q: Is my data sent to Microsoft?**
A: Only if using Azure AI mode. Local mode processes everything locally.

---

## Additional Resources

- [Microsoft Agent Framework Documentation](https://learn.microsoft.com/en-us/agent-framework/)
- [Azure AI Studio](https://ai.azure.com/)
- [Azure OpenAI Pricing](https://azure.microsoft.com/en-us/pricing/details/cognitive-services/openai-service/)
- [Azure CLI Documentation](https://learn.microsoft.com/en-us/cli/azure/)
- [Azure AI Examples](https://github.com/microsoft/agent-framework/blob/main/python/samples/getting_started/agents/azure_ai/README.md)

---

## Support

If you encounter issues:

1. Check this guide's troubleshooting section
2. Review logs: `./start.sh logs backend`
3. Test Azure AI separately using the test scripts above
4. Check Azure AI Studio for model deployment status
5. Verify authentication: `az account show`

**Remember**: Local mode always works as a fallback!
