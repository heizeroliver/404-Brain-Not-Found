"""Curated KBC product knowledge for Kate Talk (deterministic, no LLM).

Kate only talks about KBC products and the customer's own data. Everything here is factual,
conservative product-type information: no rates, prices or returns. It is information, not
advice; conditions change, so every answer points to kbc.be and an adviser.
"""
from __future__ import annotations

import re
from typing import Any, Callable

import config
from engine import spending
from engine.intent import _fold
from engine.models import Customer

Facts = dict[str, Any]
T = dict[str, str]


def _p(pid: str, keywords: list[str], name: T, summary: T,
       when: Callable[[Facts], str | None], reasons: dict[str, T]) -> dict[str, Any]:
    return {"id": pid, "keywords": keywords, "name": name, "summary": summary, "when": when, "reasons": reasons}


PRODUCTS: list[dict[str, Any]] = [
    _p("savings_account", ["spaarrekening", "spaarboek", "savings account", "compte d'epargne", "compte epargne"],
       {"nl": "KBC Spaarrekening", "en": "KBC savings account", "fr": "Compte d'épargne KBC"},
       {"nl": "Een gereglementeerde spaarrekening met een basisrente en een getrouwheidspremie. In België is een eerste schijf interest vrijgesteld van roerende voorheffing; zie kbc.be voor de actuele voorwaarden.",
        "en": "A regulated savings account with a base rate and a fidelity premium. In Belgium a first tranche of interest is exempt from withholding tax; see kbc.be for current conditions.",
        "fr": "Un compte d'épargne réglementé avec un taux de base et une prime de fidélité. En Belgique, une première tranche d'intérêts est exonérée de précompte mobilier ; voir kbc.be pour les conditions actuelles."},
       lambda f: "buffer_short" if f["buffer_shortfall"] > 0 else None,
       {"buffer_short": {"nl": "Je spaargeld dekt je buffer van 6 maanden nog niet volledig.",
                         "en": "Your savings do not yet fully cover your 6-month buffer.",
                         "fr": "Votre épargne ne couvre pas encore entièrement votre réserve de 6 mois."}}),
    _p("term_account", ["termijnrekening", "term account", "compte a terme"],
       {"nl": "KBC Termijnrekening", "en": "KBC term account", "fr": "Compte à terme KBC"},
       {"nl": "Je zet een bedrag vast voor een gekozen looptijd tegen een vooraf gekende rente; tussentijds opnemen is niet vrij. Zie kbc.be voor de actuele voorwaarden.",
        "en": "You fix an amount for a chosen term at a rate known up front; early withdrawal is not free. See kbc.be for current conditions.",
        "fr": "Vous bloquez un montant pour une durée choisie à un taux connu d'avance ; un retrait anticipé n'est pas libre. Voir kbc.be pour les conditions actuelles."},
       lambda f: "surplus" if f["remaining"] > 0 else None,
       {"surplus": {"nl": "Na je buffer en je doelen blijft er spaargeld over dat je niet meteen nodig hebt.",
                    "en": "After your buffer and goals, some savings are left that you do not need right away.",
                    "fr": "Après votre réserve et vos objectifs, il reste de l'épargne dont vous n'avez pas besoin tout de suite."}}),
    _p("pension_saving", ["pensioensparen", "pensioenspaar", "pension saving", "epargne pension", "epargne-pension"],
       {"nl": "KBC Pensioensparen", "en": "KBC pension saving", "fr": "Épargne-pension KBC"},
       {"nl": "Langetermijnsparen voor later met een Belgische belastingvermindering, binnen een jaarlijks plafond dat de wet bepaalt (zie kbc.be). Pensioenspaarfondsen kunnen in waarde dalen.",
        "en": "Long-term saving for retirement with a Belgian tax reduction, within a yearly ceiling set by law (see kbc.be). Pension saving funds can fall in value.",
        "fr": "Épargne à long terme pour la pension avec une réduction d'impôt belge, dans un plafond annuel fixé par la loi (voir kbc.be). Les fonds d'épargne-pension peuvent perdre de la valeur."},
       lambda f: ("has_plan" if f["has_pension_saving"] else ("surplus" if f["remaining"] > 0 else None)),
       {"has_plan": {"nl": "Je hebt al een pensioenspaarplan; je kan je stortingen van dit jaar bekijken.",
                     "en": "You already have a pension saving plan; you can review this year's contributions.",
                     "fr": "Vous avez déjà un plan d'épargne-pension ; vous pouvez consulter vos versements de cette année."},
        "surplus": {"nl": "Je hebt spaargeld boven je buffer en doelen en nog geen pensioenspaarplan.",
                    "en": "You have savings above your buffer and goals and no pension saving plan yet.",
                    "fr": "Vous avez de l'épargne au-delà de votre réserve et de vos objectifs, sans plan d'épargne-pension."}}),
    _p("investment_plan", ["beleggingsplan", "beleggen", "investment plan", "investing", "plan d'investissement", "investir", "bolero"],
       {"nl": "KBC Beleggingsplan", "en": "KBC investment plan", "fr": "Plan d'investissement KBC"},
       {"nl": "Periodiek een vast bedrag beleggen in fondsen. Er is risico: je kan geld verliezen en rendement is nooit zeker.",
        "en": "Investing a fixed amount in funds at regular intervals. There is risk: you can lose money and returns are never certain.",
        "fr": "Investir régulièrement un montant fixe dans des fonds. Il y a un risque : vous pouvez perdre de l'argent et le rendement n'est jamais certain."},
       lambda f: "surplus" if f["remaining"] > 0 else None,
       {"surplus": {"nl": "Er blijft spaargeld over na je buffer en doelen; beleggen is enkel iets voor geld dat je lang kan missen.",
                    "en": "Savings remain after your buffer and goals; investing only suits money you can do without for a long time.",
                    "fr": "Il reste de l'épargne après votre réserve et vos objectifs ; investir ne convient qu'à de l'argent dont vous pouvez vous passer longtemps."}}),
    _p("home_loan", ["woonkrediet", "hypothe", "home loan", "mortgage", "credit hypothecaire", "pret hypothecaire"],
       {"nl": "KBC Woonkrediet", "en": "KBC home loan", "fr": "Crédit logement KBC"},
       {"nl": "Een lening om een woning te kopen, bouwen of verbouwen, met vaste of variabele rente. Zie kbc.be voor de actuele voorwaarden.",
        "en": "A loan to buy, build or renovate a home, with a fixed or variable rate. See kbc.be for current conditions.",
        "fr": "Un prêt pour acheter, construire ou rénover un logement, à taux fixe ou variable. Voir kbc.be pour les conditions actuelles."},
       lambda f: ("house_goal" if "house_purchase" in f["purposes"] else ("has_mortgage" if f["has_mortgage"] else None)),
       {"house_goal": {"nl": "Je hebt een doel ingesteld om een woning te kopen.",
                       "en": "You set a goal to buy a home.",
                       "fr": "Vous avez fixé un objectif d'achat de logement."},
        "has_mortgage": {"nl": "Je hebt al een woonkrediet bij KBC.",
                         "en": "You already have a home loan with KBC.",
                         "fr": "Vous avez déjà un crédit logement chez KBC."}}),
    _p("renovation_loan", ["renovatiekrediet", "renovatielening", "energielening", "renovation loan", "energy loan",
                           "pret renovation", "pret energie", "credit renovation"],
       {"nl": "KBC Renovatie- en energielening", "en": "KBC renovation and energy loan", "fr": "Prêt rénovation et énergie KBC"},
       {"nl": "Een lening voor verbouwingen of energiebesparende werken zoals isolatie of een warmtepomp. Zie kbc.be voor de actuele voorwaarden en eventuele premies.",
        "en": "A loan for renovation or energy-saving works such as insulation or a heat pump. See kbc.be for current conditions and possible grants.",
        "fr": "Un prêt pour des travaux de rénovation ou d'économie d'énergie comme l'isolation ou une pompe à chaleur. Voir kbc.be pour les conditions actuelles et d'éventuelles primes."},
       lambda f: ("renovation_goal" if "renovation" in f["purposes"] else ("energy_spend" if "energy" in f["categories"] and f["owner"] else None)),
       {"renovation_goal": {"nl": "Je hebt een renovatiedoel ingesteld; zo kan je vergelijken tussen sparen en lenen.",
                            "en": "You set a renovation goal; this lets you compare saving with borrowing.",
                            "fr": "Vous avez fixé un objectif de rénovation ; cela permet de comparer épargne et emprunt."},
        "energy_spend": {"nl": "Energie is een van je uitgavencategorieën en je bent eigenaar van je woning.",
                         "en": "Energy is one of your spending categories and you own your home.",
                         "fr": "L'énergie fait partie de vos dépenses et vous êtes propriétaire."}}),
    _p("home_insurance", ["woningverzekering", "brandverzekering", "home insurance", "assurance habitation", "assurance incendie"],
       {"nl": "KBC Woningverzekering", "en": "KBC home insurance", "fr": "Assurance habitation KBC"},
       {"nl": "Verzekert je woning en inboedel tegen onder meer brand, water- en stormschade, ook als huurder. Zie kbc.be voor de waarborgen.",
        "en": "Covers your home and contents against fire, water and storm damage among others, also for tenants. See kbc.be for the cover.",
        "fr": "Couvre votre logement et son contenu contre l'incendie, les dégâts des eaux et la tempête entre autres, aussi pour les locataires. Voir kbc.be pour les garanties."},
       lambda f: ("renewal" if "home" in f["policies"] else ("renting" if f["renting"] else None)),
       {"renewal": {"nl": "Je hebt een woningverzekering met een komende vervaldag.",
                    "en": "You have a home insurance policy with an upcoming renewal.",
                    "fr": "Vous avez une assurance habitation avec une échéance à venir."},
        "renting": {"nl": "Je huurt; ook huurders hebben een huurdersaansprakelijkheid. Een woonkrediet is voor jou nu niet aan de orde.",
                    "en": "You rent; tenants also carry tenant liability. A home loan is not on the table for you now.",
                    "fr": "Vous êtes locataire ; les locataires ont aussi une responsabilité locative. Un crédit logement n'est pas d'actualité."}}),
    _p("car_insurance", ["autoverzekering", "car insurance", "assurance auto", "omnium"],
       {"nl": "KBC Autoverzekering", "en": "KBC car insurance", "fr": "Assurance auto KBC"},
       {"nl": "Verplichte BA-verzekering met optionele omnium en bijstand. Zie kbc.be voor de waarborgen.",
        "en": "Mandatory third-party liability cover with optional comprehensive (omnium) and assistance. See kbc.be for the cover.",
        "fr": "Responsabilité civile obligatoire avec omnium et assistance en option. Voir kbc.be pour les garanties."},
       lambda f: ("car_policy" if "car" in f["policies"] else ("car_goal" if "car" in f["purposes"] else None)),
       {"car_policy": {"nl": "Je hebt een autoverzekering met een komende vervaldag.",
                       "en": "You have a car insurance policy with an upcoming renewal.",
                       "fr": "Vous avez une assurance auto avec une échéance à venir."},
        "car_goal": {"nl": "Je spaart voor een auto.", "en": "You are saving for a car.", "fr": "Vous épargnez pour une voiture."}}),
    _p("family_insurance", ["familiale", "familiale verzekering", "family insurance", "hospitalisatie", "hospitalisation",
                            "hospitalization", "assurance familiale", "assurance hospitalisation"],
       {"nl": "KBC Familiale en hospitalisatieverzekering", "en": "KBC family and hospitalisation insurance",
        "fr": "Assurance familiale et hospitalisation KBC"},
       {"nl": "De familiale dekt schade die jij of je gezin per ongeluk aan anderen toebrengt; de hospitalisatieverzekering dekt ziekenhuiskosten. Zie kbc.be voor de waarborgen.",
        "en": "Family liability covers damage you or your household accidentally cause to others; hospitalisation insurance covers hospital costs. See kbc.be for the cover.",
        "fr": "L'assurance familiale couvre les dommages que vous ou votre ménage causez accidentellement à autrui ; l'assurance hospitalisation couvre les frais d'hôpital. Voir kbc.be pour les garanties."},
       lambda f: "children" if f["children"] else None,
       {"children": {"nl": "Er zijn kinderen in je gezin.", "en": "There are children in your household.",
                     "fr": "Il y a des enfants dans votre ménage."}}),
    _p("kbc_mobile", ["kbc mobile", "de app", "the app", "l'app", "kaartbeheer", "card control", "kaart blokkeren", "block my card", "bloquer ma carte"],
       {"nl": "KBC Mobile", "en": "KBC Mobile", "fr": "KBC Mobile"},
       {"nl": "De KBC-app om te bankieren, betalen en je kaarten te beheren (bijvoorbeeld blokkeren of limieten aanpassen), met Kate als digitale assistent.",
        "en": "The KBC app to bank, pay and manage your cards (for example block them or change limits), with Kate as digital assistant.",
        "fr": "L'app KBC pour gérer vos comptes, payer et contrôler vos cartes (par exemple les bloquer ou modifier les limites), avec Kate comme assistante numérique."},
       lambda f: None, {}),
]

