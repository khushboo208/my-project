import random

# Professional fashion vocabulary
FASHION_TERMS = {
    "upper": {
        "formal": ["blouse", "button-up shirt", "elegant top", "sophisticated shirt", "refined blouse"],
        "casual": ["stylish top", "chic shirt", "fashionable tee", "trendy blouse", "modern top"],
        "party": ["statement top", "eye-catching blouse", "glamorous shirt", "show-stopping top"],
        "comfy": ["relaxed top", "comfortable shirt", "cozy blouse", "effortless top"]
    },
    "bottom": {
        "formal": ["tailored trousers", "elegant pants", "sophisticated slacks", "refined trousers"],
        "casual": ["stylish pants", "chic trousers", "fashionable bottoms", "modern slacks"],
        "party": ["statement bottoms", "eye-catching pants", "dramatic trousers"],
        "comfy": ["relaxed trousers", "comfortable pants", "effortless bottoms"]
    },
    "dress": {
        "formal": ["elegant dress", "sophisticated gown", "refined dress", "timeless piece"],
        "casual": ["chic dress", "stylish frock", "fashionable dress", "modern dress"],
        "party": ["show-stopping dress", "statement gown", "eye-catching dress", "glamorous piece"],
        "comfy": ["comfortable dress", "relaxed frock", "effortless dress"]
    },
    "outer": {
        "formal": ["tailored blazer", "elegant coat", "sophisticated jacket", "refined outerwear"],
        "casual": ["stylish jacket", "chic coat", "fashionable outerwear", "modern layer"],
        "comfy": ["cozy jacket", "comfortable coat", "relaxed outerwear"]
    },
    "footwear": {
        "formal": ["elegant shoes", "sophisticated footwear", "refined heels", "polished shoes"],
        "casual": ["stylish shoes", "chic footwear", "fashionable sneakers", "modern shoes"],
        "party": ["statement heels", "eye-catching footwear", "glamorous shoes"],
        "comfy": ["comfortable shoes", "relaxed footwear", "effortless sneakers"]
    },
    "accessory": {
        "formal": ["elegant accessory", "sophisticated piece", "refined detail", "polished accent"],
        "casual": ["stylish accessory", "chic detail", "fashionable accent", "modern piece"],
        "party": ["statement accessory", "eye-catching detail", "glamorous accent"],
        "comfy": ["subtle accessory", "comfortable piece", "effortless detail"]
    }
}

COLOR_DESCRIPTIONS = {
    "black": ["sleek black", "classic black", "sophisticated black", "timeless black", "dramatic black"],
    "white": ["crisp white", "elegant white", "clean white", "refined white", "fresh white"],
    "blue": ["rich blue", "oceanic blue", "royal blue", "serene blue", "deep blue"],
    "red": ["bold red", "passionate red", "striking red", "confident red", "vibrant red"],
    "pink": ["soft pink", "romantic pink", "delicate pink", "charming pink", "elegant pink"],
    "green": ["emerald green", "sophisticated green", "natural green", "refined green", "deep green"],
    "brown": ["warm brown", "rich brown", "earthy brown", "sophisticated brown", "classic brown"],
    "grey": ["elegant grey", "sophisticated grey", "modern grey", "refined grey", "versatile grey"],
    "navy": ["classic navy", "sophisticated navy", "timeless navy", "deep navy", "refined navy"],
    "cream": ["elegant cream", "soft cream", "refined cream", "warm cream", "sophisticated cream"],
    "beige": ["versatile beige", "warm beige", "sophisticated beige", "neutral beige", "refined beige"]
}

STYLE_PRINCIPLES = [
    "creates a balanced silhouette",
    "offers versatile styling options",
    "provides sophisticated layering",
    "delivers polished coordination",
    "ensures refined proportions",
    "achieves elegant harmony",
    "presents cohesive styling",
    "maintains tasteful balance"
]

