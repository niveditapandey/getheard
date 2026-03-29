# Pricing System — GetHeard

## Overview

GetHeard uses a dynamic, admin-editable pricing formula. Prices are computed in real-time based on study parameters — no hardcoded values in code. The admin can change any part of the formula through the admin dashboard at `/admin/pricing`.

---

## The Pricing Formula

```
Total = Study Fee × Size Multiplier
      + Recruitment Fee
      + Incentive Total
      + Urgency Fee
```

---

## Component 1: Study Fee

Base prices by study type (INR):

| Study Type | Code | Base Price |
|------------|------|-----------|
| NPS / CSAT | `nps_csat` | ₹7,999 |
| Feature Feedback | `feature_feedback` | ₹11,999 |
| Pain Points / UX | `pain_points` | ₹14,999 |
| Custom / Bespoke | `custom` | ₹16,999 |

---

## Component 2: Size Multiplier

The study fee is multiplied based on how many respondents are needed:

| Panel Size | Multiplier | Example: NPS at this size |
|------------|-----------|--------------------------|
| 5–10 | 1.0× | ₹7,999 |
| 11–15 | 1.25× | ₹9,999 |
| 16–20 | 1.5× | ₹11,999 |
| 21–30 | 2.5× | ₹19,998 |
| 31–40 | 3.5× | ₹27,997 |
| 41–50 | 4.0× | ₹31,996 |
| 51–60 | 5.0× | ₹39,995 |
| 61+ | 6.0× | ₹47,994 |

**Formula:** `Study Fee After Multiplier = Base Price × get_size_multiplier(panel_size)`

---

## Component 3: Recruitment Fee

Depends on **panel source**:

### Source A: GetHeard Database (`db`)
Client picks respondents from GetHeard's existing panel.
- **Fee:** ₹1,499 per respondent
- **Formula:** `1499 × panel_size`

### Source B: Client-Provided CSV (`csv`)
Client uploads their own list.
- **Fee:** ₹0 (no recruitment fee)
- Client is responsible for their own respondent sourcing

### Source C: Targeted Recruitment (`targeted`)
GetHeard recruits new respondents meeting specific criteria.
- **Base:** ₹2,499 per respondent
- **× Market Multiplier** (see table below)
- **× Industry Multiplier** (see table below)
- **Formula:** `2499 × panel_size × market_multiplier × industry_multiplier`

#### Market Multipliers (Targeted only)
| Market | Code | Multiplier | Reason |
|--------|------|-----------|--------|
| India | `IN` | 1.0× | Large panel, easy access |
| Philippines | `PH` | 1.0× | Active online community |
| Vietnam | `VN` | 1.0× | Growing digital population |
| Indonesia | `ID` | 1.1× | Diverse geography |
| Malaysia | `MY` | 1.2× | Bilingual complexity |
| Thailand | `TH` | 1.2× | Niche digital panels |
| Singapore | `SG` | 1.4× | Small market, high cost |
| Korea | `KR` | 1.6× | Hard to recruit internationally |
| China | `CN` | 1.5× | Access complexity |
| Japan | `JP` | 1.8× | Most expensive market |

#### Industry Multipliers (Targeted only)
| Industry | Multiplier | Reason |
|----------|-----------|--------|
| Gaming | 0.9× | Large, easy to reach audience |
| E-commerce | 1.0× | Standard |
| Education | 1.0× | Standard |
| Other | 1.0× | Standard |
| SaaS/Tech | 1.1× | Slightly niche |
| FMCG | 1.1× | Consumer brand targeting |
| Fintech | 1.2× | Financial services screen-in |
| Automotive | 1.3× | Ownership/intent screening |
| Real Estate | 1.4× | High-intent, lower volume |
| Healthcare | 1.5× | Sensitive, harder to recruit |

---

## Component 4: Respondent Incentive (Optional)

Client can add an optional per-respondent incentive that gets passed to respondents as points.

- **Client pays:** ₹X per respondent (entered in pricing slider)
- **Respondent receives:** Points equivalent (50% of INR value in India)
- **Formula:** `incentive_total = respondent_incentive_per_head × panel_size`

---

## Component 5: Urgency Premium (Optional)

If the client needs results faster than the standard timeline:

