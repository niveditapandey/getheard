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
        default="gemini-2.5-flash",
        description="Default Gemini model (fast — used for real-time voice and chat)"
    )
    gemini_model_pro: str = Field(
        default="gemini-2.5-pro",
        description="Pro Gemini model (used for question design and report analysis)"
    )
    gcp_location: str = Field(
        default="us-central1",
        description="GCP region for Vertex AI"
    )

    # Google AI Studio API key (preferred — avoids Vertex AI quota issues)
    # Get one free at https://aistudio.google.com/app/apikey
    gemini_api_key: str = Field(default="", description="Google AI Studio API key")
    
    # Sarvam AI Configuration (Optional - for Indian languages)
    sarvam_api_key: str = Field(default="", description="Sarvam AI API key")

    # Twilio WhatsApp Configuration (Optional)
    twilio_account_sid: str = Field(default="", description="Twilio Account SID")
    twilio_auth_token: str = Field(default="", description="Twilio Auth Token")
    twilio_whatsapp_number: str = Field(
        default="whatsapp:+14155238886",
        description="Twilio WhatsApp sandbox/production number",
    )

    # API Key Authentication
    api_key: str = Field(default="getheard-dev-key-2026", description="Platform API key")

    # Client portal auth
    secret_key: str = Field(default="getheard-secret-2026", description="Session middleware secret key")
    client_credentials: str = Field(
        default="demo:demo123",
        description="Comma-separated user:pass pairs for client portal, e.g. 'acme:pass1,beta:pass2'"
    )

    # Admin credentials (separate from client credentials)
    admin_credentials: str = Field(
        default="admin:getheard-admin-2026",
        description="Admin portal credentials: user:pass"
    )

    # Payment gateways
    razorpay_key_id: str = Field(default="", description="Razorpay Key ID — get from razorpay.com/app/keys")
    razorpay_key_secret: str = Field(default="", description="Razorpay Key Secret")
    stripe_publishable_key: str = Field(default="", description="Stripe Publishable Key — get from dashboard.stripe.com")
    stripe_secret_key: str = Field(default="", description="Stripe Secret Key")

    # Email (Resend)
    resend_api_key: str = Field(default="", description="Resend API key — get from resend.com/api-keys")
    resend_from_email: str = Field(default="hello@getheard.space", description="From address for outbound emails")

    # WhatsApp Business API (Meta)
    whatsapp_phone_number_id: str = Field(default="", description="WhatsApp Business Phone Number ID from Meta Business Manager")
    whatsapp_business_id: str = Field(default="", description="WhatsApp Business Account ID from Meta Business Manager")
    whatsapp_access_token: str = Field(default="", description="WhatsApp Business API access token from Meta")
    
    # Voice Provider Selection
    voice_provider: str = Field(
        default="google_cloud",
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
    def client_credentials_dict(self) -> dict:
        """Parse client_credentials string into {username: password} dict."""
        result = {}
        for pair in self.client_credentials.split(","):
            pair = pair.strip()
            if ":" in pair:
                u, p = pair.split(":", 1)
                result[u.strip()] = p.strip()
        return result

    @property
    def admin_credentials_dict(self) -> dict:
        """Parse admin_credentials string into {username: password} dict."""
        result = {}
        for pair in self.admin_credentials.split(","):
            pair = pair.strip()
            if ":" in pair:
                u, p = pair.split(":", 1)
                result[u.strip()] = p.strip()
        return result

    @property
    def has_razorpay(self) -> bool:
        return bool(self.razorpay_key_id and self.razorpay_key_secret)

    @property
    def has_stripe(self) -> bool:
        return bool(self.stripe_publishable_key and self.stripe_secret_key)

    @property
    def has_resend(self) -> bool:
        return bool(self.resend_api_key)

    @property
    def has_whatsapp_api(self) -> bool:
        return bool(self.whatsapp_phone_number_id and self.whatsapp_access_token)

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

    @property
    def has_twilio_credentials(self) -> bool:
        """Check if Twilio credentials are configured."""
        return bool(self.twilio_account_sid and self.twilio_auth_token)
    
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
