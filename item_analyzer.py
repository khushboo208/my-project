import base64
import json
import mimetypes
import os
import re

import requests
from PIL import Image


DEFAULT_ANALYSIS = {
    "is_clothing_item": True,
    "article_type": "clothing item",
    "color": "unknown",
    "main_category": "Apparel",
    "sub_category": "General",
    "fit": "regular",
    "material": "unknown",
    "gender": "unisex",
    "season_tags": ["all-season"],
    "occasion_tags": ["casual"],
    "style_tags": ["everyday"],
    "description": "This appears to be a clothing item.",
    "extra_details": {},
}

ARTICLE_HINTS = {
    "dress": ["dress", "gown", "maxi dress", "mini dress"],
    "top": [
        "top",
        "blouse",
        "tank",
        "camisole",
        "tee",
        "t-shirt",
        "t shirt",
        "shirt",
        "button-up",
        "button down",
        "polo",
    ],
    "trousers": ["trouser", "trousers", "pants", "pant", "jeans", "jean", "slacks"],
    "skirt": ["skirt"],
    "jacket": ["jacket", "coat", "blazer", "cardigan"],
    "hoodie": ["hoodie", "sweatshirt"],
    "shorts": ["shorts", "short"],
    "sneakers": ["sneaker", "sneakers", "trainer", "trainers"],
    "heels": ["heel", "heels", "pump", "pumps", "stiletto"],
    "boots": ["boot", "boots"],
    "sandals": ["sandal", "sandals"],
    "shoes": ["shoe", "shoes", "loafer", "loafers", "oxford", "oxfords", "flats"],
    "bag": ["bag", "handbag", "purse", "tote", "backpack", "clutch"],
    "watch": ["watch"],
    "belt": ["belt"],
    "scarf": ["scarf"],
    "hat": ["hat", "cap", "beanie"],
}

ARTICLE_TO_CATEGORY = {
    "dress": ("Apparel", "Dress"),
    "top": ("Apparel", "Top"),
    "trousers": ("Apparel", "Bottom"),
    "skirt": ("Apparel", "Skirt"),
    "jacket": ("Apparel", "Outerwear"),
    "hoodie": ("Apparel", "Outerwear"),
    "shorts": ("Apparel", "Bottom"),
    "sneakers": ("Footwear", "Sneakers"),
    "heels": ("Footwear", "Heels"),
    "boots": ("Footwear", "Boots"),
    "sandals": ("Footwear", "Sandals"),
    "shoes": ("Footwear", "Shoes"),
    "bag": ("Accessory", "Bag"),
    "watch": ("Accessory", "Watch"),
    "belt": ("Accessory", "Belt"),
    "scarf": ("Accessory", "Scarf"),
    "hat": ("Accessory", "Hat"),
}

NON_CLOTHING_HINTS = {
    "phone",
    "laptop",
    "computer",
    "monitor",
    "keyboard",
    "mouse",
    "chair",
    "table",
    "desk",
    "bottle",
    "cup",
    "mug",
    "plate",
    "sofa",
    "couch",
    "bed",
    "television",
    "tv",
    "book",
    "notebook",
    "plant",
    "flower vase",
    "car",
    "toy",
    "headphones",
}

TOP_PRIORITY_HINTS = [
    "t-shirt",
    "t shirt",
    "tshirt",
    "shirt",
    "blouse",
    "polo",
    "button-up",
    "button down",
    "top",
]

COLOR_BUCKETS = {
    "black": (30, 30, 30),
    "white": (225, 225, 225),
    "grey": (140, 140, 140),
    "red": (180, 50, 50),
    "blue": (60, 90, 180),
    "green": (70, 140, 70),
    "pink": (220, 140, 170),
    "brown": (130, 90, 55),
    "beige": (210, 190, 150),
    "yellow": (210, 190, 60),
}

ALLOWED_ARTICLE_TYPES = [
    "top",
    "dress",
    "trousers",
    "skirt",
    "jacket",
    "hoodie",
    "shorts",
    "sneakers",
    "heels",
    "boots",
    "sandals",
    "shoes",
    "bag",
    "watch",
    "belt",
    "scarf",
    "hat",
]


