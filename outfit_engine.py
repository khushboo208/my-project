import random

ARTICLE_ALIASES = {
    "upper": ["tshirt", "t-shirt", "t shirt", "tee", "shirt", "top", "blouse", "hoodie", "sweater"],
    "outer": ["jacket", "coat", "blazer", "cardigan"],
    "bottom": ["jean", "jeans", "pant", "pants", "trouser", "trousers", "skirt", "jogger", "short", "shorts"],
    "dress": ["dress", "gown"],
    "footwear": ["shoe", "shoes", "sneaker", "sneakers", "trainer", "trainers", "heel", "heels", "boot", "boots", "sandal", "sandals"],
    "accessory": ["watch", "bag", "handbag", "belt", "scarf", "hat"],
}

COLOR_KEYWORDS = {
    "black": ["black"],
    "white": ["white", "cream", "ivory"],
    "blue": ["blue", "navy"],
    "red": ["red", "maroon", "burgundy"],
    "pink": ["pink", "rose"],
    "green": ["green", "olive"],
    "brown": ["brown", "tan", "beige", "khaki", "camel"],
    "grey": ["grey", "gray", "charcoal", "silver"],
}

NEUTRAL_COLORS = {"black", "white", "grey", "brown", "beige", "cream", "tan"}
OCCASION_KEYWORDS = {
    "party": {"party", "night out", "festive", "statement", "celebration", "gala", "event", "soiree"},
    "formal": {"formal", "evening", "tailored", "elevated", "sophisticated", "business", "professional", "corporate"},
    "office": {"office", "work", "professional", "smart-casual", "business casual", "corporate", "meeting"},
    "casual": {"casual", "everyday", "relaxed", "weekend", "laid back", "comfortable", "effortless", "casual wear", "daily", "regular"},
    "date": {"date", "romantic", "cute", "feminine", "dinner", "intimate", "evening", "special occasion", "datenight", "date night"},
    "sporty": {"sporty", "active", "athleisure", "athletic", "dynamic", "energetic"},
}

MOOD_KEYWORDS = {
    "comfy": {"comfy", "cozy", "relaxed", "soft", "comfortable", "effortless", "luxurious comfort"},
    "classy": {"classy", "polished", "elevated", "sleek", "sophisticated", "refined", "elegant", "timeless"},
    "bold": {"bold", "statement", "edgy", "dramatic", "eye-catching", "confident", "show-stopping"},
    "cute": {"cute", "sweet", "playful", "romantic", "charming", "feminine", "delicate"},
    "minimal": {"minimal", "clean", "simple", "neutral", "understated", "streamlined", "modern"},
    "sporty": {"sporty", "active", "athleisure", "athletic", "dynamic", "energetic"},
    "vintage": {"vintage", "retro", "classic", "timeless", "heritage", "traditional"},
}

WEATHER_ALIASES = {
    "summer": {"summer", "hot", "warm"},
    "winter": {"winter", "cold", "chilly"},
    "rainy": {"rain", "rainy", "storm", "wet"},
}

COLOR_FAMILIES = {
    "black": "neutral",
    "white": "neutral",
    "grey": "neutral",
    "gray": "neutral",
    "brown": "earth",
    "beige": "earth",
    "tan": "earth",
    "cream": "earth",
    "blue": "cool",
    "navy": "cool",
    "green": "cool",
    "red": "warm",
    "orange": "warm",
    "yellow": "warm",
    "pink": "warm",
    "purple": "cool",
}

SEASON_TAG_MAP = {
    "summer": {"summer", "spring", "warm-weather"},
    "winter": {"winter", "fall", "cold-weather"},
    "rainy": {"rainy", "monsoon", "all-season", "transitional"},
    "normal": {"all-season", "spring", "fall", "transitional"},
}


def normalize(text):
    return (text or "").strip().lower()


def split_tags(raw_value):
    if not raw_value:
        return set()
    return {normalize(tag) for tag in raw_value.split(",") if normalize(tag)}


def item_text_blob(item):
    fields = [
        item.get("article_type"),
        item.get("color"),
        item.get("gender"),
        item.get("main_category"),
        item.get("sub_category"),
        item.get("fit"),
        item.get("material"),
        item.get("season_tags"),
        item.get("occasion_tags"),
        item.get("style_tags"),
        item.get("description"),
    ]
    return " ".join(normalize(field) for field in fields if field)


def article_matches(article, aliases):
    article = normalize(article)
    return any(alias in article for alias in aliases)


def infer_item_category(item):
    article = normalize(item.get("article_type"))
    description = normalize(item.get("description"))
    full_text = f"{article} {description}"

    for category, aliases in ARTICLE_ALIASES.items():
        if any(alias in full_text for alias in aliases):
            return category
    return None


