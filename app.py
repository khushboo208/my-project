import json
import os
import sqlite3
from functools import wraps

import requests
from flask import Flask, jsonify, redirect, render_template, request, session, url_for
from flask_login import LoginManager, current_user, login_required
from werkzeug.utils import secure_filename

from auth.auth import auth, google_bp
from env_loader import load_env_file
from item_analyzer import analyze_clothing_item, fallback_analysis
from models import SavedOutfit, User, db, ensure_user_columns
from openai_stylist import analyze_style_request
from wardrobe_db import init_db
from weekly_engine import build_weekly_plan

os.environ["OAUTHLIB_INSECURE_TRANSPORT"] = "1"
load_env_file()

app = Flask(__name__)

app.config["SECRET_KEY"] = "ai_wardrobe_secret"
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///users.db"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
os.makedirs(app.instance_path, exist_ok=True)

UPLOAD_FOLDER = os.path.join(os.getcwd(), "static", "uploads")
app.config["UPLOAD_FOLDER"] = "static/uploads"
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

db.init_app(app)
with app.app_context():
    db_file_name = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    unified_db_path = os.path.join(app.instance_path, db_file_name)
    legacy_wardrobe_path = os.path.join(os.getcwd(), "wardrobe.db")
    init_db(db_path=unified_db_path, legacy_path=legacy_wardrobe_path)
    db.create_all()
    ensure_user_columns()

login_manager = LoginManager()
login_manager.login_view = "auth.login"
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


app.register_blueprint(auth)
app.register_blueprint(google_bp, url_prefix="/login")


def fetch_user_items():
    conn = sqlite3.connect(get_unified_db_path())
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM wardrobe WHERE user_id = ?", (current_user.id,))
    rows = cursor.fetchall()
    conn.close()
    print(f"FETCH_ITEMS DEBUG: Found {len(rows)} items for user {current_user.id}")
    return [dict(row) for row in rows]


def live_location_enabled():
    return bool(getattr(current_user, "live_location_enabled", False))


def get_unified_db_path():
    db_file_name = app.config["SQLALCHEMY_DATABASE_URI"].replace("sqlite:///", "")
    if os.path.isabs(db_file_name):
        return db_file_name
    return os.path.join(app.instance_path, db_file_name)


def admin_required(view_func):
    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not current_user.is_authenticated:
            return redirect(url_for("auth.login"))
        if not getattr(current_user, "is_admin", False):
            return redirect(url_for("dashboard"))
        return view_func(*args, **kwargs)

    return wrapped


def build_request_signature(user_message, parsed_request):
    parsed_request = parsed_request or {}
    parts = [
        (parsed_request.get("intent") or "").strip().lower(),
        (parsed_request.get("occasion") or "").strip().lower(),
        (parsed_request.get("mood") or "").strip().lower(),
        (parsed_request.get("weather") or "").strip().lower(),
        (parsed_request.get("color") or "").strip().lower(),
        (parsed_request.get("gender") or "").strip().lower(),
        (user_message or "").strip().lower(),
    ]
    return "|".join(parts)


def merge_style_profile(parsed_request, style_profile):
    merged = dict(parsed_request or {})
    style_profile = style_profile or {}
    for key in ["occasion", "mood", "weather", "color", "gender"]:
        if not merged.get(key) and style_profile.get(key):
            merged[key] = style_profile.get(key)

    notes = list(style_profile.get("style_notes", []))
    for note in (merged.get("style_notes") or []):
        if note and note not in notes:
            notes.append(note)
    merged["style_notes"] = notes
    return merged


def update_style_profile(style_profile, parsed_request):
    profile = dict(style_profile or {})
    for key in ["occasion", "mood", "weather", "color", "gender"]:
        value = (parsed_request or {}).get(key)
        if value:
            profile[key] = value

    notes = list(profile.get("style_notes", []))
    for note in ((parsed_request or {}).get("style_notes") or []):
        if note and note not in notes:
            notes.append(note)
    profile["style_notes"] = notes
    return profile


