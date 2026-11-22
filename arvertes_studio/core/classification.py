"""Categorias persistentes e sugestões de classificação por termos."""

import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol


CATEGORY_LABELS = {
    "skin": "Pele",
    "hair": "Cabelo",
    "eyes": "Olhos",
    "clothing": "Roupas",
    "footwear": "Calçados",
    "accessories": "Acessórios",
    "metal": "Metal",
    "vegetation": "Vegetação",
    "buildings": "Construções",
    "creatures": "Criaturas",
    "objects": "Objetos",
    "unidentified": "Não identificado",
}

UNIDENTIFIED = "unidentified"

_RULE_TERMS = {
    "skin": "pele skin epiderme epidermis",
    "hair": "cabelo cabelos hair tranca trancas braid braids barba beard",
    "eyes": "olho olhos eye eyes eyeball eyeballs iris",
    "clothing": (
        "roupa roupas clothing camisa camiseta shirt calca calcas pants jacket "
        "jaqueta casaco moletom hoodie vestido dress"
    ),
    "footwear": (
        "calcado calcados bota botas boot boots sapato sapatos shoe shoes "
        "footwear tenis sneakers"
    ),
    "accessories": (
        "acessorio acessorios accessory accessories pulseira bracelet mochila "
        "backpack colar necklace brinco earring oculos glasses"
    ),
    "metal": "metal metallic aco steel ferro iron cobre copper aluminio aluminum aluminium",
    "vegetation": (
        "vegetacao vegetation arvore tree arbusto shrub foliage folhagem leaf leaves grama grass"
    ),
    "buildings": "construcao construcoes building buildings parede wall telhado roof",
    "creatures": "criatura criaturas creature creatures monstro monster",
    "objects": "objeto objetos prop props crate caixote barril barrel",
}

_CATEGORY_BY_TERM = {
    term: category for category, terms in _RULE_TERMS.items() for term in terms.split()
}


@dataclass(frozen=True, slots=True)
class Suggestion:
    category: str
    reason: str
    evidence: tuple[str, ...]


class Classifier(Protocol):
    def suggest(self, object_name: str, material_names: Iterable[str] = ()) -> Suggestion:
        """Sugere uma categoria a partir dos dados fornecidos."""


def _terms(name: str) -> set[str]:
    decomposed = unicodedata.normalize("NFKD", name)
    unaccented = "".join(character for character in decomposed if not unicodedata.combining(character))
    spaced = re.sub(r"([A-Z])([A-Z][a-z])", r"\1 \2", unaccented)
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", spaced)
    return set(re.findall(r"[a-z]+", spaced.casefold()))


class RuleClassifier:
    def suggest(self, object_name: str, material_names: Iterable[str] = ()) -> Suggestion:
        sources = [("nome do objeto", object_name)]
        sources.extend((f'material “{name}”', name) for name in sorted(set(material_names)))
        categories = set()
        evidence = []
        for source, name in sources:
            for term in sorted(_terms(name) & _CATEGORY_BY_TERM.keys()):
                categories.add(_CATEGORY_BY_TERM[term])
                evidence.append(f"{source} ({term})")

        if not categories:
            return Suggestion(UNIDENTIFIED, "Revise manualmente para identificar a categoria.", ())
        if len(categories) > 1:
            labels = ", ".join(CATEGORY_LABELS[category] for category in sorted(categories))
            reason = f"Termos de categorias diferentes ({labels}). Revise manualmente."
            return Suggestion(UNIDENTIFIED, reason, tuple(evidence))

        category = categories.pop()
        reason = f"Termos encontrados indicam {CATEGORY_LABELS[category]}. Confirme a sugestão."
        return Suggestion(category, reason, tuple(evidence))
