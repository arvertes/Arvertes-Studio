"""Parâmetros explícitos da bancada procedural, independentes do Blender."""
from math import isfinite
import re

PALETTE = ("skin", "cloth", "leather", "hair", "metal")
OPTIONS = {"silhouette": ("slender", "stocky"), "head": ("oval", "angular"),
           "hair": ("cropped", "crest", "braid"), "beard": ("none", "short"),
           "outfit": ("jacket", "tunic"), "accessory": ("pendant", "pack")}
VIEWS = {"front", "profile", "back", "three_quarter", "detail"}
COLOR = re.compile(r"#[a-fA-F0-9]{6}")
TEXTURE_ROLES = ("basecolor", "normal", "orm")


def validate_style(value):
    ranges = {"height_m": (1.4, 2.2), "width": (.80, 1.25), "depth": (.85, 1.25)}
    keys = set(ranges) | set(OPTIONS) | {"palette", "triangle_budget", "texture_edge"}
    if not isinstance(value, dict) or value.keys() != keys:
        raise ValueError("Parâmetros da receita procedural incompatíveis.")
    for key, (low, high) in ranges.items():
        number = value[key]
        if type(number) not in (int, float) or not isfinite(number) or not low <= number <= high:
            raise ValueError("Dimensão fora dos limites da receita procedural.")
    if any(value[key] not in options for key, options in OPTIONS.items()):
        raise ValueError("Selecione opções de anatomia, cabelo, roupa e acessório compatíveis.")
    palette = value["palette"]
    if (not isinstance(palette, dict) or set(palette) != set(PALETTE)
            or any(not isinstance(color, str) or not COLOR.fullmatch(color) for color in palette.values())):
        raise ValueError("A paleta requer cinco cores hexadecimais RGB.")
    if type(value["triangle_budget"]) is not int or not 1000 <= value["triangle_budget"] <= 25_000:
        raise ValueError("Orçamento experimental de 1.000 a 25.000 triângulos.")
    if type(value["texture_edge"]) is not int or value["texture_edge"] not in (64, 128, 256):
        raise ValueError("Resolução experimental de 64, 128 ou 256 pixels.")
    return value


def reference_views(value, count):
    if value is None:
        return [None] * count
    if (not isinstance(value, list) or len(value) != count
            or any(item is not None and (not isinstance(item, str) or item not in VIEWS) for item in value)):
        raise ValueError("Declare uma vista conhecida ou nula para cada referência.")
    return value


def validate_adaptation(options):
    required = {"height_m", "front", "require_humanoid"}
    if not isinstance(options, dict) or not required <= options.keys() or options.keys() - required - {"materials"}:
        raise ValueError("Informe altura, frente e requisito de rig para adaptação.")
    height = options["height_m"]
    if (type(height) not in (int, float) or not .50 <= height <= 3.0
            or options["front"] not in ("-Y", "+Y", "-X", "+X")
            or type(options["require_humanoid"]) is not bool
            or options.get("materials", "preserve") not in ("preserve", "fill_missing_neutral")):
        raise ValueError("Normalização fora da faixa admitida.")
    return options


def study_presets():
    return {
        "túnica e trança": {
            "height_m": 1.86, "width": .84, "depth": .92, "silhouette": "slender", "head": "oval",
            "hair": "braid", "beard": "none", "outfit": "tunic", "accessory": "pendant",
            "palette": {"skin": "#ac6951", "cloth": "#258988", "leather": "#213c51",
                        "hair": "#403035", "metal": "#e8ba67"},
            "triangle_budget": 9500, "texture_edge": 128,
        },
        "jaqueta e mochila": {
            "height_m": 1.58, "width": 1.20, "depth": 1.17, "silhouette": "stocky", "head": "angular",
            "hair": "crest", "beard": "short", "outfit": "jacket", "accessory": "pack",
            "palette": {"skin": "#bd8c68", "cloth": "#ab4e33", "leather": "#51332f",
                        "hair": "#2b2e39", "metal": "#d7cdd0"},
            "triangle_budget": 9500, "texture_edge": 128,
        },
    }
