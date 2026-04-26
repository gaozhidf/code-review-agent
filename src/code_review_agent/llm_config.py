import os
from typing import Tuple
from langchain_core.language_models import BaseChatModel
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv

load_dotenv()


class LLMConfig:
    """Configuration factory for multiple LLM providers."""

    @staticmethod
    def get_llm(model_id: str) -> BaseChatModel:
        """Get LLM instance from model ID in format provider/model."""
        provider, model_name = model_id.split("/", 1)
        
        if provider == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
            return ChatOpenAI(
                api_key=api_key,
                base_url=base_url,
                model=model_name,
                temperature=0.1,
            )
        elif provider == "anthropic":
            api_key = os.getenv("ANTHROPIC_API_KEY")
            return ChatAnthropic(
                api_key=api_key,
                model=model_name,
                temperature=0.1,
            )
        elif provider == "gemini":
            api_key = os.getenv("GEMINI_API_KEY")
            return ChatGoogleGenerativeAI(
                api_key=api_key,
                model=model_name,
                temperature=0.1,
                convert_system_message_to_human=True,
            )
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")

    @staticmethod
    def get_default_llm() -> BaseChatModel:
        """Get the default configured LLM."""
        default_model = os.getenv("DEFAULT_LLM_MODEL", "openai/gpt-4o")
        return LLMConfig.get_llm(default_model)