def normalize(text):
    return (text or "").strip().lower()


def parse_bool(value, default=True):
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "yes", "1"}:
            return True
        if lowered in {"false", "no", "0"}:
            return False
    return default


def parse_int(value, default=0):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _data_url_for_image(image_path):
    mime_type = mimetypes.guess_type(image_path)[0] or "image/jpeg"
    with open(image_path, "rb") as image_file:
        encoded = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded}"


def detect_dominant_color(image_path):
    try:
        image = Image.open(image_path).convert("RGB")
        width, height = image.size
        crop = image.crop((width * 0.2, height * 0.2, width * 0.8, height * 0.8))
        pixels = list(crop.getdata())
        if not pixels:
            return "unknown"

        avg = tuple(sum(channel) / len(pixels) for channel in zip(*pixels))

        def distance(color_a, color_b):
            return sum((a - b) ** 2 for a, b in zip(color_a, color_b))

        return min(COLOR_BUCKETS, key=lambda name: distance(avg, COLOR_BUCKETS[name]))
    except Exception:
        return "unknown"


def fallback_analysis(image_path):
    analysis = dict(DEFAULT_ANALYSIS)
    filename = os.path.basename(image_path).lower()
    analysis["color"] = detect_dominant_color(image_path)

    for article_type, hints in ARTICLE_HINTS.items():
        if any(hint in filename for hint in hints):
            analysis["article_type"] = article_type
            break

    analysis = enrich_from_article_type(analysis)
    analysis["description"] = build_human_description(analysis)
    return analysis


def extract_json_candidate(text):
    text = (text or "").strip()
    if not text:
        return None

    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()

    if text.startswith("{") and text.endswith("}"):
        return text

    match = re.search(r"\{.*\}", text, flags=re.DOTALL)
    if match:
        return match.group(0)

    return None


def normalize_text_field(value, default):
    if not isinstance(value, str):
        return default
    value = value.strip()
    return value or default


def normalize_list_field(value, default):
    if isinstance(value, list):
        cleaned = [str(part).strip().lower() for part in value if str(part).strip()]
        return cleaned or list(default)
    if isinstance(value, str):
        cleaned = [part.strip().lower() for part in re.split(r"[,\n;/]", value) if part.strip()]
        return cleaned or list(default)
    return list(default)


def infer_article_type_from_text(text, default="clothing item"):
    lowered = normalize(text)
    if not lowered:
        return default

    if "dress shirt" in lowered:
        return "top"

    for hint in TOP_PRIORITY_HINTS:
        if re.search(rf"\b{re.escape(hint)}\b", lowered):
            return "top"

    for article_type, hints in ARTICLE_HINTS.items():
        if any(re.search(rf"\b{re.escape(hint)}\b", lowered) for hint in hints):
            return article_type
    return default


def normalize_article_type(value, fallback_text=""):
    cleaned = normalize(value)
    if not cleaned or cleaned == "clothing item":
        return infer_article_type_from_text(fallback_text, default="clothing item")

    alias_map = {
        "shirt": "top",
        "t-shirt": "top",
        "tshirt": "top",
        "tee": "top",
        "blouse": "top",
        "polo": "top",
        "button-up shirt": "top",
        "button down shirt": "top",
        "jeans": "trousers",
        "pants": "trousers",
        "trouser": "trousers",
        "joggers": "trousers",
        "coat": "jacket",
        "blazer": "jacket",
        "cardigan": "jacket",
        "sweatshirt": "hoodie",
        "sneaker": "sneakers",
        "shoe": "shoes",
        "oxford": "shoes",
        "oxford shoes": "shoes",
        "loafers": "shoes",
        "pumps": "heels",
        "boot": "boots",
        "sandals": "sandals",
    }
    if cleaned in alias_map:
        return alias_map[cleaned]

    if cleaned in ARTICLE_HINTS:
        return cleaned

    inferred = infer_article_type_from_text(f"{cleaned} {fallback_text}", default=cleaned)
    return inferred