_BY_ID = {p["id"]: p for p in PRODUCTS}
_GENERIC = re.compile(r"(kbc[- ]?product|producten van kbc|welke producten|wat biedt kbc|which products|what products"
                      r"|kbc offer|products? (?:do|does|would|could)|quels produits|produits kbc|produits de kbc"
                      r"|que propose kbc)")
_ASSUME = {"nl": "Informatie, geen advies. Bekijk kbc.be voor de actuele voorwaarden.",
           "en": "Information, not advice. Check kbc.be for current conditions.",
           "fr": "Information, pas un conseil. Consultez kbc.be pour les conditions actuelles."}
_ADVISER = {"nl": "Dit is informatie, geen advies; een KBC-adviseur kan je verder helpen.",
            "en": "This is information, not advice; a KBC adviser can help you further.",
            "fr": "Ceci est une information, pas un conseil ; un conseiller KBC peut vous aider."}
_INTRO = {"nl": "Op basis van je eigen gegevens kunnen deze KBC-producten interessant zijn om over te lezen: {names}.",
          "en": "Based on your own data, these KBC products may be worth reading about: {names}.",
          "fr": "Sur la base de vos propres données, ces produits KBC peuvent être utiles à découvrir : {names}."}


def _l(t: T, lang: str) -> str:
    return t.get(lang) or t["en"]


