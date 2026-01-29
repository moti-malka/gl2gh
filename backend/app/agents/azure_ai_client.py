"""Azure AI client wrapper for Microsoft Agent Framework"""

import os
from typing import Optional
from app.config import settings
from app.utils.logging import get_logger

logger = get_logger(__name__)

# Try to import Azure AI dependencies, but allow graceful fallback
try:
    from agent_framework.azure import AzureAIClient
    from azure.identity.aio import AzureCliCredential, DefaultAzureCredential
    AZURE_AI_AVAILABLE = True
except ImportError:
    logger.info("Azure AI dependencies not available, agents will run in local mode")
    AzureAIClient = None
    AzureCliCredential = None
    DefaultAzureCredential = None
    AZURE_AI_AVAILABLE = False


class AgentClientFactory:
    """
    Factory for creating Microsoft Agent Framework clients.
    
    Supports:
    - Azure AI hosted agents (requires Azure AI project)
    - Local agents (no Azure dependency)
    - Multiple authentication methods
    """
    
    _client: Optional[AzureAIClient] = None
    _credential: Optional[any] = None
    
    @classmethod
    async def get_azure_ai_client(cls) -> Optional[AzureAIClient]:
        """
        Get or create Azure AI client for MAF agents.
        
        Returns None if Azure AI is not configured.
        Uses AzureCliCredential by default (requires: az login)
        Falls back to DefaultAzureCredential for service principals.
        
        Environment variables required:
            - AZURE_AI_PROJECT_ENDPOINT
            - AZURE_AI_MODEL_DEPLOYMENT_NAME
        
        Optional (for service principal):
            - AZURE_TENANT_ID
            - AZURE_CLIENT_ID
            - AZURE_CLIENT_SECRET
        """
        if not AZURE_AI_AVAILABLE:
            logger.debug("Azure AI dependencies not installed")
            return None
            
        if not settings.AZURE_AI_PROJECT_ENDPOINT or not settings.AZURE_AI_MODEL_DEPLOYMENT_NAME:
            logger.info("Azure AI not configured, agents will run in local mode")
            return None
        
        if cls._client is None:
            try:
                # Try Azure CLI credential first (most common for dev)
                if not settings.AZURE_CLIENT_ID:
                    logger.info("Using Azure CLI credential for authentication")
                    cls._credential = AzureCliCredential()
                else:
                    # Use DefaultAzureCredential for service principal
                    logger.info("Using DefaultAzureCredential for authentication")
                    cls._credential = DefaultAzureCredential()
                
                cls._client = AzureAIClient(
                    async_credential=cls._credential,
                    endpoint=settings.AZURE_AI_PROJECT_ENDPOINT,
                    model_deployment_name=settings.AZURE_AI_MODEL_DEPLOYMENT_NAME
                )
                
                logger.info(f"Azure AI client initialized successfully")
                logger.info(f"Endpoint: {settings.AZURE_AI_PROJECT_ENDPOINT}")
                logger.info(f"Model: {settings.AZURE_AI_MODEL_DEPLOYMENT_NAME}")
                
            except Exception as e:
                logger.error(f"Failed to initialize Azure AI client: {e}")
                logger.info("Agents will run in local mode")
                cls._client = None
                if cls._credential:
                    await cls._credential.close()
                    cls._credential = None
        
        return cls._client
    
    @classmethod
    async def cleanup(cls):
        """Clean up resources"""
        if cls._credential:
            await cls._credential.close()
            cls._credential = None
        cls._client = None
    
    @classmethod
    def is_azure_ai_configured(cls) -> bool:
        """Check if Azure AI is configured"""
        return AZURE_AI_AVAILABLE and bool(
            settings.AZURE_AI_PROJECT_ENDPOINT and 
            settings.AZURE_AI_MODEL_DEPLOYMENT_NAME
        )


async def create_agent_with_instructions(instructions: str, name: str = "Agent"):
    """
    Create a Microsoft Agent Framework agent with instructions.
    
    Uses Azure AI if configured, otherwise returns None and logs info.
    
    Args:
        instructions: Natural language instructions for the agent
        name: Agent name for logging
        
    Returns:
        MAF agent instance or None
    """
    client = await AgentClientFactory.get_azure_ai_client()
    
    if client is None:
        logger.info(f"{name}: Azure AI not available, using local implementation")
        return None
    
    try:
        agent = client.as_agent(instructions=instructions)
        logger.info(f"{name}: Created with Azure AI")
        return agent
    except Exception as e:
        logger.error(f"{name}: Failed to create Azure AI agent: {e}")
        return None
