"""World rulebook (option D, Personal Economist): rule changes in the world applied
to each customer's digital twin.

Rules are declarative data validated by pydantic: a list of conditions on twin
fields, an impact formula and text templates. Admin-added rules (POST /admin/rules)
use exactly the same schema, so nothing is ever executed as code.

Figures come from ACTION_PLAN.md section 3 only.
"""
from __future__ import annotations

import threading
from datetime import date, timedelta
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from engine.models import Customer, Moment, Stakes
from engine.render import render
from engine.twin import build_twin

TYPE = "world_rule"
CATEGORY = "info"
REQUIRES_INSURANCE_DATA = False  # handled per rule below
PROJECTABLE = True  # rules have effective dates: they belong on the timeline

Lang = Literal["nl", "fr", "en"]
ConditionOp = Literal["eq", "ne", "gt", "gte", "lt", "lte", "in", "exists", "missing",
                      "date_after", "date_before"]
Scalar = str | int | float | bool | None


class Condition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str = Field(pattern=r"^[a-z_][a-z0-9_]{1,40}$")
    op: ConditionOp
    value: Scalar | list[Scalar] = None

    def holds(self, twin: dict[str, Any]) -> bool:
        actual = twin.get(self.field)
        op, expected = self.op, self.value
        if op == "exists":
            return actual is not None
        if op == "missing":
            return actual is None
        if op == "in":
            return isinstance(expected, list) and actual in expected
        if op in ("date_after", "date_before"):
            if not isinstance(actual, str) or not isinstance(expected, str):
                return False
            try:
                a, e = date.fromisoformat(actual), date.fromisoformat(expected)
            except ValueError:
                return False
            return a > e if op == "date_after" else a < e
        if actual is None or isinstance(expected, list):
            return False
        if op == "eq":
            return actual == expected
        if op == "ne":
            return actual != expected
        if isinstance(actual, bool) or isinstance(expected, bool):
            return False
        if not isinstance(actual, (int, float)) or not isinstance(expected, (int, float)):
            return False
        return {"gt": actual > expected, "gte": actual >= expected,
                "lt": actual < expected, "lte": actual <= expected}[op]