def message_has_style_intent(user_message, parsed_request=None):
    if parsed_request and parsed_request.get("intent") in {"style_request", "outfit_request"}:
        return True

    text = normalize(user_message)
    if not text:
        return False

    # Enhanced fashion keywords
    keywords = [
        "outfit", "wear", "style", "look", "dress", "ensemble", "fit", "silhouette",
        "party", "casual", "formal", "office", "date", "business", "professional",
        "winter", "summer", "rainy", "comfy", "classy", "bold", "cute", "minimal",
        "elegant", "sophisticated", "curate", "styling", "fashion", "chic", "refined"
    ]
    return any(keyword in text for keyword in keywords)


def detect_requested_color(text):
    text = normalize(text)
    for canonical, variants in COLOR_KEYWORDS.items():
        if any(variant in text for variant in variants):
            return canonical
    return None


def detect_requested_weather(text):
    text = normalize(text)
    for canonical, variants in WEATHER_ALIASES.items():
        if any(variant in text for variant in variants):
            return canonical
    return None


def derive_effective_weather(preferences, temperature=None, weather_condition=None):
    requested = normalize(preferences.get("weather"))
    if requested in {"summer", "winter", "rainy"}:
        return requested

    weather_condition = normalize(weather_condition)
    if "rain" in weather_condition or "storm" in weather_condition:
        return "rainy"

    if temperature is not None:
        if temperature <= 15:
            return "winter"
        if temperature >= 30:
            return "summer"

    return "normal"


def extract_preferences(user_message, parsed_request=None):
    text = normalize(user_message)
    
    # If we have parsed_request from AI, use it
    if parsed_request and parsed_request.get("intent") in {"style_request", "outfit_request"}:
        preferences = {
            "occasion": parsed_request.get("occasion"),
            "mood": parsed_request.get("mood"),
            "weather": parsed_request.get("weather"),
            "color": parsed_request.get("color"),
            "gender": parsed_request.get("gender"),
            "style_notes": parsed_request.get("style_notes") or [],
            "avoid_repeat": bool(parsed_request.get("avoid_repeat", True)),
        }
    else:
        # Fallback to keyword extraction
        preferences = {
            "occasion": None,
            "mood": None,
            "weather": detect_requested_weather(text),
            "color": detect_requested_color(text),
            "gender": None,
            "style_notes": [],
            "avoid_repeat": True,
        }
    
    # Check for occasion keywords
    for occasion, keywords in OCCASION_KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword in text]
        if matches:
            preferences["occasion"] = occasion
            break

    # Check for mood keywords
    for mood, keywords in MOOD_KEYWORDS.items():
        matches = [keyword for keyword in keywords if keyword in text]
        if matches:
            preferences["mood"] = mood
            break

    if not preferences["gender"]:
        if any(word in text for word in ["men", "man", "male", "boys"]):
            preferences["gender"] = "men"
        elif any(word in text for word in ["women", "woman", "female", "girls"]):
            preferences["gender"] = "women"

    preferences["wants_outfit"] = message_has_style_intent(user_message, parsed_request)
    return preferences


def matches_gender(item, gender):
    item_gender = normalize(item.get("gender"))
    if item_gender in {"unisex", ""}:
        return True

    normalized_pref = normalize(gender)
    if normalized_pref == "men":
        normalized_pref = "male"
    elif normalized_pref == "women":
        normalized_pref = "female"

    if normalized_pref in {"male", "female"}:
        return item_gender == normalized_pref

    article = item_text_blob(item)
    if not gender:
        return True
    if gender == "women":
        return not any(word in article for word in ["men", "male", "boy"])
    if gender == "men":
        return not any(word in article for word in ["women", "female", "girl"])
    return True


def normalize_gender_pref(gender):
    normalized_pref = normalize(gender)
    if normalized_pref == "men":
        return "male"
    if normalized_pref == "women":
        return "female"
    return normalized_pref


def item_conflicts_with_gender_intent(item, category, gender_pref, user_message):
    gender_pref = normalize_gender_pref(gender_pref)
    if gender_pref not in {"male", "female"}:
        return False

    article = normalize(item.get("article_type"))
    text = f"{article} {item_text_blob(item)}"
    explicit_message = normalize(user_message)

    # If user explicitly asks for these pieces, do not hard-block.
    explicitly_requested = any(
        token in explicit_message
        for token in ["dress", "skirt", "heels", "heel", "feminine", "masculine"]
    )
    if explicitly_requested:
        return False

    if gender_pref == "male":
        if category == "dress":
            return True
        if any(word in text for word in ["dress", "skirt", "stiletto", "high heel", "pump"]):
            return True

    if gender_pref == "female":
        if any(word in text for word in ["men-only", "male formal suit"]):
            return True

    return False


