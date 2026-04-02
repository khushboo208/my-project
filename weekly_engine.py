import random
from collections import defaultdict, deque

import requests


def fetch_live_weather(latitude, longitude):
    try:
        url = (
            f"https://api.open-meteo.com/v1/forecast?"
            f"latitude={latitude}&longitude={longitude}"
            f"&current_weather=true"
        )
        response = requests.get(url, timeout=5)
        data = response.json()
        temperature = data["current_weather"]["temperature"]
        weather_code = data["current_weather"]["weathercode"]
        condition = map_weather_code(weather_code)
        return temperature, condition
    except Exception:
        return None, None


def map_weather_code(code):
    if code in [0, 1]:
        return "clear"
    if code in [2, 3]:
        return "cloudy"
    if code in [61, 63, 65]:
        return "rain"
    if code in [71, 73, 75]:
        return "snow"
    return "clear"


def normalize(text):
    return (text or "").lower().replace("-", "").replace(" ", "")


def normalize_gender_label(value):
    value = (value or "").strip().lower()
    if value in {"men", "male"}:
        return "male"
    if value in {"women", "female"}:
        return "female"
    if value == "unisex":
        return "unisex"
    return ""


def infer_weekly_gender_pref(items, explicit_gender=None):
    explicit = normalize_gender_label(explicit_gender)
    if explicit in {"male", "female"}:
        return explicit

    counts = {"male": 0, "female": 0}
    for item in items:
        g = normalize_gender_label(item.get("gender"))
        if g in counts:
            counts[g] += 1

    if counts["male"] == counts["female"] == 0:
        return ""
    return "male" if counts["male"] >= counts["female"] else "female"


def gender_ok(item, gender_pref):
    if not gender_pref:
        return True
    item_gender = normalize_gender_label(item.get("gender"))
    if item_gender in {"", "unisex"}:
        return True
    return item_gender == gender_pref


def derive_effective_weather(temperature=None, weather_condition=None):
    weather_condition = (weather_condition or "").lower()

    if "rain" in weather_condition or "storm" in weather_condition:
        return "rainy"
    if "snow" in weather_condition:
        return "winter"

    if temperature is not None:
        if temperature <= 15:
            return "winter"
        if temperature >= 30:
            return "summer"

    return "normal"


def weather_ok(item, category, effective_weather, temperature=None):
    article = normalize(item.get("article_type"))

    if effective_weather == "winter":
        if category == "bottom" and "short" in article:
            return False
        if category == "footwear" and "sandal" in article:
            return False
        if category == "dress" and temperature is not None and temperature < 12:
            return False

    if effective_weather == "summer":
        if category == "outer" and not any(light in article for light in ["blazer", "cardigan"]):
            return False
        if category == "footwear" and "boot" in article and temperature is not None and temperature >= 30:
            return False

    if effective_weather == "rainy":
        if category == "footwear" and ("sandal" in article or "heel" in article):
            return False
        if category == "dress" and temperature is not None and temperature < 20:
            return False

    return True


def categorize_items(items, gender_pref=""):
    categories = {
        "upper": [],
        "bottom": [],
        "dress": [],
        "footwear": [],
        "outer": [],
    }

    for item in items:
        if not gender_ok(item, gender_pref):
            continue
        article = normalize(item.get("article_type"))

        if any(x in article for x in ["tshirt", "shirt", "top", "blouse", "tee", "hoodie", "sweater"]):
            categories["upper"].append(item)
        elif any(x in article for x in ["jean", "pant", "trouser", "skirt", "short", "jogger"]):
            categories["bottom"].append(item)
        elif "dress" in article:
            categories["dress"].append(item)
        elif any(x in article for x in ["shoe", "sneaker", "heel", "boot", "sandal"]):
            categories["footwear"].append(item)
        elif any(x in article for x in ["jacket", "coat", "blazer", "hoodie", "cardigan"]):
            categories["outer"].append(item)

    return categories


