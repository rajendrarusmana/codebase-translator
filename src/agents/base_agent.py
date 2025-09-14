from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, List
from langchain_core.language_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
import logging
import os
import time
import asyncio
from typing import Callable

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseAgent(ABC):
    def __init__(
        self,
        llm: Optional[BaseChatModel] = None,
        model_name: str = "gpt-4",
        temperature: float = 0.0,
        config: Optional[Dict[str, Any]] = None
    ):
        self.config = config or {}
        self.rate_limit_config = self.config.get('rate_limiting', {})
        self.llm = llm or self._create_llm(model_name, temperature)
        self.parser = JsonOutputParser()
        self.request_times = []  # Track request timestamps for rate limiting
        
    async def _execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with exponential backoff retry on rate limit errors."""
        max_retries = self.rate_limit_config.get('max_retries', 3)
        retry_delay = self.rate_limit_config.get('retry_delay_seconds', 5)
        
        for attempt in range(max_retries):
            try:
                # Apply rate limiting
                await self._apply_rate_limit()
                
                # Execute the function
                result = await func(*args, **kwargs) if asyncio.iscoroutinefunction(func) else func(*args, **kwargs)
                return result
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error
                if '429' in error_str or 'rate_limit_error' in error_str:
                    if attempt < max_retries - 1:
                        # Exponential backoff
                        wait_time = retry_delay * (2 ** attempt)
                        logger.warning(f"Rate limit hit, retrying in {wait_time} seconds... (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(wait_time) if asyncio.iscoroutinefunction(func) else time.sleep(wait_time)
                        continue
                    else:
                        logger.error(f"Max retries ({max_retries}) reached for rate limit error")
                        raise
                else:
                    # Not a rate limit error, re-raise immediately
                    raise
    
    async def _apply_rate_limit(self):
        """Apply rate limiting based on configuration."""
        requests_per_minute = self.rate_limit_config.get('requests_per_minute', 60)
        
        # Clean old timestamps
        current_time = time.time()
        self.request_times = [t for t in self.request_times if current_time - t < 60]
        
        # Check if we're at the limit
        if len(self.request_times) >= requests_per_minute:
            # Calculate wait time
            oldest_request = min(self.request_times)
            wait_time = 60 - (current_time - oldest_request) + 0.1
            if wait_time > 0:
                logger.info(f"Rate limiting: waiting {wait_time:.1f} seconds...")
                await asyncio.sleep(wait_time)
        
        # Record this request
        self.request_times.append(time.time())
    
    def _create_llm(self, model_name: str, temperature: float) -> BaseChatModel:
        """Create LLM instance based on model name with fallback detection."""
        
        # OpenRouter models (uses OpenAI-compatible API)
        if "openrouter" in model_name.lower() or model_name.startswith(("openrouter/", "or:")):
            if not os.getenv("OPENROUTER_API_KEY"):
                raise ValueError("OPENROUTER_API_KEY environment variable is required for OpenRouter models")
            
            # Extract the actual model name (e.g., "openrouter/meta-llama/llama-3.1-8b-instruct" -> "meta-llama/llama-3.1-8b-instruct")
            actual_model_name = model_name
            if model_name.startswith("openrouter/"):
                actual_model_name = model_name[len("openrouter/"):]
            elif model_name.startswith("or:"):
                actual_model_name = model_name[len("or:"):]
            
            # Create OpenAI-compatible client for OpenRouter
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=actual_model_name,
                temperature=temperature,
                openai_api_key=os.getenv("OPENROUTER_API_KEY"),
                openai_api_base="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://github.com/codebase-translator",  # Optional, for OpenRouter analytics
                    "X-Title": "Codebase Translator"  # Optional, for OpenRouter analytics
                }
            )
        
        # OpenAI models
        elif any(x in model_name.lower() for x in ["gpt", "openai"]):
            if not os.getenv("OPENAI_API_KEY"):
                raise ValueError("OPENAI_API_KEY environment variable is required for OpenAI models")
            return ChatOpenAI(model=model_name, temperature=temperature)
        
        # Anthropic models  
        elif any(x in model_name.lower() for x in ["claude-", "anthropic"]) and not model_name.startswith("openrouter/"):
            if not os.getenv("ANTHROPIC_API_KEY"):
                raise ValueError("ANTHROPIC_API_KEY environment variable is required for Anthropic models")
            return ChatAnthropic(model=model_name, temperature=temperature)
        
        # Try to detect from common model patterns
        elif model_name.startswith(("gpt-", "text-", "davinci")):
            logger.warning(f"Assuming {model_name} is an OpenAI model")
            return ChatOpenAI(model=model_name, temperature=temperature)
            
        elif model_name.startswith(("claude-")):
            logger.warning(f"Assuming {model_name} is an Anthropic model") 
            return ChatAnthropic(model=model_name, temperature=temperature)
        
        else:
            available_backends = ["OpenAI (gpt-*)", "Anthropic (claude-*)", "OpenRouter (openrouter/* or or:*)"]
            raise ValueError(
                f"Unsupported model: {model_name}\n"
                f"Available backends: {', '.join(available_backends)}\n"
                f"Set appropriate API key: OPENAI_API_KEY, ANTHROPIC_API_KEY, or OPENROUTER_API_KEY"
            )
    
    @abstractmethod
    def get_prompt(self) -> ChatPromptTemplate:
        pass
    
    @abstractmethod
    async def process(self, state: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def create_chain(self):
        prompt = self.get_prompt()
        return prompt | self.llm
    
    async def invoke_llm(self, messages: List[Dict[str, str]], **kwargs) -> str:
        try:
            chain = self.create_chain()
            response = await chain.ainvoke({"messages": messages, **kwargs})
            return response.content
        except Exception as e:
            logger.error(f"Error invoking LLM: {e}")
            raise
    
    def log_action(self, action: str, details: Optional[Dict[str, Any]] = None):
        logger.info(f"[{self.__class__.__name__}] {action}")
        if details:
            logger.debug(f"Details: {details}")