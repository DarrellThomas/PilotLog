"""State tax analysis for SWA base shopping.

Federal law (49 USC 40116): airline employees are taxed ONLY by:
  (A) their state of residence, OR
  (B) the state where they earn >50% of pay (effectively base state)

Most pilots are taxed by residence state. But some states (CA, CO) impose
additional payroll taxes (SDI, FAMLI) based on WHERE YOU ARE BASED regardless
of residence. This means basing in CA or CO has hidden costs even if you
live in TX.

Key insight: you can live in State A (no tax) and be based in State B,
but you still owe State B's payroll taxes AND potentially State B's income
tax if it's your base state.
"""

from dataclasses import dataclass

# 2026 Captain 12+ YOS — actual pay from pay slips
# YTD gross through May 2026: $215,439.49 (5 months) → annualized $517,055
# Includes: regular TFP, premium, overrides, vacation, sick, per diem, PS benefits
# TFP rate: $343.14/TFP (confirmed), previous $329.94 (Dec 2025)
CAPTAIN_RATE = 343.14
GROSS_ANNUAL = 517_055  # annualized from actual 2026 pay slips


@dataclass
class StateTax:
    """Tax profile for a state at captain pay scale."""
    state: str
    abbreviation: str
    top_rate: float          # top marginal income tax rate (%)
    rate_type: str           # "flat", "progressive", "none"
    estimated_tax: int       # estimated annual state income tax at captain pay
    sdi_rate: float          # state disability insurance rate (%)
    sdi_cap: int             # wage cap for SDI (0 = no cap)
    sdi_annual: int          # estimated annual SDI at captain pay
    famli_rate: float        # paid family leave rate (%)
    famli_cap: int           # wage cap for FAMLI
    famli_annual: int        # estimated annual FAMLI
    local_tax: float         # local/city tax rate if applicable
    local_annual: int        # estimated local tax
    notes: str               # important caveats


# SWA base states — 2026 rates at ~$343K captain gross
# Sources: Tax Foundation, state EDD/DOR sites, FAMLI program
BASE_STATES = {
    # === NO INCOME TAX ===
    "TX": StateTax(
        state="Texas", abbreviation="TX",
        top_rate=0, rate_type="none",
        estimated_tax=0,
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="No state income tax. No payroll taxes. Best tax base.",
    ),
    "TN": StateTax(
        state="Tennessee", abbreviation="TN",
        top_rate=0, rate_type="none",
        estimated_tax=0,
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="No state income tax.",
    ),
    "FL": StateTax(
        state="Florida", abbreviation="FL",
        top_rate=0, rate_type="none",
        estimated_tax=0,
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="No state income tax.",
    ),
    "NV": StateTax(
        state="Nevada", abbreviation="NV",
        top_rate=0, rate_type="none",
        estimated_tax=0,
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="No state income tax.",
    ),

    # === LOW TAX ===
    "AZ": StateTax(
        state="Arizona", abbreviation="AZ",
        top_rate=2.5, rate_type="flat",
        estimated_tax=12_926,  # 2.5% of $517K
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="Flat 2.5%. Lowest income tax state with a tax. Good value base.",
    ),

    # === MODERATE TAX ===
    "CO": StateTax(
        state="Colorado", abbreviation="CO",
        top_rate=4.4, rate_type="flat",
        estimated_tax=22_750,  # 4.4% of $517K
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0.44, famli_cap=176_100, famli_annual=775,
        local_tax=0, local_annual=0,
        notes="4.4% flat + FAMLI 0.44% (capped at $176K). FAMLI applies to "
              "base state — you pay even if you live in TX. Total ~$23,525.",
    ),
    "IL": StateTax(
        state="Illinois", abbreviation="IL",
        top_rate=4.95, rate_type="flat",
        estimated_tax=25_594,  # 4.95% of $517K
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="4.95% flat. No payroll add-ons. Straightforward.",
    ),
    "GA": StateTax(
        state="Georgia", abbreviation="GA",
        top_rate=5.19, rate_type="flat",
        estimated_tax=26_835,  # 5.19% of $517K
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="5.19% flat (was 5.49%, being phased down). No payroll add-ons.",
    ),

    # === HIGHER TAX ===
    "MD": StateTax(
        state="Maryland", abbreviation="MD",
        top_rate=6.5, rate_type="progressive",
        estimated_tax=31_267,  # effective ~6.05% after brackets at $517K
        sdi_rate=0, sdi_cap=0, sdi_annual=0,
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=3.2, local_annual=16_546,  # Anne Arundel County ~2.81% at $517K
        notes="6.5% top bracket + LOCAL county tax ~2.81% (Anne Arundel/BWI). "
              "Total effective ~9.2%. Local tax applies to residents only.",
    ),

    # === HIGHEST TAX ===
    "CA": StateTax(
        state="California", abbreviation="CA",
        top_rate=13.3, rate_type="progressive",
        estimated_tax=47_013,  # effective ~9.1% at $517K (progressive brackets)
        sdi_rate=1.3, sdi_cap=0, sdi_annual=6_722,  # NO CAP — 1.3% of $517K
        famli_rate=0, famli_cap=0, famli_annual=0,
        local_tax=0, local_annual=0,
        notes="13.3% top bracket + SDI 1.3% NO WAGE CAP. SDI applies to BASE "
              "STATE — you pay $6,722/yr SDI even living in TX and commuting. "
              "If based+living in CA, total hit ~$53,735. Worst tax base by far.",
    ),
}