def build_weekly_plan(
    items,
    gender=None,
    latitude=None,
    longitude=None,
    temperature=None,
    weather_condition=None
):
    if latitude and longitude:
        temperature, weather_condition = fetch_live_weather(latitude, longitude)

    effective_weather = derive_effective_weather(temperature, weather_condition)
    gender_pref = infer_weekly_gender_pref(items, gender)
    categories = categorize_items(items, gender_pref=gender_pref)

    usage = defaultdict(int)
    recent_items = deque(maxlen=14)
    recent_footwear = deque(maxlen=3)
    recent_by_category = {
        "upper": deque(maxlen=2),
        "bottom": deque(maxlen=2),
        "dress": deque(maxlen=3),
        "footwear": deque(maxlen=2),
        "outer": deque(maxlen=2),
    }
    used_top_bottom_pairs = set()
    used_dress_shoe_pairs = set()
    previous_outfit_signature = None
    dress_days_used = 0

    def smart_pick(category_name, avoid_list=None, extra_avoid=None):
        category_items = categories[category_name]
        if not category_items:
            return None

        avoid_list = avoid_list or []
        extra_avoid = extra_avoid or set()
        cooldown_block = set(recent_by_category.get(category_name, []))
        filtered = [
            item for item in category_items
            if item["id"] not in recent_items
            and item["id"] not in avoid_list
            and item["id"] not in cooldown_block
            and item["id"] not in extra_avoid
            and weather_ok(item, category_name, effective_weather, temperature)
        ]

        if not filtered:
            filtered = [
                item for item in category_items
                if item["id"] not in avoid_list
                and item["id"] not in extra_avoid
                and weather_ok(item, category_name, effective_weather, temperature)
            ]

        if not filtered:
            return None

        min_use = min(usage[item["id"]] for item in filtered)
        least_used = [item for item in filtered if usage[item["id"]] == min_use]
        chosen = random.choice(least_used)
        usage[chosen["id"]] += 1
        recent_items.append(chosen["id"])
        if category_name in recent_by_category:
            recent_by_category[category_name].append(chosen["id"])
        return chosen

    def compatible(top, bottom):
        if not top or not bottom:
            return False

        top_color = (top.get("color") or "").lower()
        bottom_color = (bottom.get("color") or "").lower()

        if top_color == bottom_color and top_color not in {"black", "white", "grey", "brown"}:
            return False

        if effective_weather == "winter" and "short" in normalize(bottom.get("article_type")):
            return False

        return True

    def occasion_for_day(day):
        if day == 0:
            return "formal"
        if day == 4:
            return "smart-casual"
        if day >= 5:
            return "casual"
        return "business-casual"

    weekly = []

    for day in range(7):
        outfit = {}
        occasion = occasion_for_day(day)

        use_dress = False
        if gender_pref != "male" and categories["dress"] and dress_days_used < 2:
            if effective_weather in {"winter", "rainy"}:
                use_dress = False
            elif temperature is not None and temperature < 18:
                use_dress = False
            elif not (categories["upper"] and categories["bottom"]):
                use_dress = True
            elif occasion == "casual":
                use_dress = random.random() < 0.18
            elif occasion == "business-casual":
                use_dress = random.random() < 0.08
            elif occasion == "smart-casual":
                use_dress = random.random() < 0.12

        if use_dress:
            dress_avoid = set(recent_by_category["dress"])
            dress = smart_pick("dress", extra_avoid=dress_avoid)
            shoe = smart_pick("footwear", avoid_list=list(recent_footwear))

            if dress and shoe:
                pair_key = (dress["id"], shoe["id"])
                if pair_key in used_dress_shoe_pairs:
                    alt_shoe = smart_pick(
                        "footwear",
                        avoid_list=list(recent_footwear),
                        extra_avoid={shoe["id"]},
                    )
                    if alt_shoe:
                        shoe = alt_shoe
                        pair_key = (dress["id"], shoe["id"])

                outfit["dress"] = dress
                outfit["footwear"] = shoe
                recent_footwear.append(shoe["id"])
                used_dress_shoe_pairs.add(pair_key)
                dress_days_used += 1

                if effective_weather in {"rainy", "winter"}:
                    outer = smart_pick("outer")
                    if outer:
                        outfit["outerwear"] = outer
            else:
                use_dress = False

        if not outfit:
            upper = smart_pick("upper")
            bottom = smart_pick("bottom")
            attempts = 0

            while attempts < 4 and upper and bottom and not compatible(upper, bottom):
                bottom = smart_pick("bottom")
                attempts += 1

            pair_attempts = 0
            while (
                upper
                and bottom
                and (upper["id"], bottom["id"]) in used_top_bottom_pairs
                and pair_attempts < 4
            ):
                bottom = smart_pick("bottom", extra_avoid={bottom["id"]})
                pair_attempts += 1

            shoe = smart_pick("footwear", avoid_list=list(recent_footwear))

            if not upper or not bottom:
                dress = smart_pick("dress")
                if dress:
                    outfit["dress"] = dress
                else:
                    weekly.append({})
                    continue
            else:
                outfit["upper"] = upper
                outfit["bottom"] = bottom
                used_top_bottom_pairs.add((upper["id"], bottom["id"]))

            if shoe:
                outfit["footwear"] = shoe
                recent_footwear.append(shoe["id"])

            if effective_weather in {"rainy", "winter"} or (temperature is not None and temperature < 18):
                outer = smart_pick("outer")
                if outer:
                    outfit["outerwear"] = outer

        signature = tuple(sorted([value["id"] for value in outfit.values() if value]))
        if signature == previous_outfit_signature and "bottom" in outfit:
            alternate_bottom = smart_pick("bottom", extra_avoid={outfit["bottom"]["id"]})
            if alternate_bottom:
                outfit["bottom"] = alternate_bottom
                signature = tuple(sorted([value["id"] for value in outfit.values() if value]))

        previous_outfit_signature = signature
        weekly.append(outfit)

    return weekly