def build_follow_up_question(preferences):
    missing = []
    if not preferences.get("occasion"):
        missing.append("occasion")
    if not preferences.get("mood"):
        missing.append("mood")
    if not preferences.get("color"):
        missing.append("color")

    if not missing:
        return "If you want, I can generate an alternate with a different vibe."
    if len(missing) == 1:
        return f"Quick follow-up: what {missing[0]} do you want?"
    return f"Quick follow-up: tell me your {missing[0]} and {missing[1]} for a sharper look."


def outfit_to_payload(outfit):
    payload = {}
    for key, item in (outfit or {}).items():
        if not item:
            continue
        payload[key] = {
            "id": item.get("id"),
            "article_type": item.get("article_type"),
            "color": item.get("color"),
            "image_path": item.get("image_path"),
        }
    return payload


def hydrate_outfit_from_ids(last_outfit_ids, items):
    item_by_id = {}
    for item in items:
        try:
            item_by_id[int(item.get("id"))] = item
        except (TypeError, ValueError):
            continue

    hydrated = {}
    for slot, item_id in (last_outfit_ids or {}).items():
        try:
            item_id = int(item_id)
        except (TypeError, ValueError):
            continue
        if item_id in item_by_id:
            hydrated[slot] = item_by_id[item_id]
    return hydrated