def decide_clothing_from_text(*texts):
    blob = " ".join(normalize(text) for text in texts if text).strip()
    if not blob:
        return True

    if "dress shirt" in blob:
        return True

    if any(re.search(rf"\b{re.escape(hint)}\b", blob) for hints in ARTICLE_HINTS.values() for hint in hints):
        return True

    if any(re.search(rf"\b{re.escape(hint)}\b", blob) for hint in NON_CLOTHING_HINTS):
        return False

    if any(word in blob for word in ["apparel", "clothing", "footwear", "wearable", "garment", "outfit"]):
        return True

    return True


def enrich_from_article_type(analysis):
    article_type = normalize(analysis.get("article_type"))
    main_category, sub_category = ARTICLE_TO_CATEGORY.get(article_type, ("Apparel", "General"))

    if normalize(analysis.get("main_category")) in {"", "apparel", "general", "unknown"}:
        analysis["main_category"] = main_category

    if normalize(analysis.get("sub_category")) in {"", "general", "unknown"}:
        analysis["sub_category"] = sub_category

    if article_type in {"dress", "skirt"} and not analysis.get("occasion_tags"):
        analysis["occasion_tags"] = ["casual", "date"]
    elif article_type in {"top", "trousers", "shorts"} and not analysis.get("occasion_tags"):
        analysis["occasion_tags"] = ["casual", "office"]
    elif article_type in {"jacket", "hoodie"} and not analysis.get("season_tags"):
        analysis["season_tags"] = ["fall", "winter"]

    return analysis


def build_human_description(analysis):
    article_type = normalize(analysis.get("article_type")) or "clothing item"
    color = normalize(analysis.get("color"))
    fit = normalize(analysis.get("fit"))
    material = normalize(analysis.get("material"))
    extra_details = analysis.get("extra_details", {}) or {}

    words = []
    if color and color != "unknown":
        words.append(color)
    if fit and fit not in {"unknown", "regular"}:
        words.append(fit)
    if material and material != "unknown":
        words.append(material)

    style = normalize(extra_details.get("style"))
    if style:
        words.append(style.replace("_", " "))

    core = " ".join(words + [article_type.replace("_", " ")]).strip()
    if article_type in {"shoes", "sneakers", "heels", "boots", "sandals"}:
        sentence = f"These appear to be {core}."
    else:
        sentence = f"It appears to be a {core}."

    feature_bits = []
    for key in ["pattern", "graphic", "print", "heel_type", "heel_height", "toe_shape", "neckline", "sleeve_length", "closure"]:
        value = extra_details.get(key)
        if value:
            feature_bits.append(str(value).replace("_", " "))

    features = extra_details.get("features")
    if isinstance(features, list):
        feature_bits.extend(str(feature).replace("_", " ") for feature in features[:4])

    if feature_bits:
        sentence += " It includes " + ", ".join(feature_bits) + "."

    return sentence


