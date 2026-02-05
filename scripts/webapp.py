# app/webapp.py

import base64
import hashlib
import secrets
from functools import wraps

import requests
from flask import Flask, request, redirect, url_for, render_template_string, jsonify, session
from .db import get_messages_with_stats, insert_message_query, get_message_stats
from .config import (
    AUTH_ENABLED,
    FLASK_SECRET_KEY,
    VK_CLIENT_ID,
    VK_CLIENT_SECRET,
    VK_REDIRECT_URI,
    ALLOWED_VK_IDS,
)
import logging

logger = logging.getLogger(__name__)

INDEX_HTML = """
<!doctype html>
<title>Broadcast demo</title>
{% if user %}
  <p>Вы вошли как {{ user['name'] }} (<a href="{{ url_for('logout') }}">выйти</a>)</p>

  <h1>Создать рассылку</h1>
  <form method="post" action="{{ url_for('create_message') }}">
    <label>Текст сообщения:</label><br>
    <textarea name="message" rows="4" cols="40"></textarea><br><br>

    <label>Время отправки (UTC):</label><br>
    <input name="message_time" placeholder="now или 2025-11-25 15:30"><br><br>

    <button type="submit">Создать</button>
  </form>

  <hr>

  <h2>Список рассылок</h2>
  <table border="1" cellpadding="4" cellspacing="0">
    <tr>
      <th>ID</th>
      <th>Текст</th>
      <th>Время</th>
      <th>Отправлено (чатов)</th>
    </tr>
    {% for row in rows %}
    <tr>
      <td>{{ row['id'] }}</td>
      <td>{{ row['message'][:40] }}</td>
      <td>{{ row['message_time'] }}</td>
      <td>{{ row['sent'] }}</td>
    </tr>
    {% endfor %}
  </table>
{% else %}
  <h1>Авторизация</h1>
  <p>Чтобы управлять рассылками, войдите через VK ID.</p>
  <a href="{{ url_for('login') }}">Войти через VK ID</a>
{% endif %}
"""


def _require_auth_config():
    missing = []
    if not FLASK_SECRET_KEY:
        missing.append("FLASK_SECRET_KEY")
    if not VK_CLIENT_ID:
        missing.append("VK_CLIENT_ID")
    if not VK_CLIENT_SECRET:
        missing.append("VK_CLIENT_SECRET")
    if not VK_REDIRECT_URI:
        missing.append("VK_REDIRECT_URI")
    if not ALLOWED_VK_IDS:
        missing.append("ALLOWED_VK_IDS")
    if missing:
        raise RuntimeError(f"Missing OAuth config values: {', '.join(missing)}")


def _base64url_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("utf-8")


def _generate_pkce_pair() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(64)
    verifier = verifier[:128]
    challenge = _base64url_encode(hashlib.sha256(verifier.encode("utf-8")).digest())
    return verifier, challenge


def _build_vk_authorize_url(state: str, code_challenge: str) -> str:
    params = {
        "scope": "vkid.personal_info,vkid.email,offline",
        "client_id": VK_CLIENT_ID,
        "redirect_uri": VK_REDIRECT_URI,
        "response_type": "code",
        "code_challenge": code_challenge,
        "code_challenge_method": "S256",
        "state": state,
    }
    query = "&".join(f"{key}={requests.utils.quote(str(value))}" for key, value in params.items())
    return f"https://id.vk.ru/authorize?{query}"


def _get_current_user() -> dict | None:
    if not AUTH_ENABLED:
        return {"vk_id": "local", "name": "локальный режим"}
    return session.get("user")


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if AUTH_ENABLED and not _get_current_user():
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def create_app() -> Flask:
    app = Flask(__name__)
    if AUTH_ENABLED:
        _require_auth_config()
        app.secret_key = FLASK_SECRET_KEY

    @app.route("/", methods=["GET"])
    @_login_required
    def index():
        rows = get_messages_with_stats()
        return render_template_string(INDEX_HTML, rows=rows, user=_get_current_user())

    @app.route("/create", methods=["POST"])
    @_login_required
    def create_message():
        message = request.form.get("message", "").strip()
        message_time = request.form.get("message_time", "").strip() or "now"
        users_group = 1  # пока хардкод

        insert_message_query(message, message_time, users_group)
        logger.info("web: created message time=%r len=%s users_group=%s", message_time, len(message), users_group)
        return redirect(url_for("index"))

    @app.route("/api/stats/<int:message_id>", methods=["GET"])
    def api_stats(message_id):
        row = get_message_stats(message_id)
        if row is None:
            return jsonify({"error": "not found"}), 404

        return jsonify({
            "id": row["id"],
            "message": row["message"],
            "message_time": row["message_time"],
            "sent": row["sent"],
            "clicks": row["clicks"],
        })

    @app.route("/login", methods=["GET"])
    def login():
        if not AUTH_ENABLED:
            return redirect(url_for("index"))
        next_path = request.args.get("next") or url_for("index")
        session["after_login"] = next_path
        state = secrets.token_urlsafe(16)
        code_verifier, code_challenge = _generate_pkce_pair()
        session["vk_state"] = state
        session["vk_code_verifier"] = code_verifier
        return redirect(_build_vk_authorize_url(state, code_challenge))

    @app.route("/auth/vk/callback", methods=["GET"])
    def vk_callback():
        if not AUTH_ENABLED:
            return redirect(url_for("index"))
        code = request.args.get("code")
        device_id = request.args.get("device_id")
        received_state = request.args.get("state")
        expected_state = session.get("vk_state")

        if not code or not device_id or not received_state:
            return "Ошибка: не хватает параметров от VK", 400
        if received_state != expected_state:
            return "Ошибка: invalid_state", 400

        code_verifier = session.get("vk_code_verifier")
        if not code_verifier:
            return "Ошибка: code_verifier утерян", 400

        token_resp = requests.post("https://id.vk.ru/oauth2/auth", data={
            "grant_type": "authorization_code",
            "client_id": VK_CLIENT_ID,
            "client_secret": VK_CLIENT_SECRET,
            "redirect_uri": VK_REDIRECT_URI,
            "code": code,
            "code_verifier": code_verifier,
            "device_id": device_id,
        }, timeout=10)

        if token_resp.status_code != 200:
            logger.error("VK Auth Error: %s", token_resp.text)
            return "Ошибка авторизации в VK", 400

        tokens = token_resp.json()
        access_token = tokens.get("access_token")
        if not access_token:
            return "Ошибка: access_token отсутствует", 400

        user_info_resp = requests.get(
            "https://api.vk.com/method/users.get",
            params={
                "access_token": access_token,
                "v": "5.241",
                "fields": "first_name,last_name,bdate,email",
            },
            timeout=10,
        )

        if user_info_resp.status_code != 200:
            logger.error("VK API Error: %s", user_info_resp.text)
            return "Ошибка получения данных пользователя", 500

        user_info = user_info_resp.json()
        if "error" in user_info:
            logger.error("VK API Error: %s", user_info["error"])
            return "Ошибка VK API", 500

        vk_user = user_info["response"][0]
        if str(vk_user["id"]) not in ALLOWED_VK_IDS:
            session.clear()
            return "Доступ запрещен", 403
        full_name = " ".join(part for part in [vk_user.get("first_name"), vk_user.get("last_name")] if part)
        session["user"] = {
            "vk_id": str(vk_user["id"]),
            "name": full_name or "пользователь",
        }

        return redirect(session.pop("after_login", url_for("index")))

    @app.route("/logout", methods=["GET"])
    def logout():
        session.clear()
        return redirect(url_for("index"))

    return app
