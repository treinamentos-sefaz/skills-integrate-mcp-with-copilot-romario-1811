"""
High School Management System API

A super simple FastAPI application that allows students to view and sign up
for extracurricular activities at Mergington High School.
"""

import base64
import hashlib
import hmac
import json
import os
import secrets
import time
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

ADMIN_COOKIE_NAME = "admin_session"
ADMIN_SESSION_SECONDS = 60 * 60
PASSWORD_HASH_ITERATIONS = 600_000
ADMIN_USERS_FILE = Path(__file__).with_name("admin_users.json")


class AdminLogin(BaseModel):
    username: str
    password: str


def load_admin_users() -> dict[str, str]:
    users_file = Path(os.getenv("ADMIN_USERS_FILE", str(ADMIN_USERS_FILE)))
    try:
        users = json.loads(users_file.read_text(encoding="utf-8"))
    except FileNotFoundError as error:
        raise RuntimeError("Administrator accounts are not configured") from error
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError("Administrator account file could not be read") from error

    if not isinstance(users, list):
        raise RuntimeError("Administrator account file must contain a JSON list")

    result = {}
    for user in users:
        if (
            not isinstance(user, dict)
            or not isinstance(user.get("username"), str)
            or not user["username"].strip()
            or not isinstance(user.get("password_hash"), str)
        ):
            raise RuntimeError("Administrator account entries are invalid")
        result[user["username"]] = user["password_hash"]
    return result


def hash_password(password: str) -> str:
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("ascii"),
        PASSWORD_HASH_ITERATIONS,
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def verify_password(password: str, password_hash: str) -> bool:
    try:
        algorithm, rounds, salt, expected_hex = password_hash.split("$", 3)
        iterations = int(rounds)
        expected = bytes.fromhex(expected_hex)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= iterations <= 1_000_000:
            return False
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("ascii"), iterations
        )
    except (ValueError, UnicodeEncodeError):
        return False
    return hmac.compare_digest(actual, expected)


def get_session_secret() -> bytes:
    secret = os.getenv("ADMIN_SESSION_SECRET", "")
    if len(secret) < 32:
        raise RuntimeError("ADMIN_SESSION_SECRET must contain at least 32 characters")
    return secret.encode("utf-8")


def create_admin_session(username: str, secret: bytes) -> str:
    payload = json.dumps(
        {"username": username, "expires": int(time.time()) + ADMIN_SESSION_SECONDS},
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")
    signature = hmac.new(
        secret, encoded_payload.encode("ascii"), hashlib.sha256
    ).hexdigest()
    return f"{encoded_payload}.{signature}"


def get_session_username(token: str | None, secret: bytes) -> str | None:
    if not token:
        return None
    try:
        encoded_payload, signature = token.split(".", 1)
        expected_signature = hmac.new(
            secret, encoded_payload.encode("ascii"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected_signature):
            return None
        padding = "=" * (-len(encoded_payload) % 4)
        payload = json.loads(
            base64.urlsafe_b64decode(encoded_payload + padding).decode("utf-8")
        )
        username = payload["username"]
        expires = payload["expires"]
        if not isinstance(username, str) or not isinstance(expires, int):
            return None
        if expires <= int(time.time()):
            return None
        return username
    except (ValueError, KeyError, TypeError, UnicodeDecodeError, json.JSONDecodeError):
        return None


def require_admin(request: Request) -> str:
    try:
        users = load_admin_users()
        secret = get_session_secret()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    username = get_session_username(request.cookies.get(ADMIN_COOKIE_NAME), secret)
    if username not in users:
        raise HTTPException(status_code=401, detail="Teacher login required")
    return username


@app.get("/auth/status")
def auth_status(request: Request):
    try:
        users = load_admin_users()
        secret = get_session_secret()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    username = get_session_username(request.cookies.get(ADMIN_COOKIE_NAME), secret)
    return {"authenticated": username in users, "configured": bool(users)}


@app.post("/auth/login")
def admin_login(credentials: AdminLogin, request: Request, response: Response):
    try:
        users = load_admin_users()
        secret = get_session_secret()
    except RuntimeError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error

    password_hash = users.get(credentials.username)
    if not password_hash or not verify_password(credentials.password, password_hash):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    response.set_cookie(
        ADMIN_COOKIE_NAME,
        create_admin_session(credentials.username, secret),
        max_age=ADMIN_SESSION_SECONDS,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return {"message": "Logged in successfully"}


@app.post("/auth/logout")
def admin_logout(request: Request, response: Response):
    response.delete_cookie(
        ADMIN_COOKIE_NAME,
        httponly=True,
        secure=request.url.scheme == "https",
        samesite="lax",
        path="/",
    )
    return {"message": "Logged out successfully"}

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str, request: Request):
    """Sign up a student for an activity"""
    require_admin(request)

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str, request: Request):
    """Unregister a student from an activity"""
    require_admin(request)

    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