def color_compatible(color1, color2):
    """Professional color coordination for fashion"""
    if not color1 or not color2:
        return True
    
    c1 = color1.lower()
    c2 = color2.lower()
    
    # Exact match
    if c1 == c2:
        return True
    
    # Neutral colors are compatible with everything
    neutral_colors = {"black", "white", "grey", "gray", "beige", "cream", "tan", "brown", "navy", "khaki"}
    if c1 in neutral_colors or c2 in neutral_colors:
        return True
    
    # Fashion color harmony rules
    warm_colors = {"red", "orange", "yellow", "pink", "brown", "beige", "cream"}
    cool_colors = {"blue", "green", "purple", "grey", "gray", "navy"}
    
    # Warm + Warm or Cool + Cool = Good
    if (c1 in warm_colors and c2 in warm_colors) or (c1 in cool_colors and c2 in cool_colors):
        return True
    
    # Complementary colors (basic color theory)
    complementary = {
        "red": "green", "orange": "blue", "yellow": "purple",
        "blue": "orange", "green": "red", "purple": "yellow"
    }
    
    # Allow complementary colors
    if complementary.get(c1) == c2 or complementary.get(c2) == c1:
        return True
    
    # Analogous colors (adjacent on color wheel)
    analogous = {
        "red": ["orange", "pink"], "blue": ["purple", "green"],
        "yellow": ["orange", "green"], "green": ["yellow", "blue"],
        "purple": ["blue", "pink"], "orange": ["red", "yellow"]
    }
    
    if c1 in analogous and c2 in analogous[c1]:
        return True
    
    # Family-based fallback
    f1 = COLOR_FAMILIES.get(c1)
    f2 = COLOR_FAMILIES.get(c2)
    if not f1 or not f2:
        return True
    if "neutral" in {f1, f2}:
        return True
    if f1 == f2:
        return True

    # Controlled warm/cool clash policy
    high_risk = {
        ("red", "green"),
        ("green", "red"),
        ("orange", "purple"),
        ("purple", "orange"),
        ("yellow", "pink"),
        ("pink", "yellow"),
    }
    if (c1, c2) in high_risk:
        return False
    return True


def infer_item_formality(item):
    blob = item_text_blob(item)
    article = normalize(item.get("article_type"))
    style_tags = split_tags(item.get("style_tags"))
    occasion_tags = split_tags(item.get("occasion_tags"))

    if any(word in blob for word in ["formal", "tailored", "blazer", "suit", "polished", "evening"]):
        return "formal"
    if "formal" in occasion_tags or "office" in occasion_tags:
        return "formal"
    if any(word in blob for word in ["party", "statement", "glam", "sequin", "shine"]):
        return "party"
    if "party" in occasion_tags:
        return "party"
    if any(word in article for word in ["sneaker", "hoodie", "jogger", "short"]):
        return "casual"
    if "casual" in occasion_tags or "casual" in style_tags:
        return "casual"
    return "smart"


def formality_fit_score(item, occasion):
    if not occasion:
        return 0
    level = infer_item_formality(item)
    preferred = {
        "formal": {"formal"},
        "office": {"formal", "smart"},
        "party": {"party", "smart"},
        "date": {"party", "smart"},
        "casual": {"casual", "smart"},
        "sporty": {"casual"},
    }.get(occasion, {"smart", "casual"})

    if level in preferred:
        return 10
    if level == "smart":
        return 4
    return -10


def footwear_is_appropriate(item, occasion, mood, effective_weather):
    article = normalize(item.get("article_type"))
    blob = item_text_blob(item)

    if effective_weather == "rainy" and any(word in article for word in ["heel", "sandal"]):
        return False
    if occasion in {"formal", "office"} and any(word in article for word in ["sneaker", "trainer"]):
        return False
    if occasion == "sporty" and not any(word in article for word in ["sneaker", "trainer", "sport"]):
        return False
    if mood == "comfy" and any(word in article for word in ["heel", "stiletto"]):
        return False
    if mood == "classy" and any(word in article for word in ["flipflop", "sports sandal"]):
        return False
    if any(word in blob for word in ["damaged", "worn out", "dirty"]):
        return False
    return True