def normalize_item_id(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


@app.route("/")
def home():
    return render_template("home.html")


@app.route("/dashboard")
@login_required
def dashboard():
    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM wardrobe WHERE user_id = ?", (current_user.id,))
    item_count = cursor.fetchone()[0]
    conn.close()
    show_intro = bool(session.pop("show_dashboard_intro", False))
    has_admin = User.query.filter_by(is_admin=True).first() is not None

    return render_template(
        "dashboard.html",
        item_count=item_count,
        live_location_enabled=live_location_enabled(),
        show_intro=show_intro,
        can_bootstrap_admin=(not has_admin and current_user.is_authenticated),
    )


@app.route("/profile")
@login_required
def profile():
    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM wardrobe WHERE user_id = ?", (current_user.id,))
    item_count = cursor.fetchone()[0]
    conn.close()

    return render_template(
        "profile.html",
        user=current_user,
        item_count=item_count,
        live_location_enabled=live_location_enabled(),
    )


@app.route("/admin/users")
@login_required
@admin_required
def admin_users():
    query = (request.args.get("q") or "").strip().lower()
    users = User.query.order_by(User.id.desc()).all()

    if query:
        users = [
            user
            for user in users
            if query in (user.name or "").lower()
            or query in (user.email or "").lower()
            or query in (user.provider or "").lower()
        ]

    wardrobe_counts = {}
    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, COUNT(*) FROM wardrobe GROUP BY user_id")
    for user_id, count in cursor.fetchall():
        wardrobe_counts[user_id] = count
    conn.close()

    outfit_counts = {}
    for saved in SavedOutfit.query.all():
        outfit_counts[saved.user_id] = outfit_counts.get(saved.user_id, 0) + 1

    return render_template(
        "admin_users.html",
        users=users,
        query=query,
        wardrobe_counts=wardrobe_counts,
        outfit_counts=outfit_counts,
    )


@app.route("/admin/bootstrap", methods=["POST"])
@login_required
def admin_bootstrap():
    already_has_admin = User.query.filter_by(is_admin=True).first()
    if already_has_admin:
        return redirect(url_for("dashboard"))

    current_user.is_admin = True
    db.session.commit()
    return redirect(url_for("admin_users"))


@app.route("/admin/users/<int:user_id>/toggle-admin", methods=["POST"])
@login_required
@admin_required
def admin_toggle_user_role(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        return redirect(url_for("admin_users", q=request.args.get("q", "")))
    if target.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return redirect(url_for("admin_users", q=request.args.get("q", "")))

    target.is_admin = not bool(target.is_admin)
    db.session.commit()
    return redirect(url_for("admin_users", q=request.args.get("q", "")))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@login_required
@admin_required
def admin_delete_user(user_id):
    target = User.query.get_or_404(user_id)
    if target.id == current_user.id:
        return redirect(url_for("admin_users", q=request.args.get("q", "")))
    if target.is_admin:
        admin_count = User.query.filter_by(is_admin=True).count()
        if admin_count <= 1:
            return redirect(url_for("admin_users", q=request.args.get("q", "")))

    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute("SELECT image_path FROM wardrobe WHERE user_id = ?", (target.id,))
    image_rows = cursor.fetchall()
    cursor.execute("DELETE FROM wardrobe WHERE user_id = ?", (target.id,))
    conn.commit()
    conn.close()

    for row in image_rows:
        image_path = row[0] or ""
        abs_path = os.path.join(os.getcwd(), image_path.replace("/", os.sep))
        try:
            if os.path.exists(abs_path):
                os.remove(abs_path)
        except OSError:
            pass

    SavedOutfit.query.filter_by(user_id=target.id).delete()
    db.session.delete(target)
    db.session.commit()

    return redirect(url_for("admin_users", q=request.args.get("q", "")))


@app.route("/toggle-live-location", methods=["POST"])
@login_required
def toggle_live_location():
    data = request.get_json() or {}
    enabled = bool(data.get("enabled"))

    current_user.live_location_enabled = enabled
    db.session.commit()

    if not enabled:
        session.pop("temperature", None)
        session.pop("weather_condition", None)
        session.pop("weather_tag", None)
        session.modified = True

    return jsonify({"success": True, "enabled": enabled})


@app.route("/update-location", methods=["POST"])
@login_required
def update_location():
    if not live_location_enabled():
        return jsonify({"error": "Live location is disabled"}), 403

    data = request.get_json() or {}
    latitude = data.get("latitude")
    longitude = data.get("longitude")

    if latitude is None or longitude is None:
        return jsonify({"error": "Missing location"}), 400

    try:
        api_key = os.getenv("OPENWEATHER_API_KEY", "cdf703159998a2e871e2cac808774baa")
        url = (
            "https://api.openweathermap.org/data/2.5/weather"
            f"?lat={latitude}&lon={longitude}&appid={api_key}&units=metric"
        )
        response = requests.get(url, timeout=10)
        weather_data = response.json()

        temperature = weather_data["main"]["temp"]
        weather_condition = weather_data["weather"][0]["main"].lower()

        if temperature < 15:
            detected_weather = "winter"
        elif temperature > 28:
            detected_weather = "summer"
        elif "rain" in weather_condition:
            detected_weather = "rainy"
        else:
            detected_weather = "normal"

        session["temperature"] = temperature
        session["weather_condition"] = weather_condition
        session["weather_tag"] = detected_weather
        session.modified = True

        return jsonify({"status": "Location updated"})
    except requests.exceptions.RequestException as e:
        print(f"Weather API error: {e}")
        return jsonify({"error": f"Weather service unavailable: {str(e)}"}), 500
    except Exception as e:
        print(f"Location update error: {e}")
        return jsonify({"error": f"Location update failed: {str(e)}"}), 500


@app.route("/generate-outfit")
@login_required
def generate_outfit():
    from outfit_engine import build_outfit

    items = fetch_user_items()
    if not items:
        return render_template(
            "generate_outfit.html",
            outfit=None,
            temperature=session.get("temperature"),
            weather=session.get("weather_condition") or session.get("weather_tag"),
            preferences={},
            generation_error="Add wardrobe items first, then generate an outfit.",
            live_location_enabled=live_location_enabled(),
        )

    temperature = session.get("temperature")
    weather_condition = session.get("weather_condition") or session.get("weather_tag")

    outfit, preferences, weather = build_outfit(
        user_message="outfit",
        items=items,
        temperature=temperature,
        weather_condition=weather_condition,
        last_outfit_ids=None,
    )

    if outfit == "NO_INTENT":
        return render_template(
            "generate_outfit.html",
            outfit=None,
            temperature=temperature,
            weather=weather_condition,
            preferences=preferences or {},
            generation_error="No styling intent detected. Try generating again.",
            live_location_enabled=live_location_enabled(),
        )

    if isinstance(outfit, dict) and "missing_pieces" in outfit:
        missing = outfit.get("missing_pieces") or []
        missing_text = ", ".join(str(piece) for piece in missing[:3]) if missing else "required pieces"
        return render_template(
            "generate_outfit.html",
            outfit=None,
            temperature=temperature,
            weather=weather_condition,
            preferences=preferences or {},
            generation_error=f"Not enough compatible wardrobe items. Missing: {missing_text}.",
            live_location_enabled=live_location_enabled(),
        )

    if not isinstance(outfit, dict) or not outfit:
        return render_template(
            "generate_outfit.html",
            outfit=None,
            temperature=temperature,
            weather=weather_condition,
            preferences=preferences or {},
            generation_error="Could not generate a complete outfit right now.",
            live_location_enabled=live_location_enabled(),
        )

    clean_outfit = {}
    for key, value in outfit.items():
        if isinstance(value, dict) and value.get("id") and value.get("image_path"):
            clean_outfit[key] = {
                "id": value["id"],
                "image_path": value["image_path"],
                "article_type": value.get("article_type", "item"),
                "color": value.get("color", "neutral"),
            }

    if not clean_outfit:
        return render_template(
            "generate_outfit.html",
            outfit=None,
            temperature=temperature,
            weather=weather_condition,
            preferences=preferences or {},
            generation_error="No displayable outfit items were returned.",
            live_location_enabled=live_location_enabled(),
        )

    return render_template(
        "generate_outfit.html",
        outfit=clean_outfit,
        temperature=temperature,
        weather=weather,
        preferences=preferences or {},
        generation_error=None,
        live_location_enabled=live_location_enabled(),
    )


@app.route("/custom-outfit", methods=["GET", "POST"])
@login_required
def custom_outfit():
    from outfit_engine import (
        build_outfit,
        build_outfit_meta,
        categorize_items,
        create_partial_outfit,
        derive_effective_weather,
    )
    from fashion_descriptions import generate_outfit_description, generate_stylist_reply
    
    print(f"CUSTOM_OUTFIT DEBUG: Request method: {request.method}")
    
    if "chat_history" not in session:
        session["chat_history"] = []
        # Add a welcome message when chat starts
        session["chat_history"].append({"sender": "bot", "message": "Hello! I'm your personal AI stylist. I'm here to help you curate perfect ensemble from your wardrobe. Tell me about the occasion, your style preferences, or the weather, and I'll create something exceptional for you!"})
    
    if request.method == "GET":
        return render_template(
            "custom_chat.html",
            chat_history=session.get("chat_history", []),
            live_location_enabled=live_location_enabled(),
        )

    if request.method == "POST":
        data = request.get_json() or {}
        user_message = (data.get("message") or "").strip()
        edit_action = (data.get("edit_action") or "").strip().lower()
        normalized_message = user_message.lower().strip()

        if not user_message and not edit_action:
            return jsonify({"error": "No message"}), 400

        if edit_action:
            return jsonify({"error": "Edit outfit is disabled for now."}), 400

        if normalized_message in {"reset style", "clear style memory", "start over"}:
            session.pop("style_profile", None)
            session.pop("request_outfit_memory", None)
            session.pop("last_outfit_ids", None)
            session.pop("last_style_prompt", None)
            bot_reply = "Style memory cleared. Tell me your occasion, mood, and color and I will start fresh."
            session["chat_history"].append({"sender": "user", "message": user_message})
            session["chat_history"].append({"sender": "bot", "message": bot_reply})
            session.modified = True
            return jsonify({"bot_reply": bot_reply, "outfit": {}, "stylist_meta": None})

        session["chat_history"].append({"sender": "user", "message": user_message})
        session["last_style_prompt"] = user_message
        session.modified = True  # Ensure session is saved

        items = fetch_user_items()
        temperature = session.get("temperature")
        weather_condition = session.get("weather_condition") or session.get("weather_tag")

        try:
            parsed_request = analyze_style_request(
                user_message=user_message,
                items=items,
                temperature=temperature,
                weather_condition=weather_condition,
                chat_history=session.get("chat_history", []),
            )
        except Exception as e:
            # Fallback to basic parsing
            parsed_request = {"intent": "style_request", "occasion": None, "mood": None}

        style_profile = session.get("style_profile", {})
        merged_request = merge_style_profile(parsed_request, style_profile)
        session["style_profile"] = update_style_profile(style_profile, merged_request)
        request_signature = build_request_signature(user_message, merged_request)
        request_outfit_memory = session.get("request_outfit_memory", {})
        repeated_request_last_outfit = request_outfit_memory.get(request_signature)
        last_outfit_ids = repeated_request_last_outfit or session.get("last_outfit_ids")

        try:
            outfit, preferences, selected_weather = build_outfit(
                user_message=user_message,
                items=items,
                temperature=temperature,
                weather_condition=weather_condition,
                last_outfit_ids=last_outfit_ids,
                parsed_request=merged_request,
            )
        except Exception as e:
            outfit = None
            preferences = {}
            selected_weather = None

        if outfit == "NO_INTENT":
            bot_reply = merged_request.get(
                "reply",
                "Tell me about the occasion, your personal style preferences, or the weather conditions, and I'll curate something exceptional from your wardrobe.",
            )
            bot_reply = f"{bot_reply} {build_follow_up_question(merged_request)}"
            session["chat_history"].append({"sender": "bot", "message": bot_reply})
            session.modified = True
            return jsonify({"bot_reply": bot_reply, "outfit": {}, "stylist_meta": None})

        # Handle missing pieces or failed outfit generation
        if isinstance(outfit, dict) and "missing_pieces" in outfit:
            missing_pieces = outfit["missing_pieces"]
            categories = categorize_items(items)
            effective_weather = selected_weather or derive_effective_weather(
                preferences,
                temperature,
                weather_condition,
            )
            
            # Try to create a partial outfit with available pieces
            partial_outfit = create_partial_outfit(categories, missing_pieces, preferences, effective_weather)
            
            if partial_outfit:
                # We can create a partial outfit
                bot_reply = generate_stylist_reply(False, preferences, selected_weather, False, missing_pieces)
                bot_reply += f" Here's what I can create: {', '.join(partial_outfit.keys()).title()}."
                
                session["chat_history"].append({"sender": "bot", "message": bot_reply})
                session.modified = True
                
                # Return partial outfit data
                partial_data = outfit_to_payload(partial_outfit)
                meta = build_outfit_meta(partial_outfit, preferences, effective_weather, temperature)
                return jsonify({"bot_reply": bot_reply, "outfit": partial_data, "stylist_meta": meta})
            else:
                # No partial outfit possible
                bot_reply = generate_stylist_reply(False, preferences, selected_weather, False, missing_pieces)
                session["chat_history"].append({"sender": "bot", "message": bot_reply})
                session.modified = True
                return jsonify({"bot_reply": bot_reply, "outfit": {}, "stylist_meta": None})

        if not outfit:
            bot_reply = generate_stylist_reply(False, preferences, selected_weather)
            if merged_request and merged_request.get("reply"):
                bot_reply = f"{bot_reply} {merged_request.get('reply')}"
            bot_reply = f"{bot_reply} {build_follow_up_question(preferences)}"
            session["chat_history"].append({"sender": "bot", "message": bot_reply})
            session.modified = True
            return jsonify({"bot_reply": bot_reply, "outfit": {}, "stylist_meta": None})

        session["last_outfit_ids"] = {key: value["id"] for key, value in outfit.items()}
        request_outfit_memory[request_signature] = session["last_outfit_ids"]
        session["request_outfit_memory"] = request_outfit_memory

        try:
            # Generate professional stylist reply
            is_alternate = bool(repeated_request_last_outfit)
            bot_reply = generate_stylist_reply(True, preferences, selected_weather, is_alternate)
            
            # Re-enable outfit description for full professional experience
            outfit_description = generate_outfit_description(outfit, preferences, selected_weather)
            bot_reply += f" {outfit_description}"
        except Exception as e:
            bot_reply = "I've curated an ensemble for you. " + " ".join([f"{item['article_type']} in {item['color']}" for key, item in outfit.items()])

        session["chat_history"].append({"sender": "bot", "message": bot_reply})
        session.modified = True  # Ensure session is saved

        outfit_data = outfit_to_payload(outfit)
        meta = build_outfit_meta(outfit, preferences, selected_weather, temperature)
        return jsonify({"bot_reply": bot_reply, "outfit": outfit_data, "stylist_meta": meta})

    return render_template(
        "custom_chat.html",
        chat_history=session.get("chat_history", []),
        live_location_enabled=live_location_enabled(),
    )


@app.route("/wardrobe")
@login_required
def wardrobe():
    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, user_id, image_path, main_category, sub_category, article_type, color, gender
        FROM wardrobe
        WHERE user_id = ?
        """,
        (current_user.id,),
    )
    items = cursor.fetchall()
    conn.close()
    return render_template("wardrobe.html", items=items)


@app.route("/delete-item/<int:item_id>", methods=["POST"])
@login_required
def delete_item(item_id):
    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute(
        "SELECT image_path FROM wardrobe WHERE id = ? AND user_id = ?",
        (item_id, current_user.id),
    )
    item = cursor.fetchone()

    if item:
        image_path = item[0]
        cursor.execute(
            "DELETE FROM wardrobe WHERE id = ? AND user_id = ?",
            (item_id, current_user.id),
        )
        conn.commit()

        abs_path = os.path.join(os.getcwd(), image_path.replace("/", os.sep))
        if os.path.exists(abs_path):
            os.remove(abs_path)

    conn.close()
    return redirect("/wardrobe")


@app.route("/favorites")
@login_required
def favorites():
    saved_outfits = (
        SavedOutfit.query.filter_by(user_id=current_user.id)
        .order_by(SavedOutfit.created_at.desc())
        .all()
    )

    for outfit in saved_outfits:
        outfit.outfit_data = json.loads(outfit.outfit_data)

    return render_template("favorites.html", saved_outfits=saved_outfits)


@app.route("/weekly-rotation")
@login_required
def weekly_rotation():
    items = fetch_user_items()
    if not items:
        return render_template(
            "weekly_rotation.html",
            outfits=[],
            live_location_enabled=live_location_enabled(),
        )

    temperature = session.get("temperature")
    weather_condition = session.get("weather_condition") or session.get("weather_tag")

    weekly_outfits = build_weekly_plan(
        items=items,
        temperature=temperature,
        weather_condition=weather_condition,
    )

    session["weekly_outfits"] = weekly_outfits
    session.modified = True

    return render_template(
        "weekly_rotation.html",
        outfits=weekly_outfits,
        live_location_enabled=live_location_enabled(),
    )
 


@app.route("/regenerate-day", methods=["POST"])
@login_required
def regenerate_day():
    data = request.get_json() or {}
    day_index = int(data.get("day_index", -1))

    items = fetch_user_items()
    if not items:
        return jsonify({"error": "Wardrobe empty"}), 400

    temperature = session.get("temperature")
    weather_condition = session.get("weather_condition") or session.get("weather_tag")

    weekly_outfits = build_weekly_plan(
        items=items,
        temperature=temperature,
        weather_condition=weather_condition,
    )

    if day_index < 0 or day_index >= len(weekly_outfits):
        return jsonify({"error": "Invalid day"}), 400

    return jsonify({
        "outfit": weekly_outfits[day_index],
        "weather": weather_condition,
    })


@app.route("/upload", methods=["GET", "POST"])
@login_required
def upload_file():
    if request.method == "POST" and "predict" in request.form:
        file = request.files.get("image")

        if not file or file.filename == "":
            return "No file selected"

        filename = secure_filename(file.filename)
        upload_folder = os.path.join("static", "uploads")
        os.makedirs(upload_folder, exist_ok=True)

        filepath = os.path.join(upload_folder, filename)
        file.save(filepath)

        analysis, analysis_error = analyze_clothing_item(filepath)
        if not analysis:
            if analysis_error and "does not look like a clothing item" in analysis_error.lower():
                try:
                    os.remove(filepath)
                except OSError:
                    pass
                return render_template(
                    "upload.html",
                    invalid_item_error=analysis_error,
                )
            analysis = fallback_analysis(filepath)

        predicted_article = analysis["article_type"]
        main_category = analysis["main_category"]
        sub_category = analysis["sub_category"]
        final_label = f"{analysis['color']} {predicted_article}"

        return render_template(
            "upload.html",
            image_filename=filename,
            predicted_color=analysis["color"],
            predicted_article=predicted_article,
            final_label=final_label,
            main_category=main_category,
            sub_category=sub_category,
            predicted_fit=analysis["fit"],
            predicted_material=analysis["material"],
            predicted_description=analysis["description"],
            predicted_gender=analysis.get("gender", "unisex"),
            predicted_seasons=", ".join(analysis["season_tags"]),
            predicted_occasions=", ".join(analysis["occasion_tags"]),
            predicted_styles=", ".join(analysis["style_tags"]),
            predicted_extra_details=json.dumps(analysis.get("extra_details", {}), indent=2),
            analysis_error=analysis_error,
        )

    return render_template("upload.html")


@app.route("/save-item", methods=["POST"])
@login_required
def save_item():
    image_path = request.form.get("image_path")
    main_category = request.form.get("main_category")
    sub_category = request.form.get("sub_category")
    article_type = request.form.get("article_type")
    color = request.form.get("color")
    fit = request.form.get("fit")
    material = request.form.get("material")
    gender = request.form.get("gender")
    season_tags = request.form.get("season_tags")
    occasion_tags = request.form.get("occasion_tags")
    style_tags = request.form.get("style_tags")
    description = request.form.get("description")
    extra_details = request.form.get("extra_details")

    if article_type:
        article_type = article_type.strip()
    if color:
        color = color.strip().lower()
    if fit:
        fit = fit.strip().lower()
    if material:
        material = material.strip().lower()
    if gender:
        gender = gender.strip().lower()
    if gender not in {"male", "female", "unisex"}:
        gender = "unisex"
    if season_tags:
        season_tags = season_tags.strip().lower()
    if occasion_tags:
        occasion_tags = occasion_tags.strip().lower()
    if style_tags:
        style_tags = style_tags.strip().lower()
    if description:
        description = description.strip()
    if extra_details:
        extra_details = extra_details.strip()

    conn = sqlite3.connect(get_unified_db_path())
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO wardrobe
        (
            user_id, image_path, main_category, sub_category, article_type, color,
            fit, material, gender, season_tags, occasion_tags, style_tags, description, extra_details
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            current_user.id,
            image_path,
            main_category,
            sub_category,
            article_type,
            color,
            fit,
            material,
            gender,
            season_tags,
            occasion_tags,
            style_tags,
            description,
            extra_details,
        ),
    )
    conn.commit()
    conn.close()

    return redirect("/wardrobe")


@app.route("/save-outfit", methods=["POST"])
def save_outfit():
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "error": "No data received"})

    if not current_user.is_authenticated:
        return jsonify({"success": False, "error": "User not logged in"})

    outfit = data.get("outfit")
    scheduled_date = data.get("scheduled_date")
    note = data.get("note")

    if not outfit:
        return jsonify({"success": False, "error": "No outfit provided"})

    new_outfit = SavedOutfit(
        user_id=current_user.id,
        outfit_data=json.dumps(outfit),
        scheduled_date=scheduled_date or None,
        note=note or None,
    )
    db.session.add(new_outfit)
    db.session.commit()

    return jsonify({"success": True})


@app.route("/delete-outfit/<int:outfit_id>", methods=["POST"])
@login_required
def delete_outfit(outfit_id):
    outfit = SavedOutfit.query.filter_by(id=outfit_id, user_id=current_user.id).first()

    if outfit:
        db.session.delete(outfit)
        db.session.commit()
        return jsonify({"success": True})

    return jsonify({"success": False})


if __name__ == "__main__":
    app.run(debug=True)
