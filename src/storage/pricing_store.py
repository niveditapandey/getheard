"""
pricing_store.py — Load and compute dynamic pricing for GetHeard studies.
"""
import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Dict, Optional

BASE_DIR = Path(__file__).parent.parent.parent
PRICING_CONFIG_PATH = BASE_DIR / "config" / "pricing.json"

def load_pricing_config() -> Dict:
    """Load current pricing config from JSON."""
    return json.loads(PRICING_CONFIG_PATH.read_text(encoding="utf-8"))

def save_pricing_config(config: Dict) -> None:
    """Save updated pricing config (admin only)."""
    config["updated_at"] = datetime.now(timezone.utc).isoformat()
    PRICING_CONFIG_PATH.write_text(json.dumps(config, indent=2, ensure_ascii=False))

def get_size_multiplier(panel_size: int, config: Optional[Dict] = None) -> float:
    """Return the panel size multiplier for a given respondent count."""
    if config is None:
        config = load_pricing_config()
    for tier in config["panel_size_multipliers"]:
        if tier["min"] <= panel_size <= tier["max"]:
            return tier["multiplier"]
    # If larger than max defined tier, use last multiplier
    return config["panel_size_multipliers"][-1]["multiplier"]

def compute_quote(
    study_type: str,           # nps_csat | feature_feedback | pain_points | custom
    panel_size: int,
    panel_source: str,         # csv | db | targeted
    market: str = "IN",        # country code
    industry: str = "other",
    urgency: bool = False,
    respondent_incentive_per_head: int = 0,
    config: Optional[Dict] = None,
) -> Dict:
    """
    Compute full quote breakdown for a study.
    Returns itemised breakdown + total.
    """
    if config is None:
        config = load_pricing_config()

    # Base
    base = config["base_prices"].get(study_type, config["base_prices"]["custom"])
    size_mult = get_size_multiplier(panel_size, config)
    study_fee = round(base * size_mult)

    # Recruitment
    recruitment_fee = 0
    recruitment_label = "Client uploads CSV"
    rf = config["recruitment_fees"]
    if panel_source == "db":
        recruitment_fee = rf["from_db_per_respondent"] * panel_size
        recruitment_label = f"GetHeard recruits from panel DB (₹{rf['from_db_per_respondent']}/respondent)"
    elif panel_source == "targeted":
        mkt_mult = rf["targeted_market_multipliers"].get(market, rf["targeted_market_multipliers"]["OTHER"])
        ind_mult = rf["industry_multipliers"].get(industry, rf["industry_multipliers"]["other"])
        per_head = round(rf["targeted_base_per_respondent"] * mkt_mult * ind_mult)
        recruitment_fee = per_head * panel_size
        recruitment_label = f"Targeted recruitment (₹{per_head}/respondent)"

    # Incentive
    incentive_total = respondent_incentive_per_head * panel_size

    subtotal = study_fee + recruitment_fee + incentive_total

    # Urgency
    urgency_fee = round(subtotal * config["urgency_premium_percent"] / 100) if urgency else 0

    total = subtotal + urgency_fee

    symbol = config.get("currency_symbol", "₹")

    return {
        "study_fee":         study_fee,
        "study_fee_label":   f"Study fee ({study_type.replace('_',' ').title()}, {panel_size} respondents × {size_mult}×)",
        "recruitment_fee":   recruitment_fee,
        "recruitment_label": recruitment_label,
        "incentive_total":   incentive_total,
        "incentive_label":   f"Respondent incentive ({symbol}{respondent_incentive_per_head}/respondent)" if incentive_total else None,
        "urgency_fee":       urgency_fee,
        "urgency_label":     f"Expedited delivery premium ({config['urgency_premium_percent']}%)" if urgency_fee else None,
        "subtotal":          subtotal,
        "total":             total,
        "currency":          config.get("currency", "INR"),
        "currency_symbol":   symbol,
    }