# Map SWA bases to states
BASE_TO_STATE = {
    "ATL": "GA",
    "AUS": "TX",
    "BNA": "TN",
    "BWI": "MD",
    "DAL": "TX",
    "DEN": "CO",
    "HOU": "TX",
    "LAS": "NV",
    "LAX": "CA",
    "MCO": "FL",
    "MDW": "IL",
    "OAK": "CA",
    "PHX": "AZ",
}


def compute_base_tax(base, residence_state=None, gross=None):
    """Compute total state tax burden for a given base and residence.

    Args:
        base: SWA base code (e.g., "HOU")
        residence_state: state abbreviation where pilot lives (default: base state)
        gross: annual gross pay (default: captain rate)

    Returns:
        dict with tax breakdown
    """
    if gross is None:
        gross = GROSS_ANNUAL

    state_abbr = BASE_TO_STATE.get(base)
    if not state_abbr:
        return {"error": f"Unknown base: {base}"}

    base_tax = BASE_STATES[state_abbr]
    res_state = residence_state or state_abbr
    res_tax = BASE_STATES.get(res_state)

    # Income tax: owed to residence state (49 USC 40116)
    if res_tax:
        income_tax = res_tax.estimated_tax
        income_tax_state = res_state
    else:
        income_tax = 0
        income_tax_state = res_state

    # Payroll taxes: owed to BASE state regardless of residence
    # CA SDI and CO FAMLI follow the base, not residence
    sdi = base_tax.sdi_annual
    famli = base_tax.famli_annual

    # Local tax: only if you LIVE there
    local = 0
    if res_state == state_abbr:
        local = base_tax.local_annual

    total = income_tax + sdi + famli + local
    effective_rate = round(total / gross * 100, 2) if gross else 0

    return {
        "base": base,
        "base_state": state_abbr,
        "residence_state": res_state,
        "gross": gross,
        "income_tax": income_tax,
        "income_tax_state": income_tax_state,
        "sdi": sdi,
        "famli": famli,
        "local_tax": local,
        "total_state_tax": total,
        "effective_rate": effective_rate,
        "notes": base_tax.notes,
    }


def compute_all_bases(residence_state="TX", gross=None):
    """Compute tax for all SWA bases given a residence state.

    Args:
        residence_state: where the pilot lives (default TX = no income tax)
        gross: annual gross (default captain rate)

    Returns:
        list of tax breakdowns sorted by total tax (ascending)
    """
    results = []
    for base in sorted(BASE_TO_STATE.keys()):
        result = compute_base_tax(base, residence_state, gross)
        results.append(result)
    return sorted(results, key=lambda r: r["total_state_tax"])


def format_tax_report(results, residence_state="TX"):
    """Format tax comparison as readable text."""
    lines = [
        f"SWA Base Tax Comparison — Residence: {residence_state}",
        f"Gross Annual: ${results[0]['gross']:,}",
        f"Federal law (49 USC 40116): income tax owed to residence state only",
        f"Payroll taxes (CA SDI, CO FAMLI): owed to BASE state regardless",
        "",
        f"  {'Base':>4s}  {'State':>5s}  {'Income':>8s}  {'SDI':>6s}  {'FAMLI':>6s}  {'Local':>6s}  {'TOTAL':>8s}  {'Eff%':>5s}",
        f"  {'—'*4}  {'—'*5}  {'—'*8}  {'—'*6}  {'—'*6}  {'—'*6}  {'—'*8}  {'—'*5}",
    ]

    for r in results:
        total = r["total_state_tax"]
        marker = ""
        if total == 0:
            marker = "  ***"
        elif r["base_state"] == "CA":
            marker = "  !!!"

        lines.append(
            f"  {r['base']:>4s}  {r['base_state']:>5s}  "
            f"${r['income_tax']:>7,}  "
            f"${r['sdi']:>5,}  "
            f"${r['famli']:>5,}  "
            f"${r['local_tax']:>5,}  "
            f"${total:>7,}  "
            f"{r['effective_rate']:>4.1f}%{marker}"
        )

    # Commuting scenarios
    lines.extend([
        "",
        "Commuting Scenarios (live in TX, base elsewhere):",
        "  If you live in TX (no income tax) and commute to base:",
        "  - TX bases (HOU/DAL/AUS): $0 total — best case",
        "  - NV base (LAS): $0 — no income tax, no payroll add-ons",
        "  - FL base (MCO): $0 — no income tax",
        "  - TN base (BNA): $0 — no income tax",
        "  - AZ base (PHX): $0 — income tax is residence-based, not base-based",
        "  - CO base (DEN): $775 FAMLI — applies to base regardless of residence",
        "  - IL base (MDW): $0 — IL taxes residents only",
        "  - GA base (ATL): $0 — GA taxes residents only",
        "  - MD base (BWI): $0 — MD taxes residents only (no local if non-resident)",
        "  - CA base (LAX/OAK): $4,461 SDI — applies to base, NO WAGE CAP",
        "",
        "Bottom line: CA SDI ($4,461/yr) and CO FAMLI ($775/yr) follow the BASE,",
        "not your residence. Every other state tax can be avoided by living in TX.",
    ])

    return "\n".join(lines)