def normalize_analysis_payload(parsed, image_path=None, raw_text=""):
    if not isinstance(parsed, dict):
        return None

    normalized = dict(DEFAULT_ANALYSIS)
    lowered_map = {str(key).strip().lower(): value for key, value in parsed.items()}

    field_aliases = {
        "is_clothing_item": ["is_clothing_item", "is_clothing", "clothing_item", "wearable"],
        "article_type": ["article_type", "article", "item_type", "garment_type", "type"],
        "color": ["color", "colour", "dominant_color"],
        "main_category": ["main_category", "category", "maincategory"],
        "sub_category": ["sub_category", "subcategory"],
        "fit": ["fit", "fit_type"],
        "material": ["material", "fabric"],
        "gender": ["gender", "target_gender", "for_gender"],
        "season_tags": ["season_tags", "seasons", "season"],
        "occasion_tags": ["occasion_tags", "occasions", "occasion"],
        "style_tags": ["style_tags", "styles", "style"],
        "description": ["description", "summary", "caption"],
        "extra_details": ["extra_details", "details", "attributes"],
    }

    for target_field, aliases in field_aliases.items():
        for alias in aliases:
            if alias in lowered_map:
                normalized[target_field] = lowered_map[alias]
                break

    if not isinstance(normalized.get("extra_details"), dict):
        normalized["extra_details"] = {}

    known_aliases = {alias for aliases in field_aliases.values() for alias in aliases}
    for key, value in parsed.items():
        cleaned_key = str(key).strip().lower()
        if cleaned_key not in known_aliases and value not in (None, "", [], {}):
            normalized["extra_details"][cleaned_key] = value

    normalized["is_clothing_item"] = parse_bool(normalized.get("is_clothing_item"), True)
    normalized["color"] = normalize_text_field(normalized.get("color"), DEFAULT_ANALYSIS["color"])
    normalized["fit"] = normalize_text_field(normalized.get("fit"), DEFAULT_ANALYSIS["fit"])
    normalized["material"] = normalize_text_field(normalized.get("material"), DEFAULT_ANALYSIS["material"])
    normalized["gender"] = normalize_text_field(normalized.get("gender"), DEFAULT_ANALYSIS["gender"])
    if normalized["gender"] in {"men", "man", "male"}:
        normalized["gender"] = "male"
    elif normalized["gender"] in {"women", "woman", "female"}:
        normalized["gender"] = "female"
    elif normalized["gender"] not in {"male", "female", "unisex"}:
        normalized["gender"] = "unisex"
    normalized["season_tags"] = normalize_list_field(normalized.get("season_tags"), DEFAULT_ANALYSIS["season_tags"])
    normalized["occasion_tags"] = normalize_list_field(normalized.get("occasion_tags"), DEFAULT_ANALYSIS["occasion_tags"])
    normalized["style_tags"] = normalize_list_field(normalized.get("style_tags"), DEFAULT_ANALYSIS["style_tags"])

    article_context = " ".join(
        [
            str(normalized.get("article_type", "")),
            str(normalized.get("sub_category", "")),
            str(normalized.get("description", "")),
            json.dumps(normalized.get("extra_details", {})),
            raw_text or "",
        ]
    )
    normalized["article_type"] = normalize_article_type(normalized.get("article_type"), article_context)
    normalized["main_category"] = normalize_text_field(normalized.get("main_category"), DEFAULT_ANALYSIS["main_category"])
    normalized["sub_category"] = normalize_text_field(normalized.get("sub_category"), DEFAULT_ANALYSIS["sub_category"])
    normalized = enrich_from_article_type(normalized)

    if normalized["color"] == "unknown" and image_path:
        normalized["color"] = detect_dominant_color(image_path)

    description = normalize_text_field(normalized.get("description"), "")
    if (
        not description
        or description.startswith("{")
        or description.startswith("[")
        or '"item_type"' in description
        or '"features"' in description
    ):
        normalized["description"] = build_human_description(normalized)
    else:
        normalized["description"] = description

    return normalized


def extract_output_text(payload):
    choices = payload.get("choices", [])
    if not choices:
        return ""

    content = choices[0].get("message", {}).get("content", "")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for entry in content:
            if isinstance(entry, dict) and entry.get("type") == "text":
                parts.append(entry.get("text", ""))
            elif isinstance(entry, str):
                parts.append(entry)
        return "\n".join(part for part in parts if part)
    return ""


def call_hf_json(api_key, model, messages, error_label):
    response = requests.post(
        "https://router.huggingface.co/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": messages,
            "temperature": 0.1,
            "max_tokens": 500,
        },
        timeout=25,
    )
    if not response.ok:
        return None, None, f"{error_label} {response.status_code}: {response.text}"

    payload = response.json()
    output_text = extract_output_text(payload)
    if not output_text:
        return None, None, f"{error_label} returned no output text"

    json_candidate = extract_json_candidate(output_text)
    if not json_candidate:
        return None, output_text, f"{error_label} response was not valid JSON"

    parsed = json.loads(json_candidate)
    return parsed, output_text, None