def _kw(folded: str, kw: str) -> bool:
    return re.search(r"(?<![a-z])" + re.escape(kw), folded) is not None


def customer_facts(customer: Customer, alloc: dict[str, Any], lang: str = "en") -> Facts:
    rows = spending.summarize(customer, config.today(), 3, lang)["rows"]
    return {
        "purposes": {g.purpose for g in customer.goals},
        "remaining": float(alloc.get("remaining", 0.0)),
        "buffer_shortfall": float(alloc.get("buffer_shortfall", 0.0)),
        "categories": {r["key"] for r in rows},
        "owner": customer.housing.status == "owner",
        "renting": customer.housing.status == "renting",
        "has_mortgage": customer.products.mortgage is not None,
        "has_pension_saving": customer.products.pension_saving is not None,
        "policies": {p.kind for p in customer.policies},
        "children": len(customer.household.children),
    }


def _card(p: dict[str, Any], lang: str, reason: str | None) -> dict[str, Any]:
    card = {"id": p["id"], "name": _l(p["name"], lang), "summary": _l(p["summary"], lang)}
    if reason:
        card["why"] = _l(p["reasons"][reason], lang)
    return card


def answer(text: str, customer: Customer, lang: str, alloc: dict[str, Any]) -> dict[str, Any] | None:
    """Product question -> {message, products, evidence, assumptions}; anything else -> None."""
    folded = _fold(text or "")
    hits = [p for p in PRODUCTS if any(_kw(folded, _fold(k)) for k in p["keywords"])]
    generic = _GENERIC.search(folded) is not None
    if not hits and not generic:
        return None
    facts = customer_facts(customer, alloc, lang)
    scored = [(p, p["when"](facts)) for p in (hits or PRODUCTS)]
    if hits:
        chosen = scored[:3]
    else:
        # the customer's own goals first, then catalogue order
        chosen = sorted((s for s in scored if s[1]), key=lambda s: not s[1].endswith("goal"))[:3]
        if not chosen:
            chosen = [(_BY_ID["savings_account"], None), (_BY_ID["kbc_mobile"], None)]
    cards = [_card(p, lang, r) for p, r in chosen]
    if hits:
        first = cards[0]
        msg = f"{first['name']}: {first['summary']}"
        if first.get("why"):
            msg = f"{first['name']}: {first['summary'].split('. ')[0].rstrip('.')}. {first['why']}"
    else:
        msg = _l(_INTRO, lang).format(names=", ".join(c["name"] for c in cards))
    msg = f"{msg} {_l(_ADVISER, lang)}"
    evidence = [f"{p['id']}: {r}" for p, r in chosen if r]
    return {"message": msg, "products": cards, "evidence": evidence, "assumptions": [_l(_ASSUME, lang)]}