def footwear_matches_outfit(footwear, outfit, occasion=None):
    if not footwear:
        return True

    shoe_article = normalize(footwear.get("article_type"))
    bottom = outfit.get("bottom")
    dress = outfit.get("dress")

    if bottom:
        bottom_article = normalize(bottom.get("article_type"))

        # Hard mismatch rules
        if any(word in bottom_article for word in ["short", "shorts", "jogger"]):
            if any(word in shoe_article for word in ["heel", "pump", "stiletto"]):
                return False

        if any(word in bottom_article for word in ["trouser", "pant", "slack", "skirt"]):
            if occasion in {"formal", "office"} and any(word in shoe_article for word in ["sneaker", "trainer"]):
                return False

    if dress:
        dress_article = normalize(dress.get("article_type"))
        if "dress" in dress_article and occasion in {"formal", "office"}:
            if any(word in shoe_article for word in ["flipflop", "sports sandal", "trainer"]):
                return False

    return True


def outfit_structure_is_valid(outfit, preferences):
    occasion = preferences.get("occasion")
    mood = preferences.get("mood")

    upper = outfit.get("upper")
    bottom = outfit.get("bottom")
    footwear = outfit.get("footwear")

    if upper and bottom:
        upper_article = normalize(upper.get("article_type"))
        bottom_article = normalize(bottom.get("article_type"))

        # Occasion sanity checks
        if occasion in {"formal", "office"}:
            if any(word in upper_article for word in ["hoodie", "sweatshirt", "tank"]):
                return False
            if any(word in bottom_article for word in ["short", "shorts"]):
                return False

        if occasion == "party" and any(word in bottom_article for word in ["track", "jogger"]):
            return False

    if footwear:
        if not footwear_matches_outfit(footwear, outfit, occasion):
            return False
        if mood == "classy" and any(word in normalize(footwear.get("article_type")) for word in ["flipflop", "sports sandal"]):
            return False

    return True


def weather_penalty(item, effective_weather, temperature=None):
    article = normalize(item.get("article_type"))
    season_tags = split_tags(item.get("season_tags"))
    style_tags = split_tags(item.get("style_tags"))
    penalty = 0

    expected_tags = SEASON_TAG_MAP.get(effective_weather, set())
    if season_tags:
        if season_tags & expected_tags:
            penalty += 4
        elif effective_weather == "winter" and "summer" in season_tags:
            penalty -= 5
        elif effective_weather == "summer" and "winter" in season_tags:
            penalty -= 5

    if effective_weather == "winter":
        if "short" in article or "sandal" in article:
            penalty -= 6
        if any(layer in article for layer in ["coat", "jacket", "hoodie", "sweater", "boot"]):
            penalty += 4
        if "cozy" in style_tags or "layering" in style_tags:
            penalty += 2

    if effective_weather == "summer":
        if any(layer in article for layer in ["coat", "jacket", "hoodie", "sweater", "boot"]):
            penalty -= 5
        if "short" in article or "sandal" in article or "dress" in article:
            penalty += 3
        if "breathable" in style_tags or "lightweight" in style_tags:
            penalty += 2

    if effective_weather == "rainy":
        if "sandal" in article or "heel" in article:
            penalty -= 6
        if "boot" in article or "jacket" in article:
            penalty += 3

    if temperature is not None and temperature < 12 and "dress" in article:
        penalty -= 2

    return penalty


def is_weather_appropriate(item, category, effective_weather, temperature=None):
    article = normalize(item.get("article_type"))
    season_tags = split_tags(item.get("season_tags"))

    if effective_weather == "winter":
        if category == "footwear" and "sandal" in article:
            return False
        if category == "bottom" and "short" in article:
            return False
        if category == "dress" and temperature is not None and temperature < 12:
            return False
        if season_tags and "summer" in season_tags and "winter" not in season_tags and "all-season" not in season_tags:
            return False

    if effective_weather == "summer":
        if category == "outer" and not any(light in article for light in ["blazer", "cardigan"]):
            return False
        if category == "footwear" and "boot" in article and temperature is not None and temperature >= 30:
            return False
        if season_tags and "winter" in season_tags and "summer" not in season_tags and "all-season" not in season_tags:
            return False

    if effective_weather == "rainy":
        if category == "footwear" and ("sandal" in article or "heel" in article):
            return False
        if category == "dress" and temperature is not None and temperature < 20:
            return False

    if temperature is not None:
        if temperature >= 32 and any(heavy in article for heavy in ["coat", "jacket", "hoodie", "sweater"]):
            return False
        if temperature <= 10 and category == "footwear" and "heel" in article:
            return False

    return True