def analyze_clothing_item(image_path):
    api_key = os.getenv("HF_TOKEN")
    model = os.getenv("HF_VISION_MODEL", "CohereLabs/aya-vision-32b:cohere")

    if not api_key:
        return None, "HF_TOKEN is missing"

    image_data_url = _data_url_for_image(image_path)

    try:
        detection_messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a strict clothing detector. "
                            "First decide if the image is mainly a wearable fashion item. "
                            "Wearable fashion items include clothing, footwear, bags, belts, scarves, hats, and watches. "
                            "Return JSON only with these exact keys: "
                            "is_clothing_item, article_type, confidence, non_clothing_reason. "
                            f"article_type must be one of: {', '.join(ALLOWED_ARTICLE_TYPES)}, or 'unknown'. "
                            "If the image is not clearly a wearable fashion item, set is_clothing_item to false."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Detect whether this image is a wearable fashion item. Return JSON only.",
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url},
                    },
                ],
            },
        ]
        detection_parsed, detection_text, detection_error = call_hf_json(
            api_key,
            model,
            detection_messages,
            "Hugging Face detection",
        )
        if detection_error:
            return None, detection_error

        detection_article = normalize_article_type(
            (detection_parsed or {}).get("article_type"),
            detection_text or "",
        )
        detection_confidence = parse_int((detection_parsed or {}).get("confidence"), 0)
        detection_is_clothing = parse_bool((detection_parsed or {}).get("is_clothing_item"), True)
        detection_reason = normalize_text_field(
            (detection_parsed or {}).get("non_clothing_reason"),
            "",
        )

        if (
            not detection_is_clothing
            and detection_confidence >= 60
            and not decide_clothing_from_text(detection_article, detection_text or "")
        ):
            reason = detection_reason or "This does not look like a clothing item."
            return None, f"{reason} Please upload clothes, shoes, or wearable accessories only."

        classification_messages = [
            {
                "role": "system",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "You are a precise fashion item classifier. "
                            "Classify the item using clean canonical labels. "
                            "Return JSON only with these exact keys: "
                            "is_clothing_item, article_type, color, main_category, sub_category, fit, material, "
                            "season_tags, occasion_tags, style_tags, description, extra_details. "
                            f"article_type must be one of: {', '.join(ALLOWED_ARTICLE_TYPES)}. "
                            "main_category must be one of: Apparel, Footwear, Accessory. "
                            "description must be one short human sentence, never JSON, and should describe the whole item naturally."
                        ),
                    }
                ],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": (
                            "Analyze this wearable item. "
                            f"Detector hint article_type={detection_article or 'unknown'}. "
                            "Use the hint only if it matches the image. "
                            "Return JSON only."
                        ),
                    },
                    {
                        "type": "image_url",
                        "image_url": {"url": image_data_url},
                    },
                ],
            },
        ]
        parsed, output_text, classification_error = call_hf_json(
            api_key,
            model,
            classification_messages,
            "Hugging Face classification",
        )
        if classification_error:
            return None, classification_error

        if detection_article and detection_article != "clothing item":
            parsed.setdefault("article_type", detection_article)

        normalized = normalize_analysis_payload(parsed, image_path=image_path, raw_text=output_text)
        if not normalized:
            return None, "The AI response could not be normalized"

        ai_says_clothing = parse_bool(parsed.get("is_clothing_item"), detection_is_clothing)
        text_says_clothing = decide_clothing_from_text(
            normalized.get("article_type"),
            normalized.get("main_category"),
            normalized.get("sub_category"),
            normalized.get("description"),
            json.dumps(normalized.get("extra_details", {})),
            output_text,
            detection_text,
        )

        text_has_non_clothing = any(
            re.search(
                rf"\b{re.escape(hint)}\b",
                " ".join(
                    [
                        normalize(str(parsed.get("article_type", ""))),
                        normalize(str(parsed.get("main_category", ""))),
                        normalize(str(parsed.get("sub_category", ""))),
                        normalize(str(parsed.get("description", ""))),
                        normalize(output_text),
                        normalize(detection_text),
                    ]
                ),
            )
            for hint in NON_CLOTHING_HINTS
        )
        article_is_generic = normalize(normalized.get("article_type")) in {"", "clothing item", "item", "wearable"}

        if text_has_non_clothing and article_is_generic:
            return None, "This does not look like a clothing item. Please upload clothes, shoes, or wearable accessories only."

        if not ai_says_clothing and not text_says_clothing:
            return None, "This does not look like a clothing item. Please upload clothes, shoes, or wearable accessories only."

        return normalized, None
    except Exception as exc:
        return None, str(exc)
