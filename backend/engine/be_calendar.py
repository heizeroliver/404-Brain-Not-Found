"""Curated Belgian personal-finance calendar (next 12 months from today).

Conservative on purpose: no amounts or ceilings are stated. Each item says how
sure the date is ("basis"):
  legal    - the date follows from the law itself (e.g. the calendar year ends 31 Dec)
  typical  - the usual timing; the exact date is set yearly or by the bank / employer
  estimate - a rough indication; the real date depends on your own contract or file

Tips are information about options, never advice.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any, Callable

from .models import Customer

CATEGORIES = ("tax", "savings", "pension", "insurance", "loan", "home", "car", "income")
BASES = ("legal", "typical", "estimate")

FOD = "FOD Financiën / SPF Finances"
VLABEL = "Vlaamse Belastingdienst"
KBC = "kbc.be"
VLA = "vlaanderen.be"

T = dict[str, str]


def _t(nl: str, en: str, fr: str) -> T:
    return {"nl": nl, "en": en, "fr": fr}


CATEGORY_LABELS: dict[str, T] = {
    "tax": _t("Belastingen", "Tax", "Impôts"),
    "savings": _t("Sparen", "Savings", "Épargne"),
    "pension": _t("Pensioen", "Pension", "Pension"),
    "insurance": _t("Verzekeringen", "Insurance", "Assurances"),
    "loan": _t("Leningen", "Loans", "Crédits"),
    "home": _t("Wonen", "Home", "Logement"),
    "car": _t("Auto", "Car", "Voiture"),
    "income": _t("Inkomen", "Income", "Revenus"),
}

DISCLAIMER = _t(
    "Algemene informatie over Belgische data, geen fiscaal of financieel advies. Bedragen en plafonds legt de wet elk jaar "
    "vast: controleer ze bij FOD Financiën of je adviseur. 'Typisch' en 'schatting' betekenen dat de exacte datum kan verschillen.",
    "General information about Belgian dates, not tax or financial advice. Amounts and ceilings are set by law each year: "
    "check them with FOD Financiën or your adviser. 'Typical' and 'estimate' mean the exact date may differ.",
    "Informations générales sur des dates belges, pas un conseil fiscal ou financier. Les montants et plafonds sont fixés "
    "chaque année par la loi : vérifiez-les auprès du SPF Finances ou de votre conseiller. « Habituel » et « estimation » "
    "signifient que la date exacte peut varier.",
)


@dataclass(frozen=True)
class Item:
    id: str
    category: str
    start: date
    end: date | None
    title: T
    what: T
    tip: T
    basis: str
    source: str
    relevant: Callable[[Customer], bool]
    recurrence: str | None = None  # "monthly" | "quarterly" | None

    def out(self, customer: Customer, lang: str) -> dict[str, Any]:
        return {
            "id": self.id, "source": "belgium", "category": self.category,
            "date": self.start.isoformat(), "end": self.end.isoformat() if self.end else None,
            "title": self.title[lang], "what": self.what[lang], "tip": self.tip[lang],
            "basis": self.basis, "source_hint": self.source, "recurrence": self.recurrence,
            "for_you": bool(self.relevant(customer)),
        }


# ---------------------------------------------------------- relevance ---

def _employee(c: Customer) -> bool:
    return c.employment.contract_type in ("permanent", "temporary") and not c.employment.self_employed


def _earning(c: Customer) -> bool:
    return c.employment.contract_type in ("permanent", "temporary", "self_employed")


def _has_policy(kind: str) -> Callable[[Customer], bool]:
    return lambda c: any(p.kind == kind for p in c.policies)


def _owner(c: Customer) -> bool:
    return c.housing.status == "owner"


def _wants_home(c: Customer) -> bool:
    return any(g.purpose in ("house_purchase", "renovation") for g in c.goals)


def _has_car(c: Customer) -> bool:
    return _has_policy("car")(c) or c.employment.company_car is not None or any(g.purpose == "car" for g in c.goals)


def _always(_: Customer) -> bool:
    return True


def _never(_: Customer) -> bool:
    return False


# ---------------------------------------------------------- dates ---

def _next(today: date, month: int, day: int) -> date:
    d = date(today.year, month, day)
    return d if d >= today else date(today.year + 1, month, day)


def _anniversary(today: date, origin: date) -> date:
    try:
        d = origin.replace(year=today.year)
    except ValueError:  # 29 Feb
        d = date(today.year, 3, 1)
    if d < today:
        try:
            d = origin.replace(year=today.year + 1)
        except ValueError:
            d = date(today.year + 1, 3, 1)
    return d


def _months_before(d: date, months: int) -> date:
    y, m = d.year, d.month - months
    while m <= 0:
        m += 12
        y -= 1
    day = min(d.day, 28)
    return date(y, m, day)


# ---------------------------------------------------------- catalogue ---

def build(customer: Customer, today: date) -> list[Item]:
    """All items whose date (or window start) falls within [today, today + 365d]."""
    ny = _next(today, 12, 31)          # coming 31 December
    y1 = ny.year + 1                   # the following calendar year
    first_of_next = _next(today, today.month % 12 + 1, 1) if today.day > 1 else today
    car_pol = next((p for p in customer.policies if p.kind == "car"), None)
    road_date = _anniversary(today, car_pol.renewal_date) if car_pol else first_of_next
    items: list[Item] = [
        Item("pension_saving_deadline", "pension", ny, None,
             _t("Pensioensparen: laatste stortingen dit jaar", "Pension saving: last payments this year",
                "Épargne-pension : derniers versements de l'année"),
             _t("Wat je vóór 31 december stort, telt voor het belastingvoordeel van dit jaar; banken hanteren vaak een eigen, vroegere uiterste datum.",
                "What you pay in before 31 December counts for this year's tax benefit; banks often use their own, earlier cut-off.",
                "Ce que vous versez avant le 31 décembre compte pour l'avantage fiscal de cette année ; les banques appliquent souvent une date limite plus tôt."),
             _t("Een vaste maandelijkse storting spreidt het bedrag en voorkomt dat je de deadline mist.",
                "A fixed monthly payment spreads the amount and avoids missing the deadline.",
                "Un versement mensuel fixe étale le montant et évite de rater l'échéance."),
             "legal", FOD, lambda c: c.products.pension_saving is not None or (_earning(c) and c.age < 65)),
        Item("pension_saving_ceiling", "pension", _next(today, 10, 1), ny,
             _t("Pensioensparen: kies je plafond", "Pension saving: choose your ceiling", "Épargne-pension : choisissez votre plafond"),
             _t("Er zijn twee wettelijke jaarplafonds met een verschillend belastingvoordeel; het jaarbedrag legt de wet vast.",
                "There are two legal yearly ceilings with a different tax benefit; the yearly amounts are set by law.",
                "Il existe deux plafonds annuels légaux avec un avantage fiscal différent ; les montants sont fixés par la loi."),
             _t("Het lagere plafond geeft procentueel meer voordeel, het hogere meer in euro; bekijk de actuele bedragen bij FOD Financiën.",
                "The lower ceiling gives a higher percentage benefit, the higher one more in euros; check current amounts with FOD Financiën.",
                "Le plafond bas donne un avantage plus élevé en pourcentage, le haut davantage en euros ; vérifiez les montants actuels au SPF Finances."),
             "typical", FOD, lambda c: c.products.pension_saving is not None),
        Item("long_term_savings_deadline", "savings", ny, None,
             _t("Langetermijnsparen: stortingen vóór jaareinde", "Long-term savings: payments before year end",
                "Épargne à long terme : versements avant la fin de l'année"),
             _t("Premies voor een individuele levensverzekering of een lening voor een tweede woning tellen per kalenderjaar.",
                "Premiums for an individual life insurance or a loan for a second home count per calendar year.",
                "Les primes d'assurance-vie individuelle ou d'un crédit pour une seconde habitation comptent par année civile."),
             _t("Het plafond hangt af van je inkomen en is gedeeld met andere uitgaven; check FOD Financiën voor je situatie.",
                "The ceiling depends on your income and is shared with other expenses; check FOD Financiën for your situation.",
                "Le plafond dépend de vos revenus et est partagé avec d'autres dépenses ; vérifiez auprès du SPF Finances."),
             "legal", FOD, lambda c: _earning(c) and c.age < 65),
        Item("gifts_deadline", "tax", ny, None,
             _t("Giften aan erkende instellingen", "Gifts to recognised charities", "Libéralités aux institutions agréées"),
             _t("Giften van minstens €40 per jaar aan een erkende instelling kunnen een belastingvermindering geven; het attest gaat elektronisch naar de fiscus.",
                "Gifts of at least €40 a year to a recognised institution can give a tax reduction; the certificate goes to the tax authority electronically.",
                "Des dons d'au moins 40 € par an à une institution agréée peuvent donner une réduction d'impôt ; l'attestation est transmise électroniquement au fisc."),
             _t("Alleen giften binnen het kalenderjaar tellen voor dat jaar; bundel ze per instelling.",
                "Only gifts within the calendar year count for that year; group them per institution.",
                "Seuls les dons de l'année civile comptent pour cette année ; regroupez-les par institution."),
             "legal", FOD, _never),
        Item("savings_interest_reset", "savings", date(y1, 1, 1), None,
             _t("Nieuwe vrijstelling spaarrente", "New tax-free savings interest", "Nouvelle exonération des intérêts d'épargne"),
             _t("De eerste schijf rente op gereglementeerde spaarrekeningen is per kalenderjaar vrij van roerende voorheffing.",
                "The first tranche of interest on regulated savings accounts is exempt from withholding tax per calendar year.",
                "La première tranche d'intérêts sur les comptes d'épargne réglementés est exonérée de précompte mobilier par année civile."),
             _t("De vrijstelling geldt per persoon; met een partner kan elk een eigen spaarrekening de vrijstelling benutten. Bedrag: check FOD Financiën.",
                "The exemption applies per person; partners can each use it with their own savings account. Amount: check FOD Financiën.",
                "L'exonération s'applique par personne ; chaque partenaire peut l'utiliser avec son propre compte. Montant : voir SPF Finances."),
             "legal", FOD, lambda c: c.accounts.savings_balance > 0),
        Item("mortgage_certificate", "loan", date(y1, 1, 15), date(y1, 2, 28),
             _t("Fiscaal attest woonlening", "Mortgage tax certificate", "Attestation fiscale du crédit hypothécaire"),
             _t("Je bank bezorgt een jaarlijks attest met je afbetalingen, dat je nodig hebt voor je belastingaangifte.",
                "Your bank sends a yearly certificate with your repayments, which you need for your tax return.",
                "Votre banque envoie une attestation annuelle de vos remboursements, utile pour votre déclaration."),
             _t("Of je lening nog voordeel geeft hangt af van de datum van je akte en je regio; controleer het vooraf ingevulde vak.",
                "Whether your loan still gives a benefit depends on your deed date and region; check the pre-filled box.",
                "L'avantage éventuel dépend de la date de l'acte et de votre région ; vérifiez la case pré-remplie."),
             "typical", KBC, lambda c: c.products.mortgage is not None),
        Item("tax_on_web_opens", "tax", date(ny.year + 1, 5, 1), date(ny.year + 1, 5, 31),
             _t("Belastingaangifte opent (Tax-on-web)", "Tax return opens (Tax-on-web)", "Ouverture de la déclaration (Tax-on-web)"),
             _t("De aangifte personenbelasting voor inkomsten van vorig jaar opent meestal in mei via MyMinfin.",
                "The personal income tax return for last year's income usually opens in May via MyMinfin.",
                "La déclaration à l'impôt des personnes physiques pour les revenus de l'an passé ouvre en général en mai via MyMinfin."),
             _t("Kijk de vooraf ingevulde gegevens na: pensioensparen, giften, kinderopvang en woonlening worden soms vergeten.",
                "Check the pre-filled data: pension saving, gifts, childcare and mortgage are sometimes missed.",
                "Vérifiez les données pré-remplies : épargne-pension, dons, garde d'enfants et crédit sont parfois oubliés."),
             "typical", FOD, _earning),
        Item("tax_return_deadline", "tax", date(ny.year + 1, 7, 15), None,
             _t("Deadline belastingaangifte", "Tax return deadline", "Date limite de la déclaration"),
             _t("Online indienen kan meestal tot half juli; met een boekhouder of als zelfstandige geldt vaak een latere datum.",
                "Filing online is usually possible until mid-July; via an accountant or as self-employed a later date often applies.",
                "Le dépôt en ligne est en général possible jusqu'à mi-juillet ; via un comptable ou comme indépendant, une date plus tardive s'applique souvent."),
             _t("Wie vroeg indient, krijgt een eventuele terugbetaling doorgaans ook sneller.",
                "Filing early usually also means any refund arrives sooner.",
                "Déposer tôt signifie en général un remboursement éventuel plus rapide."),
             "typical", FOD, _earning),
        Item("tax_assessment", "tax", today, date(ny.year + 1, 6, 30),
             _t("Aanslagbiljet vorig inkomstenjaar", "Tax assessment for last income year", "Avertissement-extrait de rôle"),
             _t("Het aanslagbiljet voor een tijdig ingediende aangifte komt meestal vóór eind juni van het jaar erna.",
                "The assessment for a return filed on time usually arrives before the end of June of the following year.",
                "L'avertissement-extrait de rôle d'une déclaration rentrée à temps arrive en général avant fin juin de l'année suivante."),
             _t("Een terugbetaling kan je laten meetellen als spaargeld; moet je bijbetalen, dan staat de betaaltermijn op het biljet.",
                "A refund can go straight to savings; if you owe tax, the payment term is on the assessment.",
                "Un remboursement peut aller vers l'épargne ; si vous devez payer, le délai figure sur l'avertissement."),
             "typical", FOD, _earning),
        Item("property_tax_bill", "home", date(ny.year + 1, 6, 1), date(ny.year + 1, 9, 30),
             _t("Aanslag onroerende voorheffing", "Property tax bill (onroerende voorheffing)", "Précompte immobilier"),
             _t("Eigenaars in Vlaanderen krijgen het aanslagbiljet meestal tussen juni en september.",
                "Owners in Flanders usually receive the bill between June and September.",
                "En Flandre, les propriétaires reçoivent l'avis en général entre juin et septembre."),
             _t("Er bestaan verminderingen, bv. voor kinderen ten laste of een energiezuinige renovatie; check de voorwaarden.",
                "Reductions exist, e.g. for dependent children or an energy-efficient renovation; check the conditions.",
                "Des réductions existent, p.ex. pour enfants à charge ou une rénovation énergétique ; vérifiez les conditions."),
             "typical", VLABEL, _owner),
        Item("renovation_premium", "home", date(ny.year + 1, 1, 1), None,
             _t("Mijn VerbouwPremie: voorwaarden checken", "Mijn VerbouwPremie: check conditions", "Mijn VerbouwPremie : vérifier les conditions"),
             _t("Premies voor renovatie en energie in Vlaanderen vraag je aan na de eindfactuur; voorwaarden wijzigen vaak op 1 januari.",
                "Flemish renovation and energy premiums are requested after the final invoice; conditions often change on 1 January.",
                "Les primes flamandes à la rénovation et à l'énergie se demandent après la facture finale ; les conditions changent souvent au 1er janvier."),
             _t("Bewaar facturen en attesten; de termijn om aan te vragen na de factuur is beperkt, check vlaanderen.be.",
                "Keep invoices and certificates; the period to apply after the invoice is limited, check vlaanderen.be.",
                "Conservez factures et attestations ; le délai pour introduire la demande est limité, voir vlaanderen.be."),
             "estimate", VLA, lambda c: _owner(c) or _wants_home(c)),
        Item("holiday_pay", "income", date(ny.year + 1, 5, 1), date(ny.year + 1, 6, 30),
             _t("Vakantiegeld", "Holiday pay", "Pécule de vacances"),
             _t("Werknemers krijgen hun vakantiegeld meestal in mei of juni.",
                "Employees usually receive holiday pay in May or June.",
                "Les salariés reçoivent en général leur pécule en mai ou juin."),
             _t("Een deel meteen opzijzetten voor pensioensparen of je buffer houdt het buiten de vakantie-uitgaven.",
                "Setting part aside for pension saving or your buffer keeps it out of holiday spending.",
                "Mettre une partie de côté pour l'épargne-pension ou le coussin l'écarte des dépenses de vacances."),
             "typical", FOD, _employee),
        Item("year_end_bonus", "income", date(ny.year, 12, 1), date(ny.year, 12, 31),
             _t("Eindejaarspremie", "End-of-year bonus", "Prime de fin d'année"),
             _t("In veel sectoren wordt de eindejaarspremie in december betaald.",
                "In many sectors the end-of-year bonus is paid in December.",
                "Dans de nombreux secteurs, la prime de fin d'année est versée en décembre."),
             _t("Valt ze vóór 31 december, dan kan je ze nog inzetten voor pensioensparen van dit jaar.",
                "If it arrives before 31 December you can still use it for this year's pension saving.",
                "Si elle arrive avant le 31 décembre, elle peut encore servir à l'épargne-pension de l'année."),
             "typical", FOD, _employee),
        Item("child_benefit", "income", first_of_next, None,
             _t("Groeipakket (kinderbijslag)", "Child benefit (Groeipakket)", "Allocations familiales (Groeipakket)"),
             _t("Het Groeipakket in Vlaanderen wordt maandelijks betaald; andere regio's hebben een eigen stelsel.",
                "Flanders' Groeipakket is paid monthly; other regions have their own system.",
                "Le Groeipakket flamand est versé chaque mois ; les autres régions ont leur propre régime."),
             _t("Een automatische maandelijkse overschrijving naar een spaarrekening voor je kind maakt sparen vanzelf.",
                "An automatic monthly transfer to a savings account for your child makes saving effortless.",
                "Un virement mensuel automatique vers un compte d'épargne pour votre enfant rend l'épargne facile."),
             "typical", VLA, lambda c: bool(c.household.children), recurrence="monthly"),
        Item("road_tax", "car", road_date, None,
             _t("Verkeersbelasting", "Road tax (verkeersbelasting)", "Taxe de circulation"),
             _t("De jaarlijkse verkeersbelasting komt rond de verjaardag van de inschrijving van je auto.",
                "The yearly road tax arrives around the anniversary of your car's registration.",
                "La taxe de circulation annuelle arrive vers la date anniversaire de l'immatriculation."),
             _t("Het bedrag hangt af van motor en uitstoot; vergelijk dat mee bij de keuze van een volgende auto.",
                "The amount depends on engine and emissions; include it when choosing your next car.",
                "Le montant dépend du moteur et des émissions ; tenez-en compte pour votre prochaine voiture."),
             "estimate", VLABEL, _has_car),
    ]

    # Self-employed advance tax payments (typical quarter dates).
    for n, (m, d) in enumerate(((10, 10), (12, 20), (4, 10), (7, 10)), start=1):
        dd = _next(today, m, d)
        items.append(Item(
            f"advance_payment_{dd.isoformat()}", "tax", dd, None,
            _t("Voorafbetaling zelfstandigen", "Advance tax payment (self-employed)", "Versement anticipé (indépendants)"),
            _t("Zelfstandigen kunnen per kwartaal belasting vooraf betalen om een vermeerdering te vermijden.",
               "Self-employed people can prepay tax per quarter to avoid a surcharge.",
               "Les indépendants peuvent payer l'impôt par trimestre pour éviter une majoration."),
            _t("Vroegere voorafbetalingen geven een groter voordeel dan latere; de exacte data maakt FOD Financiën jaarlijks bekend.",
               "Earlier advance payments give a larger benefit than later ones; FOD Financiën publishes the exact dates yearly.",
               "Les versements anticipés plus tôt donnent un avantage plus grand ; le SPF Finances publie les dates exactes chaque année."),
            "typical", FOD, lambda c: c.employment.self_employed or c.employment.contract_type == "self_employed",
            recurrence="quarterly"))

    # Insurance: cancellation deadline 3 months before each policy anniversary (Belgian insurance law).
    names = {"home": _t("woonverzekering", "home insurance", "assurance habitation"),
             "car": _t("autoverzekering", "car insurance", "assurance auto"),
             "family": _t("familiale verzekering", "family liability insurance", "assurance familiale"),
             "hospitalisation": _t("hospitalisatieverzekering", "hospitalisation insurance", "assurance hospitalisation")}
    for p in customer.policies:
        ren = _anniversary(today, p.renewal_date)
        cut = _months_before(ren, 3)
        if cut < today:
            cut, ren = _months_before(_anniversary(ren + timedelta(days=1), p.renewal_date), 3), \
                _anniversary(ren + timedelta(days=1), p.renewal_date)
        nm = names[p.kind]
        items.append(Item(
            f"policy_cancel_{p.kind}", "car" if p.kind == "car" else "insurance", cut, None,
            _t(f"Opzegtermijn {nm['nl']}", f"Notice period: {nm['en']}", f"Délai de résiliation : {nm['fr']}"),
            _t("Een jaarcontract kan je opzeggen tot minstens 3 maanden vóór de vervaldag.",
               "A yearly contract can be cancelled up to at least 3 months before its renewal date.",
               "Un contrat annuel peut être résilié au moins 3 mois avant son échéance."),
            _t("Vergelijk dekking en premie ruim vóór deze datum; daarna loopt het contract een jaar verder.",
               "Compare cover and premium well before this date; after it the contract runs another year.",
               "Comparez couverture et prime bien avant cette date ; ensuite le contrat court un an de plus."),
            "legal", "FSMA / " + KBC, _always))

    # Rent indexation on the lease anniversary (renters).
    if customer.housing.status == "renting" and customer.housing.rent_since:
        d = _anniversary(today, customer.housing.rent_since)
        items.append(Item(
            "rent_indexation", "home", d, None,
            _t("Mogelijke huurindexering", "Possible rent indexation", "Indexation possible du loyer"),
            _t("De verhuurder mag de huur één keer per jaar indexeren, op de verjaardag van het huurcontract, na schriftelijke vraag.",
               "The landlord may index the rent once a year, on the lease anniversary, after a written request.",
               "Le bailleur peut indexer le loyer une fois par an, à la date anniversaire du bail, après demande écrite."),
            _t("De indexering volgt een wettelijke formule en kan beperkt zijn door het energielabel; reken ze na.",
               "Indexation follows a legal formula and can be limited by the energy label; check the calculation.",
               "L'indexation suit une formule légale et peut être limitée par le certificat énergétique ; vérifiez le calcul."),
            "legal", VLA, _always))

    limit = today + timedelta(days=365)
    return [i for i in items if today <= i.start <= limit]


PERSONAL_CATEGORY = (
    ("pension", "pension"), ("insurance", "insurance"), ("holiday", "income"), ("income", "income"),
    ("salary", "income"), ("bonus", "income"), ("home", "home"), ("house", "home"), ("rent", "home"),
    ("energy", "home"), ("mortgage", "loan"), ("loan", "loan"), ("car", "car"), ("tax", "tax"),
    ("cash", "savings"), ("saving", "savings"), ("term", "savings"), ("child", "income"),
)


def personal_category(moment_type: str) -> str:
    for key, cat in PERSONAL_CATEGORY:
        if key in moment_type:
            return cat
    return "savings"


def calendar(customer: Customer, today: date, lang: str) -> list[dict[str, Any]]:
    return [i.out(customer, lang) for i in build(customer, today)]
