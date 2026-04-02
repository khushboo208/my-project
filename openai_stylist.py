import json
import os

import requests


STYLE_KEYWORDS = {
    "outfit",
    "wear",
    "style",
    "look",
    "dress me",
    "fit",
    "ensemble",
    "what should i wear",
    "what to wear",
    "curate",
    "generate",
    "create",
}

GREETING_KEYWORDS = {
    "hi",
    "hello",
    "hey",
    "good morning",
    "good afternoon",
    "good evening",
}

SMALL_TALK_KEYWORDS = {
    "how are you",
    "what can you do",
    "help",
    "thank you",
    "thanks",
    "bye",
    "goodbye",
}

ALTERNATE_KEYWORDS = {
    "another",
    "alternative",
    "different",
    "else",
    "new option",
    "change it",
    "something else",
}

OCCASION_KEYWORDS = {
    "party": {"party", "club", "night out", "celebration", "gala"},
    "formal": {"formal", "black tie", "wedding guest", "reception"},
    "office": {"office", "work", "meeting", "business", "corporate"},
    "casual": {"casual", "daily", "everyday", "weekend", "relaxed"},
    "date": {"date", "dinner date", "romantic"},
    "sporty": {"gym", "sport", "athleisure", "active"},
    "travel": {"airport", "travel", "trip", "vacation"},
}

MOOD_KEYWORDS = {
    "comfy": {"comfy", "comfort", "cozy", "relaxed"},
    "classy": {"classy", "elegant", "polished", "sophisticated"},
    "bold": {"bold", "statement", "edgy", "dramatic"},
    "cute": {"cute", "playful", "sweet"},
    "minimal": {"minimal", "simple", "clean", "understated"},
    "sporty": {"sporty", "athletic", "active"},
}

WEATHER_KEYWORDS = {
    "summer": {"summer", "hot", "humid", "warm"},
    "winter": {"winter", "cold", "chilly"},
    "rainy": {"rain", "rainy", "drizzle", "storm"},
}

COLOR_KEYWORDS = {
    "black": {"black", "charcoal"},
    "white": {"white", "ivory", "cream"},
    "blue": {"blue", "navy", "cobalt"},
    "red": {"red", "maroon", "burgundy"},
    "pink": {"pink", "rose"},
    "green": {"green", "olive"},
    "brown": {"brown", "tan", "beige", "camel"},
    "grey": {"grey", "gray", "silver"},
    "yellow": {"yellow", "mustard"},
    "purple": {"purple", "violet", "lilac"},
}

GENDER_KEYWORDS = {
    "men": {"men", "male", "boy", "masculine", "for him", "for men"},
    "women": {"women", "female", "girl", "feminine", "for her", "for women"},
}

STYLE_NOTE_PATTERNS = {
    "no_dress": {"no dress", "without dress", "dont use dress", "don't use dress"},
    "no_heels": {"no heels", "without heels", "dont use heels", "don't use heels"},
    "monochrome": {"monochrome", "same color", "single tone"},
    "layered": {"layered", "layering", "with layers"},
    "oversized": {"oversized", "loose fit", "baggy"},
}


def normalize(text):
    return (text or "").strip().lower()


def normalize_plain(text):
    cleaned = normalize(text)
    for ch in [".", ",", "!", "?", ";", ":"]:
        cleaned = cleaned.replace(ch, "")
    return cleaned.strip()


def summarize_wardrobe(items):
    summary = []
    for item in items[:30]:
        summary.append(
            {
                "id": item.get("id"),
                "article_type": item.get("article_type"),
                "color": item.get("color"),
                "main_category": item.get("main_category"),
                "sub_category": item.get("sub_category"),
                "fit": item.get("fit"),
                "style_tags": item.get("style_tags"),
            }
        )
    return summary


def keyword_match(text, choices):
    for key, variants in choices.items():
        for variant in variants:
            if variant in text:
                return key
    return None


def keyword_list(text, patterns):
    notes = []
    for note, variants in patterns.items():
        if any(variant in text for variant in variants):
            notes.append(note)
    return notes