- **Premium:** +25% on the subtotal (study fee + recruitment fee + incentive)
- **Toggle:** Client can switch on/off on the pricing page
- **Formula:** `urgency_fee = subtotal × 0.25`

---

## Full Calculation Example

**Scenario:** NPS study, 20 respondents, GetHeard DB, India, Fintech, no urgency, ₹100 incentive per head

```
Base price (NPS):              ₹7,999
Size multiplier (16–20 = 1.5): × 1.5
Study fee after multiplier:    ₹11,999 (rounded)

Recruitment fee (db):          20 × ₹1,499 = ₹29,980
Incentive:                     20 × ₹100   = ₹2,000
Urgency:                       ₹0

─────────────────────────────────────
TOTAL:                         ₹43,979
```

---

## Changing Prices (Admin)

Go to `/admin/pricing` → Edit any cell → Click Save.

All changes take effect immediately for new quotes. Existing confirmed quotes are not affected.

The pricing config is stored in `config/pricing.json`. The admin panel provides an inline editor for all pricing tiers.

**Admin pricing URL:** http://localhost:8000/admin/pricing

---

## Code Reference

The pricing computation lives in `src/storage/pricing_store.py`:

```python
from src.storage.pricing_store import compute_quote

result = compute_quote(
    study_type="nps_csat",
    panel_size=20,
    panel_source="db",           # csv | db | targeted
    market="IN",
    industry="fintech",
    urgency=False,
    respondent_incentive_per_head=100
)

# result contains:
# {
#   "study_fee": 7999,
#   "size_multiplier": 1.5,
#   "study_fee_after_multiplier": 11999,
#   "recruitment_fee": 29980,
#   "incentive_total": 2000,
#   "urgency_fee": 0,
#   "total": 43979,
#   "currency": "INR",
#   "line_items": [...]
# }
```

---

## Live Quote Preview (Frontend)

The pricing page calls `/api/client/quote/compute` on each lever change (debounced 300ms):

```javascript
// Triggered on slider change, select change, toggle change
async function updateQuote() {
    const params = {
        study_type: studyTypeSelect.value,
        panel_size: parseInt(panelSlider.value),
        panel_source: sourceSelect.value,
        market: project.market,
        industry: project.industry,
        urgency: urgencyToggle.checked,
        respondent_incentive_per_head: parseInt(incentiveInput.value) || 0
    };
    const resp = await fetch('/api/client/quote/compute', {
        method: 'POST',
        body: JSON.stringify(params)
    });
    const quote = await resp.json();
    totalDisplay.textContent = `₹${quote.total.toLocaleString()}`;
    // Update line items...
}
```

---

## Currency & International Pricing

Currently all pricing is in **INR (Indian Rupees)**. For international clients:

- Razorpay handles INR payments
- Stripe handles USD/SGD/other payments
- Stripe checkout page does the currency conversion
- The quote is always shown in INR; Stripe handles conversion at checkout

**Future:** Add USD pricing display for international clients (in roadmap).

---

## Points & Payout Exchange Rates

Respondents earn points; points convert to local currency:

| Country | Currency | Rate (₹ per point equivalent) | UPI Available |
|---------|----------|-------------------------------|---------------|
| India | INR | ₹0.50 per point | ✅ Yes |
| Singapore | SGD | SGD 0.01 per point | ✅ Yes |
| Indonesia | IDR | IDR 150 per point | ❌ Coming soon |
| Thailand | THB | THB 0.20 per point | ❌ Coming soon |
| Vietnam | VND | VND 15 per point | ❌ Coming soon |
| Japan | JPY | JPY 0.08 per point | ❌ Coming soon |
| Korea | KRW | KRW 0.80 per point | ❌ Coming soon |
| China | CNY | CNY 0.04 per point | ❌ Coming soon |
| Philippines | PHP | PHP 0.30 per point | ❌ Coming soon |
| Malaysia | MYR | MYR 0.025 per point | ❌ Coming soon |

**Gift card bonus:** +10% on all gift card redemptions (200 points → 220 points worth of gift card)

**Minimum redemption:** 100 points

**Points lifecycle:**
- 20% credited on panel **selection** (before interview)
- 80% credited on interview **completion**
