"""
Configuration settings for the voice interview platform.
Multi-provider support with auto-routing for optimal quality.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field
from typing import List


class Settings(BaseSettings):
    """Main settings class for the application."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Google Cloud / Vertex AI Configuration
    gcp_project_id: str = Field(..., description="Google Cloud Project ID")
    gemini_model: str = Field(
        default="gemini-1.5-pro",
        description="Gemini model to use"
    )
    gcp_location: str = Field(
        default="us-central1",
        description="GCP region for Vertex AI"
    )
    
    # Sarvam AI Configuration (Optional - for Indian languages)
    sarvam_api_key: str = Field(default="", description="Sarvam AI API key")
    
    # Voice Provider Selection
    voice_provider: str = Field(
        default="auto",
        description="Voice provider: google_cloud, sarvam, or auto"
    )
    
    # Language Configuration
    interview_language: str = Field(
        default="en,id,fil,th,vi,ko,ja,zh,hi",
        description="Supported languages (comma-separated)"
    )
    default_language: str = Field(
        default="en",
        description="Default interview language"
    )
    indian_languages: str = Field(
        default="hi,en-IN,ta,te,ml,kn,bn,mr,gu,pa,or",
        description="Indian languages that can use Sarvam"
    )
    
    # Interview Configuration
    max_interview_duration: int = Field(
        default=600,
        description="Maximum interview duration in seconds"
    )
    questions_count: int = Field(
        default=3,
        description="Number of main questions in interview"
    )
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    
    @property
    def supported_languages(self) -> List[str]:
        """Get list of all supported languages."""
        return [lang.strip() for lang in self.interview_language.split(",")]
    
    @property
    def indian_language_codes(self) -> List[str]:
        """Get list of Indian language codes."""
        return [lang.strip() for lang in self.indian_languages.split(",")]
    
    @property
    def has_sarvam_credentials(self) -> bool:
        """Check if Sarvam AI credentials are configured."""
        return bool(self.sarvam_api_key and self.sarvam_api_key != "")
    
    def should_use_sarvam(self, language_code: str) -> bool:
        """
        Determine if Sarvam should be used for this language.
        
        Auto-routing logic:
        - If language is Indian AND Sarvam credentials available → use Sarvam
        - Otherwise → use Google Cloud
        """
        if self.voice_provider == "sarvam":
            return True
        elif self.voice_provider == "google_cloud":
            return False
        else:  # auto mode
            return (
                language_code in self.indian_language_codes 
                and self.has_sarvam_credentials
            )
    
    def __repr__(self) -> str:
        """Safe representation that doesn't expose API keys."""
        return (
            f"Settings(gcp_project={self.gcp_project_id}, "
            f"gemini_model={self.gemini_model}, "
            f"voice_provider={self.voice_provider}, "
            f"languages={len(self.supported_languages)})"
        )


# Global settings instance
settings = Settings()


if __name__ == "__main__":
    print("Configuration loaded successfully!")
    print(f"GCP Project: {settings.gcp_project_id}")
    print(f"Voice Provider: {settings.voice_provider}")
    print(f"Supported Languages: {settings.supported_languages}")
    print(f"Indian Languages: {settings.indian_language_codes}")
    print(f"Has Sarvam: {settings.has_sarvam_credentials}")
    print(f"\nLanguage Routing:")
    for lang in ['hi', 'en', 'id', 'fil', 'th']:
        provider = "Sarvam" if settings.should_use_sarvam(lang) else "Google Cloud"
        print(f"  {lang}: {provider}")