def recent_user_text(chat_history, max_messages=5):
    if not chat_history:
        return ""
    user_messages = [msg.get("message", "") for msg in chat_history if msg.get("sender") == "user"]
    return " ".join(user_messages[-max_messages:])


def is_style_request(text):
    return any(keyword in text for keyword in STYLE_KEYWORDS)


def wants_alternate(text):
    return any(keyword in text for keyword in ALTERNATE_KEYWORDS)


def has_style_signals(text):
    return any(
        [
            keyword_match(text, OCCASION_KEYWORDS),
            keyword_match(text, MOOD_KEYWORDS),
            keyword_match(text, WEATHER_KEYWORDS),
            keyword_match(text, COLOR_KEYWORDS),
            keyword_match(text, GENDER_KEYWORDS),
            keyword_list(text, STYLE_NOTE_PATTERNS),
        ]
    )


def default_chat_reply(text):
    if any(word in text for word in GREETING_KEYWORDS):
        return "Ready to style you. Tell me the occasion, vibe, and any color preference, and I will build a look."
    if any(word in text for word in SMALL_TALK_KEYWORDS):
        return "I can build outfits from your wardrobe, suggest alternates, and adapt to weather. Tell me what look you want."
    return "Share your occasion, mood, and color preference, and I will curate an outfit from your wardrobe."


def is_pure_greeting_or_smalltalk(text):
    plain = normalize_plain(text)
    if not plain:
        return True
    if plain in GREETING_KEYWORDS:
        return True
    if plain in SMALL_TALK_KEYWORDS:
        return True
    if plain in {"yo", "sup", "hii", "heyy"}:
        return True
    return False


def build_rule_based_analysis(user_message, temperature=None, weather_condition=None, chat_history=None):
    current_text = normalize(user_message)
    plain_current_text = normalize_plain(user_message)
    context_text = normalize(recent_user_text(chat_history))
    full_text = f"{context_text} {current_text}".strip()

    if is_pure_greeting_or_smalltalk(plain_current_text) and not has_style_signals(plain_current_text):
        weather_hint = ""
        if temperature is not None:
            weather_hint = f" Current weather is around {round(float(temperature))} C."
        return {
            "intent": "chat",
            "reply": f"{default_chat_reply(plain_current_text)}{weather_hint}",
            "avoid_repeat": True,
            "style_notes": [],
        }

    intent = (
        "style_request"
        if (
            is_style_request(current_text)
            or wants_alternate(current_text)
            or has_style_signals(current_text)
            or (has_style_signals(full_text) and "?" not in current_text)
        )
        else "chat"
    )
    occasion = keyword_match(full_text, OCCASION_KEYWORDS)
    mood = keyword_match(full_text, MOOD_KEYWORDS)
    weather = keyword_match(full_text, WEATHER_KEYWORDS)
    color = keyword_match(full_text, COLOR_KEYWORDS)
    gender = keyword_match(full_text, GENDER_KEYWORDS)
    style_notes = keyword_list(full_text, STYLE_NOTE_PATTERNS)
    avoid_repeat = wants_alternate(current_text)

    if not weather:
        live_weather = normalize(weather_condition)
        if "rain" in live_weather:
            weather = "rainy"
        elif temperature is not None:
            if temperature <= 15:
                weather = "winter"
            elif temperature >= 30:
                weather = "summer"
            else:
                weather = "normal"

    if intent == "chat":
        weather_hint = ""
        if temperature is not None:
            weather_hint = f" Current weather is around {round(float(temperature))} C."
        return {
            "intent": "chat",
            "reply": f"{default_chat_reply(current_text)}{weather_hint}",
            "avoid_repeat": True,
            "style_notes": [],
        }

    if avoid_repeat and not any([occasion, mood, color]):
        reply = "Got it. I will create an alternative look with different pieces while keeping your last vibe."
    elif not occasion and not mood:
        reply = "Perfect. I will create a balanced outfit now. For better personalization, you can add occasion or mood in your next message."
    else:
        reply = "Great request. I am curating a look that matches your occasion, mood, and weather."

    return {
        "intent": "style_request",
        "occasion": occasion,
        "mood": mood,
        "weather": weather,
        "color": color,
        "gender": gender,
        "avoid_repeat": bool(avoid_repeat),
        "style_notes": style_notes,
        "reply": reply,
    }