_COMPETITORS = re.compile(r"\b(revolut|bnp|paribas|fortis|belfius|ing|argenta|bunq|n26|crelan|beobank|fintro"
                          r"|keytrade|triodos|axa bank|vdk)\b")
_PAYMENT = re.compile(r"(overschrijving|overgeschreven|betaling|betaald|gestort|transfer|payment|paid|sent"
                      r"|virement|paiement|paye|verse)")
_OFFTOPIC = re.compile(r"\b(weerbericht|weersverwachting|wat voor weer|weather|meteo|quel temps|grap|mop|joke|blague|voetbal|football|soccer"
                       r"|sport|tennis|politiek|politics|politique|verkiezing|election|president|recept|recipe"
                       r"|recette|koken|cooking|cuisine|python|javascript|programmeren|programming|write code"
                       r"|schrijf code|film|movie|song|liedje|chanson|horoscoop|horoscope)\b")


def out_of_scope(text: str) -> str | None:
    """'competitor' (other banks' products), 'offtopic' (not banking) or None."""
    folded = _fold(text or "")
    if _COMPETITORS.search(folded) and not _PAYMENT.search(folded):
        return "competitor"
    if _OFFTOPIC.search(folded):
        return "offtopic"
    return None


_SCOPE = {
    "competitor": {"nl": "Ik praat enkel over KBC-producten en je eigen KBC-gegevens, dus over andere banken kan ik niets zeggen.",
                   "en": "I only talk about KBC products and your own KBC data, so I can't comment on other banks.",
                   "fr": "Je ne parle que des produits KBC et de vos propres données KBC, je ne peux donc rien dire sur d'autres banques."},
    "offtopic": {"nl": "Daar kan ik niet mee helpen. Ik praat over je eigen financiën en KBC-producten, bijvoorbeeld je uitgaven, je spaargeld of je doelen.",
                 "en": "I can't help with that. I talk about your own finances and KBC products, for example your spending, savings or goals.",
                 "fr": "Je ne peux pas vous aider pour cela. Je parle de vos finances et des produits KBC, par exemple vos dépenses, votre épargne ou vos objectifs."},
}


def scope_message(kind: str, lang: str) -> str:
    return _l(_SCOPE.get(kind, _SCOPE["offtopic"]), lang)