OCCASION_SPECIFIC_COMMENTS = {
    "party": [
        "perfect for making a memorable entrance",
        "designed to turn heads with confidence",
        "ideal for celebratory occasions",
        "crafted for evening sophistication"
    ],
    "formal": [
        "exemplifies professional elegance",
        "commands respect in corporate settings",
        "maintains sophisticated standards",
        "reflects refined business acumen"
    ],
    "office": [
        "balances professionalism with style",
        "offers workplace-appropriate sophistication",
        "maintains business-casual elegance",
        "provides refined office presence"
    ],
    "casual": [
        "achieves effortless everyday style",
        "delivers relaxed sophistication",
        "offers comfortable elegance",
        "maintains casual refinement"
    ],
    "date": [
        "creates romantic elegance",
        "offers intimate sophistication",
        "perfect for special evenings",
        "exudes charming grace"
    ]
}

def generate_color_description(color):
    """Generate a sophisticated color description"""
    if not color or color == "unknown":
        return "neutral"
    
    descriptions = COLOR_DESCRIPTIONS.get(color.lower(), [color])
    return random.choice(descriptions)

def generate_item_description(item, category, occasion=None, mood=None):
    """Generate a professional description for a clothing item"""
    article_type = item.get("article_type", "piece")
    color = item.get("color", "neutral")
    
    # Determine formality level
    if occasion in ["formal", "office"]:
        formality = "formal"
    elif occasion == "party":
        formality = "party"
    elif mood == "comfy":
        formality = "comfy"
    else:
        formality = "casual"
    
    # Get fashion terms
    category_terms = FASHION_TERMS.get(category, {}).get(formality, [f"stylish {category}"])
    item_term = random.choice(category_terms)
    
    # Generate color description
    color_desc = generate_color_description(color)
    
    return f"{color_desc} {item_term}"

def generate_outfit_description(outfit, preferences=None, weather=None):
    """Generate a comprehensive, professional outfit description"""
    if not outfit:
        return "I wasn't able to curate the perfect ensemble from your current wardrobe. Consider expanding your collection with more versatile pieces."
    
    occasion = preferences.get("occasion") if preferences else None
    mood = preferences.get("mood") if preferences else None
    
    descriptions = []
    piece_descriptions = []
    
    # Generate individual piece descriptions
    for category, item in outfit.items():
        if item:
            piece_desc = generate_item_description(item, category, occasion, mood)
            piece_descriptions.append(piece_desc)
    
    # Create opening statement
    if occasion == "party":
        opening = "I've curated a show-stopping ensemble that commands attention"
    elif occasion == "formal":
        opening = "I've assembled a sophisticated presentation that embodies professional excellence"
    elif occasion == "office":
        opening = "I've designed a polished business ensemble that balances authority with style"
    elif occasion == "date":
        opening = "I've crafted an elegant composition perfect for romantic occasions"
    elif occasion == "casual":
        opening = "I've created an effortlessly chic look with refined details"
    else:
        opening = "I've curated a perfectly balanced ensemble tailored to your specifications"
    
    # Add mood context
    if mood:
        mood_context = {
            "comfy": "with luxurious comfort and ease",
            "classy": "with timeless elegance and sophistication",
            "bold": "with confident statement pieces that make an impact",
            "cute": "with charming feminine details",
            "minimal": "with clean, refined lines and understated elegance",
            "sporty": "with athletic sophistication and dynamic energy",
            "vintage": "with classic, heritage-inspired elements"
        }
        opening += f", {mood_context.get(mood, 'with perfect aesthetic balance')}"
    
    # Add weather context
    if weather:
        weather_context = {
            "winter": "perfectly suited for cooler temperatures with strategic layering",
            "summer": "ideal for warm conditions with breathable selections",
            "rainy": "weather-appropriate with practical yet stylish considerations",
            "normal": "perfectly adapted to current conditions"
        }
        opening += f", {weather_context.get(weather, 'perfectly suited to the weather')}"
    
    opening += "."
    
    # Build piece descriptions
    if len(piece_descriptions) > 1:
        if len(piece_descriptions) == 2:
            pieces_text = f"{piece_descriptions[0]} paired with {piece_descriptions[1]}"
        elif len(piece_descriptions) == 3:
            pieces_text = f"{piece_descriptions[0]}, {piece_descriptions[1]}, and {piece_descriptions[2]}"
        else:
            pieces_text = ", ".join(piece_descriptions[:-1]) + f", and {piece_descriptions[-1]}"
        
        descriptions.append(f"The ensemble features {pieces_text}.")
    else:
        descriptions.append(f"The look centers around {piece_descriptions[0]}.")
    
    # Add style principle
    principle = random.choice(STYLE_PRINCIPLES)
    descriptions.append(f"This combination {principle}.")
    
    # Add occasion-specific comment
    if occasion and occasion in OCCASION_SPECIFIC_COMMENTS:
        comment = random.choice(OCCASION_SPECIFIC_COMMENTS[occasion])
        descriptions.append(comment + ".")
    
    # Add closing statement
    closing_options = [
        "Each piece has been thoughtfully selected to create a cohesive, polished appearance.",
        "The result is a meticulously curated look that reflects refined taste.",
        "This ensemble demonstrates sophisticated styling with attention to detail.",
        "Every element works in harmony to achieve elevated style."
    ]
    descriptions.append(random.choice(closing_options))
    
    return " ".join(descriptions)