def score_item(item, category, preferences, effective_weather, temperature, last_outfit_ids, used_ids):
    """Professional scoring system for fashion items"""
    score = 0
    
    # Base score for item quality
    score += 10
    
    # Weather appropriateness (higher weight)
    if is_weather_appropriate(item, category, effective_weather, temperature):
        score += 25
    else:
        score -= 15  # Penalty for weather-inappropriate items
    
    # Color coordination bonus
    color = item.get("color", "").lower()
    preferred_color = normalize(preferences.get("color"))
    if color in NEUTRAL_COLORS:
        score += 15  # Neutral colors are versatile
    elif color in ["black", "white", "navy"]:
        score += 12  # Classic colors
    if preferred_color and preferred_color != "unknown":
        if preferred_color in color:
            score += 22
        else:
            score -= 4
    
    # Category-specific enhancements
    article_type = item.get("article_type", "").lower()
    if category == "upper" and article_type in ["blazer", "jacket", "coat"]:
        score += 20  # Structured pieces are premium
    elif category == "bottom" and article_type in ["trousers", "pants", "skirt"]:
        score += 15  # Well-tailored bottoms
    elif category == "dress" and article_type in ["cocktail dress", "evening dress"]:
        score += 25  # Special occasion dresses
    elif category == "outer" and effective_weather in ["winter", "rainy"]:
        score += 30  # Weather protection is crucial
    
    # Avoid repetition penalty
    if last_outfit_ids and item.get("id") in last_outfit_ids.values():
        if preferences.get("avoid_repeat", True):
            score -= 20  # Avoid recent repeats
        else:
            score -= 4
    
    # Used items penalty
    if used_ids and item.get("id") in used_ids:
        score -= 50  # Don't reuse items in same outfit
    
    # Occasion alignment bonus
    item_blob = item_text_blob(item)
    main_category = normalize(item.get("main_category"))
    occasion = preferences.get("occasion")
    if occasion:
        if occasion == "formal" and any(word in item_blob for word in ["blazer", "tailored", "formal", "polished", "suit"]):
            score += 20  # Formal-appropriate categories
        elif occasion == "party" and (
            color in ["black", "red", "metallic"] or any(word in item_blob for word in ["statement", "party", "shine"])
        ):
            score += 15  # Party-friendly colors
        elif occasion == "date" and color in ["pink", "red", "black", "navy"]:
            score += 15  # Romantic colors
        elif occasion == "casual" and main_category in {"apparel", "footwear"}:
            score += 10  # Casual-appropriate
        score += formality_fit_score(item, occasion)
    
    # Mood alignment bonus
    mood = preferences.get("mood")
    if mood:
        if mood == "classy" and color in NEUTRAL_COLORS:
            score += 15  # Classy neutral palette
        elif mood == "bold" and color in ["red", "yellow", "orange", "pink"]:
            score += 15  # Bold color choices
        elif mood == "comfy" and article_type in ["t-shirt", "sweater", "jeans"]:
            score += 15  # Comfortable materials

    if category == "footwear":
        if footwear_is_appropriate(item, occasion, mood, effective_weather):
            score += 12
        else:
            score -= 25
    
    score += metadata_match_score(
        item=item,
        preferences=preferences,
        effective_weather=effective_weather,
        temperature=temperature,
        category=category,
        last_outfit_ids=last_outfit_ids,
    )

    return score


def metadata_match_score(
    item,
    preferences,
    effective_weather="normal",
    temperature=None,
    category=None,
    last_outfit_ids=None,
):
    blob = item_text_blob(item)
    style_tags = split_tags(item.get("style_tags"))
    occasion_tags = split_tags(item.get("occasion_tags"))
    fit = normalize(item.get("fit"))
    material = normalize(item.get("material"))
    score = 0

    occasion = preferences.get("occasion")
    if occasion:
        keywords = OCCASION_KEYWORDS.get(occasion, set())
        if occasion in occasion_tags:
            score += 5
        if any(keyword in blob for keyword in keywords):
            score += 3

    mood = preferences.get("mood")
    if mood:
        keywords = MOOD_KEYWORDS.get(mood, set())
        if mood in style_tags:
            score += 4
        if any(keyword in blob for keyword in keywords):
            score += 2

    for note in preferences.get("style_notes", []):
        if note in blob:
            score += 2

    if mood == "comfy" and fit in {"relaxed", "oversized", "regular"}:
        score += 2
    if mood == "classy" and material in {"linen", "wool", "silk", "cotton"}:
        score += 1.5
    if mood == "bold" and any(word in blob for word in ["statement", "edgy", "dramatic"]):
        score += 2

    score += weather_penalty(item, effective_weather, temperature)

    if category and last_outfit_ids and item.get("id") == last_outfit_ids.get(category):
        score -= 3 if preferences.get("avoid_repeat", True) else 0.5

    return score