def analyze_with_openai(user_message, items, temperature=None, weather_condition=None, chat_history=None):
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        return None, "OPENAI_API_KEY missing"
    if not api_key.startswith("sk-"):
        return None, "OPENAI_API_KEY format invalid"

    model = os.getenv("OPENAI_MODEL", "gpt-5")
    wardrobe_summary = summarize_wardrobe(items)
    recent_context = recent_user_text(chat_history)

    instructions = (
        "You are a wardrobe stylist intent parser. "
        "Return strict JSON only with keys: intent, occasion, mood, weather, color, gender, avoid_repeat, style_notes, reply. "
        "intent must be chat or style_request. "
        "occasion one of party, formal, office, casual, date, sporty, travel, or null. "
        "mood one of comfy, classy, bold, cute, minimal, sporty, or null. "
        "weather one of summer, winter, rainy, normal, or null. "
        "color a simple color word or null. "
        "gender one of men, women, or null. "
        "avoid_repeat must be boolean. style_notes must be a list of short tags. "
        "reply must be one short natural sentence."
    )

    payload = {
        "model": model,
        "input": [
            {
                "role": "system",
                "content": [{"type": "input_text", "text": instructions}],
            },
            {
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": (
                            f"User message: {user_message}\n"
                            f"Recent context: {recent_context}\n"
                            f"Weather condition: {weather_condition}\n"
                            f"Temperature: {temperature}\n"
                            f"Wardrobe sample: {json.dumps(wardrobe_summary)}"
                        ),
                    }
                ],
            },
        ],
    }

    try:
        response = requests.post(
            "https://api.openai.com/v1/responses",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=6,
        )
        if not response.ok:
            return None, f"OpenAI {response.status_code}: {response.text}"

        data = response.json()
        output_text = data.get("output_text", "").strip()
        if not output_text:
            return None, "OpenAI returned empty output"

        parsed = json.loads(output_text)
        return parsed, None
    except Exception as exc:
        return None, str(exc)


def normalize_analysis_shape(parsed, fallback):
    merged = dict(fallback)
    if not isinstance(parsed, dict):
        return merged

    merged["intent"] = parsed.get("intent") if parsed.get("intent") in {"chat", "style_request"} else merged["intent"]
    merged["occasion"] = parsed.get("occasion") or merged.get("occasion")
    merged["mood"] = parsed.get("mood") or merged.get("mood")
    merged["weather"] = parsed.get("weather") or merged.get("weather")
    merged["color"] = parsed.get("color") or merged.get("color")
    merged["gender"] = parsed.get("gender") or merged.get("gender")
    merged["reply"] = parsed.get("reply") or merged.get("reply")
    merged["avoid_repeat"] = bool(parsed.get("avoid_repeat", merged.get("avoid_repeat", True)))

    style_notes = parsed.get("style_notes")
    if isinstance(style_notes, list):
        merged["style_notes"] = [normalize(note) for note in style_notes if normalize(note)]
    elif isinstance(style_notes, str) and normalize(style_notes):
        merged["style_notes"] = [normalize(style_notes)]

    return merged


def analyze_style_request(user_message, items, temperature=None, weather_condition=None, chat_history=None):
    rule_based = build_rule_based_analysis(
        user_message=user_message,
        temperature=temperature,
        weather_condition=weather_condition,
        chat_history=chat_history,
    )

    parsed, _error = analyze_with_openai(
        user_message=user_message,
        items=items,
        temperature=temperature,
        weather_condition=weather_condition,
        chat_history=chat_history,
    )

    return normalize_analysis_shape(parsed, rule_based)
