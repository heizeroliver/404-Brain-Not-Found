"""Pydantic models shared by the engine and the API.

Moment follows ACTION_PLAN.md Appendix A, plus:
  - source:   which calendar produced it ("life_calendar" = option A,
              "world_rule" = option D, "protection" = option C)
  - category: used by the vulnerability guard ("sales" moments are dropped
              while a customer is in care mode)
  - facts:    structured numbers the narrator may use (never free text)
"""
from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, computed_field

Stakes = Literal["low", "medium", "high"]
Channel = Literal["in_app_card", "push", "voice", "advisor", "letter"]
Source = Literal["life_calendar", "world_rule", "protection"]
Category = Literal["sales", "info", "care"]
Language = Literal["nl", "fr"]
Region = Literal["flanders", "wallonia", "brussels"]

FactValue = str | int | float | bool | None


class Moment(BaseModel):
    type: str = Field(pattern=r"^[a-z0-9_]{3,60}$")
    window: tuple[date, date]
    confidence: float = Field(ge=0.0, le=1.0)
    stakes: Stakes
    evidence: list[str] = Field(min_length=1)
    actions: list[str] = Field(min_length=1)
    channel_hint: Channel = "in_app_card"
    legal_basis: str
    human_review: bool = False
    source: Source = "life_calendar"
    category: Category = "info"
    facts: dict[str, FactValue] = Field(default_factory=dict)


# ---------------------------------------------------------------- customer --

class Child(BaseModel):
    name: str
    birthdate: date


class Household(BaseModel):
    partner: bool = False
    children: list[Child] = Field(default_factory=list)


class CompanyCar(BaseModel):
    fuel: Literal["diesel", "petrol", "hybrid", "electric"]
    ordered_on: date
    lease_end: date


class Employment(BaseModel):
    employer: str | None = None
    gross_monthly_salary: float = 0.0
    net_monthly_salary: float = 0.0
    contract_type: Literal["permanent", "temporary", "self_employed", "pension", "none"] = "none"
    self_employed: bool = False
    company_car: CompanyCar | None = None


class MonthBalance(BaseModel):
    month: str  # YYYY-MM
    balance: float


class Accounts(BaseModel):
    current_balance: float = 0.0
    savings_balance: float = 0.0
    savings_opened_on: date | None = None
    fidelity_date: date | None = None
    savings_history: list[MonthBalance] = Field(default_factory=list)


class Housing(BaseModel):
    status: Literal["renting", "owner", "other"] = "other"
    rent_since: date | None = None
    monthly_rent: float | None = None
    landlord: str | None = None


class Transaction(BaseModel):
    date: date
    amount: float
    payee: str
    category: str


class Policy(BaseModel):
    kind: Literal["home", "car", "family", "hospitalisation"]
    renewal_date: date
    premium: float
    new_premium: float

    @computed_field  # type: ignore[misc]
    @property
    def pct_increase(self) -> float:
        if self.premium <= 0:
            return 0.0
        return (self.new_premium / self.premium - 1.0) * 100.0


class Mortgage(BaseModel):
    deed_date: date
    epc_label: Literal["A", "B", "C", "D", "E", "F"]
    outstanding: float
    monthly_payment: float


class PensionSaving(BaseModel):
    contributions_ytd: float = 0.0
    ceiling: Literal[1050, 1350] = 1050
    monthly: float = 0.0


class Bolero(BaseModel):
    portfolio_value: float
    unrealised_gains: float
    gains_realised_ytd: float = 0.0


class TermAccount(BaseModel):
    amount: float
    maturity_date: date
    rate: float  # gross yearly rate in %


class Products(BaseModel):
    mortgage: Mortgage | None = None
    pension_saving: PensionSaving | None = None
    bolero: Bolero | None = None
    term_account: TermAccount | None = None


class SecurityAlert(BaseModel):
    """A payment the fraud engine held (e.g. a Verification of Payee close match)."""
    kind: Literal["vop_close_match", "new_payee_high_amount"]
    date: date
    amount: float
    payee_shown: str
    payee_registered: str


class Security(BaseModel):
    guardian_angel_active: bool = False
    recent_alert: SecurityAlert | None = None


class Consents(BaseModel):
    """Toggles the customer controls. They change which rules run."""
    model_config = ConfigDict(strict=True, extra="forbid")  # real booleans only, no "yes"/"1"

    use_insurance_data: bool = True
    use_other_banks: bool = False
    marketing: bool = True


class Customer(BaseModel):
    id: str = Field(pattern=r"^[a-z0-9_]{2,40}$")
    name: str
    first_name: str
    language: Language
    region: Region
    age: int = Field(ge=0, le=120)
    birthdate: date
    digital_comfort: int = Field(ge=1, le=5)
    household: Household = Field(default_factory=Household)
    employment: Employment = Field(default_factory=Employment)
    accounts: Accounts = Field(default_factory=Accounts)
    housing: Housing = Field(default_factory=Housing)
    transactions: list[Transaction] = Field(default_factory=list)
    policies: list[Policy] = Field(default_factory=list)
    products: Products = Field(default_factory=Products)
    consents: Consents = Field(default_factory=Consents)
    security: Security = Field(default_factory=Security)

    def public_profile(self) -> dict[str, Any]:
        """What /me returns: no transaction list, no raw balances history."""
        return {
            "id": self.id,
            "name": self.name,
            "first_name": self.first_name,
            "language": self.language,
            "region": self.region,
            "age": self.age,
            "digital_comfort": self.digital_comfort,
            "household": self.household.model_dump(mode="json"),
            "employment": {
                "employer": self.employment.employer,
                "contract_type": self.employment.contract_type,
                "company_car": (
                    self.employment.company_car.model_dump(mode="json")
                    if self.employment.company_car else None
                ),
            },
            "accounts": {
                "current_balance": self.accounts.current_balance,
                "savings_balance": self.accounts.savings_balance,
            },
            "housing": self.housing.model_dump(mode="json"),
            "policies": [p.model_dump(mode="json") for p in self.policies],
            "products": self.products.model_dump(mode="json"),
            "consents": self.consents.model_dump(mode="json"),
            "transaction_count": len(self.transactions),
        }