def pick_best_item(items, category, preferences, effective_weather, temperature, last_outfit_ids, used_ids):
    style_notes = set(preferences.get("style_notes", []))
    preferred_gender = preferences.get("gender")
    user_message = preferences.get("_user_message", "")

    candidates = []
    for item in items:
        if item.get("id") in used_ids:
            continue
        if preferred_gender and not matches_gender(item, preferred_gender):
            continue
        if item_conflicts_with_gender_intent(item, category, preferred_gender, user_message):
            continue

        article = normalize(item.get("article_type"))
        fit = normalize(item.get("fit"))
        blob = item_text_blob(item)

        if "no_heels" in style_notes and category == "footwear":
            if any(word in article for word in ["heel", "pump", "stiletto"]):
                continue
        if "no_dress" in style_notes and category == "dress":
            continue
        if "oversized" in style_notes and category in {"upper", "outer"}:
            if fit and fit not in {"oversized", "relaxed"}:
                continue
        if "layered" in style_notes and category == "outer":
            if not any(word in blob for word in ["jacket", "coat", "blazer", "cardigan", "layer"]):
                continue

        candidates.append(item)

    if not candidates:
        return None

    weather_safe = [
        item for item in candidates
        if is_weather_appropriate(item, category, effective_weather, temperature)
    ]
    if weather_safe:
        candidates = weather_safe

    ranked = sorted(
        candidates,
        key=lambda item: score_item(item, category, preferences, effective_weather, temperature, last_outfit_ids, used_ids),
        reverse=True,
    )
    return ranked[0]


def create_partial_outfit(categories, missing_pieces, preferences, effective_weather):
    """Create a partial outfit with available pieces"""
    partial = {}
    used_ids = set()
    
    # Try to create upper + bottom if available
    if categories["upper"] and categories["bottom"]:
        upper = pick_best_item(
            categories["upper"], "upper", preferences, effective_weather, None, None, used_ids
        )
        bottom = pick_best_item(
            categories["bottom"], "bottom", preferences, effective_weather, None, None, used_ids
        )
        
        if upper and bottom and color_compatible(upper.get("color"), bottom.get("color")):
            partial["upper"] = upper
            partial["bottom"] = bottom
            used_ids.update({upper["id"], bottom["id"]})
    
    # Try to add footwear if available
    if categories["footwear"]:
        footwear = pick_best_item(
            categories["footwear"], "footwear", preferences, effective_weather, None, None, used_ids
        )
        if footwear:
            partial["footwear"] = footwear
            used_ids.add(footwear["id"])
    
    # Try to add dress if available and no upper/bottom
    if not partial and categories["dress"]:
        dress = pick_best_item(
            categories["dress"], "dress", preferences, effective_weather, None, None, used_ids
        )
        if dress:
            partial["dress"] = dress
            used_ids.add(dress["id"])
    
    # Try to add accessories if available
    if categories["accessory"]:
        accessory = pick_best_item(
            categories["accessory"], "accessory", preferences, effective_weather, None, None, used_ids
        )
        if accessory and random.random() > 0.5:
            partial["accessory"] = accessory
    
    return partial if len(partial) >= 2 else None


def analyze_wardrobe_gaps(categories, preferences, effective_weather):
    """Analyze what pieces are missing from the wardrobe for a complete outfit"""
    missing = []
    
    # Check essential pieces
    if not categories["upper"] and not categories["dress"]:
        missing.append("upper body")
    if not categories["bottom"] and not categories["dress"]:
        missing.append("lower body")
    if not categories["footwear"]:
        missing.append("footwear")
    
    # Check weather-specific needs
    if effective_weather == "winter" and not categories["outer"]:
        missing.append("outerwear for cold weather")
    elif effective_weather == "rainy" and not categories["outer"]:
        missing.append("weather-appropriate outerwear")
    
    # Check occasion-specific needs
    occasion = preferences.get("occasion")
    if occasion in {"formal", "office"} and not categories["outer"]:
        missing.append("formal outerwear")
    elif occasion == "party" and not categories.get("accessory"):
        missing.append("accessories for special occasions")
    
    return missing


def categorize_items(items):
    categories = {
        "upper": [],
        "outer": [],
        "bottom": [],
        "dress": [],
        "footwear": [],
        "accessory": [],
    }

    for item in items:
        category = infer_item_category(item)
        if category:
            categories[category].append(item)

    return categories


def should_use_dress(user_message, categories, preferences, effective_weather, temperature):
    style_notes = set(preferences.get("style_notes", []))
    if "no_dress" in style_notes or "no dress" in normalize(user_message):
        return False
    if normalize_gender_pref(preferences.get("gender")) == "male" and "dress" not in normalize(user_message):
        return False

    wants_dress = bool(categories["dress"]) and (
        preferences.get("occasion") in {"party", "date"}
        or preferences.get("mood") == "cute"
        or "dress" in normalize(user_message)
    )

    if effective_weather in {"winter", "rainy"}:
        wants_dress = False

    if temperature is not None and temperature < 18:
        wants_dress = False

    if categories["upper"] and categories["bottom"] and preferences.get("occasion") not in {"party", "date"}:
        wants_dress = False

    return wants_dress