class Impact(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["none", "pct_above_exemption", "pct_of_field", "yearly_schedule"] = "none"
    field: str | None = Field(default=None, pattern=r"^[a-z_][a-z0-9_]{1,40}$")
    pct: float | None = Field(default=None, ge=0, le=100)
    exemption: float = Field(default=0.0, ge=0)
    schedule: dict[str, float] | None = None  # "2026": 50 (percent)
    direction: Literal["cost", "benefit", "neutral"] = "neutral"
    illustrative: bool = False

    @model_validator(mode="after")
    def _check(self) -> "Impact":
        if self.kind in ("pct_above_exemption", "pct_of_field") and (self.field is None or self.pct is None):
            raise ValueError("field and pct are required for this impact kind")
        if self.kind == "yearly_schedule" and not self.schedule:
            raise ValueError("schedule is required for yearly_schedule")
        if self.schedule and not all(k.isdigit() and len(k) == 4 for k in self.schedule):
            raise ValueError("schedule keys must be years")
        return self

    def compute(self, twin: dict[str, Any], today: date) -> dict[str, Any]:
        facts: dict[str, Any] = {"direction": self.direction, "amount": None}
        if self.kind == "none":
            return facts
        if self.kind == "yearly_schedule":
            assert self.schedule is not None
            facts["year"], facts["next_year"] = today.year, today.year + 1
            facts["pct_this_year"] = _schedule_value(self.schedule, today.year)
            facts["pct_next_year"] = _schedule_value(self.schedule, today.year + 1)
            return facts
        base = twin.get(self.field or "")
        if not isinstance(base, (int, float)) or isinstance(base, bool):
            return facts
        if self.kind == "pct_above_exemption":
            facts["amount"] = round(max(0.0, base - self.exemption) * (self.pct or 0) / 100.0)
            facts["taxable"] = round(max(0.0, base - self.exemption))
        elif self.kind == "pct_of_field":
            facts["amount"] = max(1, round(base * (self.pct or 0) / 100.0)) if base > 0 else 0
        return facts


def _schedule_value(schedule: dict[str, float], year: int) -> float:
    years = sorted(int(k) for k in schedule)
    if year < years[0]:
        return 100.0
    chosen = max(y for y in years if y <= year)
    return schedule[str(chosen)]


class WorldRule(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(pattern=r"^[a-z][a-z0-9_]{2,50}$")
    title: dict[Lang, str]
    summary: dict[Lang, str]  # narration template per language, placeholders from facts
    summary_zero: dict[Lang, str] = Field(default_factory=dict)  # used instead when the impact amount is 0
    why: dict[Lang, str] = Field(default_factory=dict)  # one sentence citing the evidence, per language
    cta: dict[Lang, str] = Field(default_factory=dict)
    effective_date: date
    level: Literal["eu", "federal", "regional", "kbc"]
    region: Literal["flanders", "wallonia", "brussels"] | None = None
    visible_from: date | None = None   # default: 90 days before effective_date
    visible_until: date | None = None  # default: 365 days after effective_date
    conditions: list[Condition] = Field(min_length=1, max_length=12)
    impact: Impact = Field(default_factory=Impact)
    evidence: list[str] = Field(min_length=1, max_length=8)
    actions: list[str] = Field(min_length=1, max_length=6)
    stakes: Stakes = "medium"
    human_review: bool = False
    legal_basis: str = Field(default="legitimate_interest", max_length=80)
    requires_insurance_data: bool = False
    source_url: str | None = Field(default=None, max_length=300)

    @model_validator(mode="after")
    def _texts(self) -> "WorldRule":
        for name in ("title", "summary"):
            if "en" not in getattr(self, name):
                raise ValueError(f"{name} needs at least an 'en' entry")
        for text in [*self.title.values(), *self.summary.values(), *self.summary_zero.values(),
                     *self.why.values(), *self.cta.values(), *self.evidence, *self.actions]:
            if len(text) > 600:
                raise ValueError("text too long")
        if self.visible_from is None:
            self.visible_from = self.effective_date - timedelta(days=90)
        if self.visible_until is None:
            self.visible_until = self.effective_date + timedelta(days=365)
        return self

    def affected(self, twin: dict[str, Any]) -> bool:
        if self.region and twin.get("region") != self.region:
            return False
        return all(c.holds(twin) for c in self.conditions)

    def impact_facts(self, twin: dict[str, Any], today: date) -> dict[str, Any]:
        facts = {k: v for k, v in twin.items() if not isinstance(v, (list, dict))}
        facts.update(self.impact.compute(twin, today))
        facts["title"] = self.title["en"]
        facts["effective_date"] = self.effective_date.isoformat()
        return facts

    def to_moment(self, twin: dict[str, Any], today: date) -> Moment:
        facts = self.impact_facts(twin, today)
        start = today if self.effective_date <= today else self.effective_date
        return Moment(
            type=self.id,
            window=(start, self.visible_until or start),
            confidence=0.8 if self.impact.illustrative else 0.95,
            stakes=self.stakes,
            evidence=[render(e, facts, "en") for e in self.evidence],
            actions=list(self.actions),
            channel_hint="in_app_card",
            legal_basis=self.legal_basis,
            human_review=self.human_review,
            source="world_rule",
            category=CATEGORY,
            facts={k: v for k, v in facts.items() if isinstance(v, (str, int, float, bool)) or v is None},
        )


# ----------------------------------------------------------------------------
# Built-in rules (ACTION_PLAN.md section 3 figures only)
# ----------------------------------------------------------------------------

BUILTIN_RULES: list[dict[str, Any]] = [
    {
        "id": "capital_gains_tax_2026",
        "title": {"en": "10% capital-gains tax since 1 Jan 2026",
                  "nl": "Meerwaardebelasting van 10% sinds 1 januari 2026",
                  "fr": "Taxe de 10 % sur les plus-values depuis le 1er janvier 2026"},
        "summary": {
            "nl": "Sinds 1 januari 2026 geldt 10% meerwaardebelasting boven een vrijstelling van €10.000 per jaar. "
                  "Je Bolero-portefeuille (€{bolero_value}) heeft €{bolero_unrealised_gains} ongerealiseerde meerwaarde: "
                  "geschatte belasting bij verkoop dit jaar €{amount}. Winsten van vóór 2026 blijven vrijgesteld.",
            "fr": "Depuis le 1er janvier 2026, une taxe de 10 % s'applique aux plus-values au-delà d'une exonération de "
                  "€10.000 par an. Votre portefeuille Bolero (€{bolero_value}) a €{bolero_unrealised_gains} de plus-value "
                  "latente : taxe estimée en cas de vente cette année €{amount}. Les gains d'avant 2026 restent exonérés.",
            "en": "Since 1 January 2026 a 10% capital-gains tax applies above a €10,000 yearly exemption. Your Bolero "
                  "portfolio (€{bolero_value}) carries €{bolero_unrealised_gains} of unrealised gains: estimated tax if "
                  "sold this year €{amount}. Gains from before 2026 stay exempt.",
        },
        "summary_zero": {
            "nl": "Sinds 1 januari 2026 geldt 10% meerwaardebelasting boven een vrijstelling van €10.000 per jaar. "
                  "Je Bolero-portefeuille (€{bolero_value}) heeft €{bolero_unrealised_gains} ongerealiseerde meerwaarde: "
                  "onder de vrijstelling, dus niets te doen. Winsten van vóór 2026 blijven sowieso vrijgesteld.",
            "fr": "Depuis le 1er janvier 2026, une taxe de 10 % s'applique aux plus-values au-delà de €10.000 par an. "
                  "Votre portefeuille Bolero (€{bolero_value}) a €{bolero_unrealised_gains} de plus-value latente : "
                  "sous l'exonération, donc rien à faire. Les gains d'avant 2026 restent de toute façon exonérés.",
            "en": "Since 1 January 2026 a 10% capital-gains tax applies above a €10,000 yearly exemption. Your Bolero "
                  "portfolio (€{bolero_value}) carries €{bolero_unrealised_gains} of unrealised gains: under the "
                  "exemption, so nothing to do. Gains from before 2026 stay exempt anyway.",
        },
        "why": {"nl": "Je hebt een Bolero-portefeuille van €{bolero_value} met €{bolero_unrealised_gains} ongerealiseerde meerwaarde; de wet geldt sinds 1 januari 2026.",
                "fr": "Vous avez un portefeuille Bolero de €{bolero_value} avec €{bolero_unrealised_gains} de plus-value latente ; la loi s'applique depuis le 1er janvier 2026.",
                "en": "You hold a Bolero portfolio of €{bolero_value} with €{bolero_unrealised_gains} of unrealised gains; the law applies since 1 January 2026."},
        "cta": {"nl": "Leg het me uit", "fr": "Expliquez-moi", "en": "Explain it to me"},
        "effective_date": "2026-01-01",
        "level": "federal",
        "conditions": [{"field": "has_bolero", "op": "eq", "value": True}],
        "impact": {"kind": "pct_above_exemption", "field": "bolero_unrealised_gains", "pct": 10,
                   "exemption": 10000, "direction": "cost", "illustrative": True},
        "evidence": [
            "Bolero portfolio worth €{bolero_value} with unrealised gains of €{bolero_unrealised_gains}",
            "10% capital-gains tax since 1 Jan 2026 above the €10,000 exemption (unused part rolls over up to "
            "€15,000); gains before 31 Dec 2025 stay exempt",
            "estimated tax if all gains were realised this year: €{amount} (illustrative)",
        ],
        "actions": ["explain_capital_gains_tax", "plan_sale_timing", "talk_to_advisor"],
        "stakes": "medium",
        "legal_basis": "legitimate_interest",
        "source_url": "https://www.kbc.be/particulieren/nl/nieuws/arizona-regeerakkoord-meerwaardebelasting.html",
    },
    {
        "id": "insurance_tax_2026",
        "title": {"en": "Insurance tax 9.25% -> 9.6% on 1 Apr 2026",
                  "nl": "Verzekeringstaks van 9,25% naar 9,6% op 1 april 2026",
                  "fr": "Taxe sur les assurances de 9,25 % à 9,6 % le 1er avril 2026"},
        "summary": {
            "nl": "Sinds 1 april 2026 is de verzekeringstaks 9,6% in plaats van 9,25%. Voor je schadeverzekeringen "
                  "(€{nonlife_premium_total} premie per jaar) betekent dat ongeveer €{amount} extra per jaar. "
                  "Dat is al verrekend; je hoeft niets te doen.",
            "fr": "Depuis le 1er avril 2026, la taxe sur les assurances est de 9,6 % au lieu de 9,25 %. Pour vos "
                  "assurances non-vie (€{nonlife_premium_total} de primes par an), cela représente environ €{amount} "
                  "de plus par an. C'est déjà appliqué ; rien à faire.",
            "en": "Since 1 April 2026 the insurance tax is 9.6% instead of 9.25%. For your non-life policies "
                  "(€{nonlife_premium_total} in yearly premiums) that means about €{amount} extra per year. "
                  "It is already applied; nothing to do.",
        },
        "why": {"nl": "Je betaalt €{nonlife_premium_total} per jaar aan schadeverzekeringen bij KBC; de taks steeg op 1 april 2026 van 9,25% naar 9,6%.",
                "fr": "Vous payez €{nonlife_premium_total} par an d'assurances non-vie chez CBC ; la taxe est passée de 9,25 % à 9,6 % le 1er avril 2026.",
                "en": "You pay €{nonlife_premium_total} a year in non-life premiums; the tax rose from 9.25% to 9.6% on 1 April 2026."},
        "cta": {"nl": "Bekijk mijn polissen", "fr": "Voir mes polices", "en": "See my policies"},
        "effective_date": "2026-04-01",
        "level": "federal",
        "conditions": [{"field": "nonlife_premium_total", "op": "gte", "value": 200}],
        "impact": {"kind": "pct_of_field", "field": "nonlife_premium_total", "pct": 0.35,
                   "direction": "cost", "illustrative": True},
        "evidence": [
            "insurance tax on non-life policies rose from 9.25% to 9.6% on 1 Apr 2026",
            "your {policy_kinds_text} policies total €{nonlife_premium_total}/year in premiums",
            "extra tax about €{amount}/year (+0.35 percentage points, illustrative); applied at renewal, no action needed",
        ],
        "actions": ["no_action_needed", "see_policy_overview"],
        "stakes": "low",
        "legal_basis": "contract_performance",
        "requires_insurance_data": True,
        "source_url": "https://www.assuralia.be/nl/artikel/veranderingen-in-de-verzekeringssector-vanaf-1-januari-2026",
    },
    {
        "id": "company_car_deductibility",
        "title": {"en": "Company car deductibility: fossil cars ordered from Jul 2023",
                  "nl": "Aftrekbaarheid bedrijfswagens: fossiele wagens besteld vanaf juli 2023",
                  "fr": "Déductibilité des voitures de société : thermiques commandées dès juillet 2023"},
        "summary": {
            "nl": "Je bedrijfswagen ({company_car_fuel_label}, besteld op {company_car_ordered_on}) is dit jaar nog "
                  "{pct_this_year}% aftrekbaar, volgend jaar {pct_next_year}% en vanaf 2028 0%. Je leasing loopt af op "
                  "{company_car_lease_end}. Wil je zien wat een elektrische leasing doet met je nettoloon?",
            "fr": "Votre voiture de société ({company_car_fuel_label}, commandée le {company_car_ordered_on}) est encore "
                  "déductible à {pct_this_year} % cette année, {pct_next_year} % l'an prochain et 0 % dès 2028. Votre "
                  "leasing se termine le {company_car_lease_end}. Voulez-vous voir l'effet d'un leasing électrique sur "
                  "votre salaire net ?",
            "en": "Your company car ({company_car_fuel_label}, ordered on {company_car_ordered_on}) is still "
                  "{pct_this_year}% deductible this year, {pct_next_year}% next year and 0% from 2028. Your lease ends on "
                  "{company_car_lease_end}. Want to see what an electric lease does to your net pay?",
        },
        "why": {"nl": "Je bedrijfswagen ({company_car_fuel_label}) werd besteld op {company_car_ordered_on}, na juli 2023, en je leasing eindigt op {company_car_lease_end}.",
                "fr": "Votre voiture de société ({company_car_fuel_label}) a été commandée le {company_car_ordered_on}, après juillet 2023, et votre leasing se termine le {company_car_lease_end}.",
                "en": "Your company car ({company_car_fuel_label}) was ordered on {company_car_ordered_on}, after July 2023, and your lease ends on {company_car_lease_end}."},
        "cta": {"nl": "Simuleer een EV-leasing", "fr": "Simuler un leasing électrique", "en": "Simulate an EV lease"},
        "effective_date": "2026-01-01",
        "level": "federal",
        "visible_until": "2028-12-31",
        "conditions": [
            {"field": "has_company_car", "op": "eq", "value": True},
            {"field": "company_car_fossil", "op": "eq", "value": True},
            {"field": "company_car_ordered_on", "op": "date_after", "value": "2023-06-30"},
        ],
        "impact": {"kind": "yearly_schedule", "schedule": {"2026": 50, "2027": 25, "2028": 0},
                   "direction": "cost"},
        "evidence": [
            "company car: {company_car_fuel}, ordered on {company_car_ordered_on}, lease ends {company_car_lease_end} "
            "(in {company_car_lease_end_days} days)",
            "fossil-fuel cars ordered from July 2023: 50% deductible in 2026, 25% in 2027, 0% in 2028; "
            "combustion/hybrid cars ordered from 2026: 0%",
            "this year {pct_this_year}%, next year {pct_next_year}%: the employer's fleet policy will likely change at lease end",
        ],
        "actions": ["ev_lease_simulation", "home_charger_loan", "talk_to_advisor"],
        "stakes": "high",
        "legal_basis": "legitimate_interest",
        "source_url": "https://www.kbc.be/ondernemen/nl/product/kredieten/fiscaliteit-bedrijfswagens.html",
    },
    {
        "id": "renovation_obligation_6y",
        "title": {"en": "Flemish renovation obligation: EPC E/F homes bought since 2023 must reach D within 6 years",
                  "nl": "Vlaamse renovatieplicht: EPC E/F gekocht sinds 2023 moet binnen 6 jaar label D halen",
                  "fr": "Obligation flamande de rénovation : PEB E/F acheté depuis 2023 doit atteindre D en 6 ans"},
        "summary": {
            "nl": "Je woning (aangekocht op {mortgage_deed_date}, EPC-label {mortgage_epc}) valt onder de Vlaamse "
                  "renovatieplicht: label D halen binnen 6 jaar, dus tegen {renovation_deadline}. Nog "
                  "{renovation_months_left} maanden. Een gespreid renovatieplan met Mijn VerbouwLening (0–1,5%) kan helpen.",
            "fr": "Votre logement (acheté le {mortgage_deed_date}, label PEB {mortgage_epc}) relève de l'obligation "
                  "flamande de rénovation : atteindre le label D dans les 6 ans, soit avant le {renovation_deadline}. "
                  "Encore {renovation_months_left} mois. Un plan échelonné avec Mijn VerbouwLening (0–1,5 %) peut aider.",
            "en": "Your home (bought on {mortgage_deed_date}, EPC label {mortgage_epc}) falls under the Flemish "
                  "renovation obligation: reach label D within 6 years, so by {renovation_deadline}. "
                  "{renovation_months_left} months left. A staged plan with Mijn VerbouwLening (0–1.5%) can help.",
        },
        "why": {"nl": "Je woningkrediet vermeldt aktedatum {mortgage_deed_date} en EPC-label {mortgage_epc}; de Vlaamse renovatieplicht geldt voor E/F-woningen gekocht sinds 2023.",
                "fr": "Votre crédit logement mentionne l'acte du {mortgage_deed_date} et le label PEB {mortgage_epc} ; l'obligation flamande vise les logements E/F achetés depuis 2023.",
                "en": "Your mortgage file shows deed date {mortgage_deed_date} and EPC label {mortgage_epc}; the Flemish obligation covers E/F homes bought since 2023."},
        "cta": {"nl": "Plan mijn renovatie", "fr": "Planifier ma rénovation", "en": "Plan my renovation"},
        "effective_date": "2026-01-01",
        "level": "regional",
        "region": "flanders",
        "visible_until": "2031-12-31",
        "conditions": [
            {"field": "has_mortgage", "op": "eq", "value": True},
            {"field": "mortgage_epc", "op": "in", "value": ["E", "F"]},
            {"field": "mortgage_deed_date", "op": "date_after", "value": "2022-12-31"},
        ],
        "impact": {"kind": "none", "direction": "cost"},
        "evidence": [
            "home bought on {mortgage_deed_date} with EPC label {mortgage_epc}",
            "Flemish renovation obligation: EPC E/F homes bought since 2023 must reach label D within 6 years "
            "(relaxed in 2026): deadline {renovation_deadline}, {renovation_months_left} months left",
            "renovation loans: Mijn VerbouwLening at 0-1.5%, staged renovation loan",
        ],
        "actions": ["renovation_plan", "verbouwlening_simulation", "talk_to_advisor"],
        "stakes": "medium",
        "legal_basis": "legal_obligation",
        "source_url": "https://www.certifisc.be/nl/posts/renovatieplicht-in-vlaanderen-soepelere-regels-sinds-1-januari-2026-",
    },
]


class Rulebook:
    """Thread-safe, in-memory rulebook. Admin-added rules live until restart."""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._rules: dict[str, WorldRule] = {}
        self.reset()

    def reset(self) -> None:
        with self._lock:
            self._rules = {r["id"]: WorldRule.model_validate(r) for r in BUILTIN_RULES}

    def rules(self) -> list[WorldRule]:
        return list(self._rules.values())

    def get(self, rule_id: str) -> WorldRule | None:
        return self._rules.get(rule_id)

    def add(self, rule: WorldRule) -> WorldRule:
        with self._lock:
            if rule.id in self._rules:
                raise ValueError("rule id already exists")
            if len(self._rules) >= 50:
                raise ValueError("rulebook is full")
            self._rules[rule.id] = rule
            return rule


RULEBOOK = Rulebook()


def detect(customer: Customer, today: date, rulebook: Rulebook | None = None) -> list[Moment]:
    book = rulebook or RULEBOOK
    twin = build_twin(customer, today)
    moments: list[Moment] = []
    for rule in book.rules():
        if rule.requires_insurance_data and not customer.consents.use_insurance_data:
            continue
        if today < (rule.visible_from or rule.effective_date) or today > (rule.visible_until or today):
            continue
        if rule.affected(twin):
            moments.append(rule.to_moment(twin, today))
    return moments