def generate_stylist_reply(outfit_success, preferences=None, weather=None, is_alternate=False, missing_pieces=None):
    """Generate a professional stylist reply with contextual awareness"""
    if missing_pieces:
        # Handle wardrobe limitations
        if len(missing_pieces) > 2:
            return (f"I'd love to create that ensemble for you, but your wardrobe is missing several essential pieces: "
                   f"{', '.join(missing_pieces[:-1])}, and {missing_pieces[-1]}. "
                   f"Consider adding these items to expand your styling options.")
        else:
            return (f"I can create a partial look, but your wardrobe is missing {', '.join(missing_pieces)}. "
                   f"Adding these pieces would allow me to craft a complete, polished ensemble.")
    
    if not outfit_success:
        return ("I wasn't able to curate the perfect ensemble from your current wardrobe. "
                "Consider expanding your collection with more versatile pieces, "
                "or let me suggest a different aesthetic direction.")
    
    if is_alternate:
        return "Here's an alternative interpretation of your requested aesthetic, offering fresh styling possibilities while maintaining the core vision."
    
    occasion = preferences.get("occasion") if preferences else None
    
    # Smart contextual replies
    replies = {
        "party": [
            "I've curated a show-stopping ensemble perfect for making an entrance.",
            "This dramatic combination ensures you'll be the center of attention.",
            "I've designed an eye-catching look that embodies celebration and confidence."
        ],
        "formal": [
            "I've crafted a sophisticated presentation that commands respect and admiration.",
            "This refined ensemble exemplifies professional excellence and timeless elegance.",
            "I've assembled a polished look that reflects authority and refined taste."
        ],
        "office": [
            "I've designed a polished business ensemble that balances professionalism with style.",
            "This sophisticated look maintains workplace standards while expressing personal style.",
            "I've curated a professional presentation that's both authoritative and elegant."
        ],
        "date": [
            "I've created an elegant composition perfect for romantic occasions.",
            "This sophisticated ensemble embodies romantic elegance and charm.",
            "I've crafted a refined look that's perfect for intimate evenings."
        ],
        "casual": [
            "I've created an effortlessly chic look with refined details.",
            "This ensemble achieves casual sophistication with elevated elements.",
            "I've curated a relaxed yet polished look perfect for everyday elegance."
        ]
    }
    
    default_replies = [
        "I've curated a perfectly balanced ensemble tailored to your specifications.",
        "This sophisticated combination reflects refined styling sensibilities.",
        "I've designed an elegant ensemble that embodies sophisticated taste."
    ]
    
    if occasion and occasion in replies:
        return random.choice(replies[occasion])
    return random.choice(default_replies)