def build_outfit(user_message, items, temperature=None, weather_condition=None, last_outfit_ids=None, parsed_request=None):
    print(f"BUILD_OUTFIT DEBUG: Starting build with {len(items)} items")
    preferences = extract_preferences(user_message, parsed_request)
    preferences["_user_message"] = user_message
    print(f"BUILD_OUTFIT DEBUG: Preferences extracted: {preferences}")

    if not preferences["wants_outfit"]:
        print("BUILD_OUTFIT DEBUG: No outfit wanted, returning NO_INTENT")
        return "NO_INTENT", preferences, derive_effective_weather(preferences, temperature, weather_condition)

    if not items:
        print("BUILD_OUTFIT DEBUG: No items available")
        return None, preferences, derive_effective_weather(preferences, temperature, weather_condition)

    effective_weather = derive_effective_weather(preferences, temperature, weather_condition)
    categories = categorize_items(items)
    print(f"BUILD_OUTFIT DEBUG: Categories: {[(k, len(v)) for k, v in categories.items()]}")
    
    # Check wardrobe limitations
    missing_pieces = analyze_wardrobe_gaps(categories, preferences, effective_weather)
    print(f"BUILD_OUTFIT DEBUG: Missing pieces: {missing_pieces}")
    
    if missing_pieces and len(missing_pieces) > 2:
        print("BUILD_OUTFIT DEBUG: Too many missing pieces, returning missing_pieces")
        # Too many missing pieces for a complete outfit
        return {"missing_pieces": missing_pieces}, preferences, effective_weather
    
    used_ids = set()
    outfit = {}
    build_attempts = 0
    max_attempts = 3
    
    while build_attempts < max_attempts:
        build_attempts += 1
        outfit.clear()
        used_ids.clear()
        style_notes = set(preferences.get("style_notes", []))
        
        if should_use_dress(user_message, categories, preferences, effective_weather, temperature):
            dress = pick_best_item(
                categories["dress"], "dress", preferences, effective_weather, temperature, last_outfit_ids, used_ids
            )
            if dress:
                outfit["dress"] = dress
                used_ids.add(dress["id"])

        if "dress" not in outfit:
            upper = pick_best_item(
                categories["upper"], "upper", preferences, effective_weather, temperature, last_outfit_ids, used_ids
            )
            bottom = pick_best_item(
                categories["bottom"], "bottom", preferences, effective_weather, temperature, last_outfit_ids, used_ids
            )

            if not upper or not bottom:
                if build_attempts == max_attempts:
                    # Final attempt failed, return missing pieces info
                    if not upper and not bottom:
                        return {"missing_pieces": ["upper body", "lower body"]}, preferences, effective_weather
                    elif not upper:
                        return {"missing_pieces": ["upper body"]}, preferences, effective_weather
                    else:
                        return {"missing_pieces": ["lower body"]}, preferences, effective_weather
                continue

            if not color_compatible(upper.get("color"), bottom.get("color")):
                sorted_bottoms = sorted(
                    categories["bottom"],
                    key=lambda item: score_item(item, "bottom", preferences, effective_weather, temperature, last_outfit_ids, used_ids),
                    reverse=True,
                )
                replacement_found = False
                for candidate in sorted_bottoms:
                    if candidate["id"] != upper["id"] and color_compatible(upper.get("color"), candidate.get("color")):
                        bottom = candidate
                        replacement_found = True
                        break
                if not replacement_found:
                    if build_attempts == max_attempts:
                        return {"missing_pieces": ["color-compatible lower body"]}, preferences, effective_weather
                    continue

            if "monochrome" in style_notes:
                upper_color = normalize(upper.get("color"))
                same_tone_bottom = next(
                    (
                        candidate
                        for candidate in sorted(
                            categories["bottom"],
                            key=lambda item: score_item(
                                item,
                                "bottom",
                                preferences,
                                effective_weather,
                                temperature,
                                last_outfit_ids,
                                used_ids,
                            ),
                            reverse=True,
                        )
                        if normalize(candidate.get("color")) == upper_color and candidate.get("id") != upper.get("id")
                    ),
                    None,
                )
                if same_tone_bottom:
                    bottom = same_tone_bottom

            outfit["upper"] = upper
            outfit["bottom"] = bottom
            used_ids.update({upper["id"], bottom["id"]})

        # Add outerwear if needed
        if (
            effective_weather in {"winter", "rainy"}
            or preferences.get("occasion") in {"formal", "office"}
            or "layered" in style_notes
        ):
            outer = pick_best_item(
                categories["outer"], "outer", preferences, effective_weather, temperature, last_outfit_ids, used_ids
            )
            if outer:
                outfit["outer"] = outer
                used_ids.add(outer["id"])

        # Add footwear
        footwear = pick_best_item(
            categories["footwear"], "footwear", preferences, effective_weather, temperature, last_outfit_ids, used_ids
        )
        if footwear and footwear_is_appropriate(
            footwear,
            preferences.get("occasion"),
            preferences.get("mood"),
            effective_weather,
        ) and footwear_matches_outfit(footwear, outfit, preferences.get("occasion")):
            outfit["footwear"] = footwear
            used_ids.add(footwear["id"])
        elif categories["footwear"]:
            # Try alternate footwear that matches the already-selected pieces.
            ranked_footwear = sorted(
                categories["footwear"],
                key=lambda item: score_item(
                    item,
                    "footwear",
                    preferences,
                    effective_weather,
                    temperature,
                    last_outfit_ids,
                    used_ids,
                ),
                reverse=True,
            )
            replacement = next(
                (
                    shoe
                    for shoe in ranked_footwear
                    if shoe.get("id") not in used_ids
                    and footwear_is_appropriate(
                        shoe,
                        preferences.get("occasion"),
                        preferences.get("mood"),
                        effective_weather,
                    )
                    and footwear_matches_outfit(
                        shoe,
                        outfit,
                        preferences.get("occasion"),
                    )
                ),
                None,
            )
            if replacement:
                outfit["footwear"] = replacement
                used_ids.add(replacement["id"])
        elif build_attempts == max_attempts and categories["footwear"]:
            return {"missing_pieces": ["occasion-appropriate footwear"]}, preferences, effective_weather

        # Add accessory occasionally
        accessory = pick_best_item(
            categories["accessory"], "accessory", preferences, effective_weather, temperature, last_outfit_ids, used_ids
        )
        if accessory and random.random() > 0.35:
            outfit["accessory"] = accessory

        if outfit:
            # Final outfit-level guardrails
            if outfit.get("upper") and outfit.get("bottom"):
                if not color_compatible(outfit["upper"].get("color"), outfit["bottom"].get("color")):
                    continue
            if outfit.get("footwear") and not footwear_is_appropriate(
                outfit["footwear"],
                preferences.get("occasion"),
                preferences.get("mood"),
                effective_weather,
            ):
                continue
            if not outfit_structure_is_valid(outfit, preferences):
                continue
            return outfit, preferences, effective_weather

    # If all attempts failed
    return None, preferences, effective_weather


def build_outfit_meta(outfit, preferences, effective_weather, temperature=None):
    if not outfit:
        return None

    occasion = preferences.get("occasion") or "any"
    mood = preferences.get("mood") or "balanced"
    color = preferences.get("color") or "open palette"
    gender = preferences.get("gender") or "unisex"

    reasons = []
    if effective_weather in {"winter", "summer", "rainy"}:
        reasons.append(f"Matched to {effective_weather} conditions.")
    if temperature is not None:
        reasons.append(f"Built around approximately {round(float(temperature))} C.")
    if outfit.get("outer") and effective_weather in {"winter", "rainy"}:
        reasons.append("Added outerwear for practical layering.")
    if outfit.get("upper") and outfit.get("bottom"):
        if color_compatible(outfit["upper"].get("color"), outfit["bottom"].get("color")):
            reasons.append("Top and bottom are color-compatible.")
    if outfit.get("footwear"):
        if footwear_is_appropriate(outfit["footwear"], occasion, mood, effective_weather):
            reasons.append("Footwear fits mood, occasion, and weather.")

    tips = []
    if mood == "classy":
        tips.append("Keep accessories minimal and structured.")
    elif mood == "bold":
        tips.append("Use one statement piece and keep the rest clean.")
    elif mood == "comfy":
        tips.append("Prioritize soft layers and relaxed silhouettes.")
    else:
        tips.append("Balance proportions for a cleaner silhouette.")

    if effective_weather == "rainy":
        tips.append("Prefer water-friendly footwear and avoid delicate fabrics.")
    elif effective_weather == "summer":
        tips.append("Keep fabrics breathable and avoid heavy layering.")
    elif effective_weather == "winter":
        tips.append("Use thermal-friendly layers and closed footwear.")

    return {
        "weather": effective_weather,
        "temperature": temperature,
        "occasion": occasion,
        "mood": mood,
        "color": color,
        "gender": gender,
        "reasons": reasons[:4],
        "tips": tips[:3],
    }
