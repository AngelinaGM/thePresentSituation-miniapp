import asyncio, base64, hashlib, hmac, json, logging, secrets, time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl
from urllib.request import Request as UrlRequest, urlopen

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, HttpUrl, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Gift, Reservation, User, Wishlist, WishlistStatus

PUBLIC = Path(__file__).resolve().parent.parent / "public"
logger = logging.getLogger(__name__)


def frontend_asset_version() -> str:
    digest = hashlib.sha256()
    for asset_name in ("app.js", "style.css"):
        digest.update((PUBLIC / asset_name).read_bytes())
    return digest.hexdigest()[:12]


ASSET_VERSION = frontend_asset_version()


def mini_app_url(settings: Settings) -> str:
    base_url = settings.app_url.rstrip("/")
    separator = "&" if "?" in base_url else "?"
    return f"{base_url}{separator}v={ASSET_VERSION}"


def telegram_api(method: str, payload: dict, settings: Settings) -> None:
    request = UrlRequest(
        f"https://api.telegram.org/bot{settings.bot_token}/{method}",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Telegram {method} returned HTTP {response.status}")


async def configure_telegram_webhook() -> None:
    settings = get_settings()
    if not (settings.bot_token and settings.app_url and settings.telegram_webhook_secret):
        logger.warning("Telegram webhook was not configured: required settings are missing.")
        return
    await asyncio.to_thread(
        telegram_api,
        "setWebhook",
        {
            "url": f"{settings.app_url.rstrip('/')}/telegram/webhook",
            "secret_token": settings.telegram_webhook_secret,
        },
        settings,
    )
    await asyncio.to_thread(
        telegram_api,
        "setMyCommands",
        {
            "commands": [
                {"command": "start", "description": "Open the app"},
                {"command": "help", "description": "Learn about the app"},
            ]
        },
        settings,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        await configure_telegram_webhook()
    except Exception:
        logger.exception("Telegram webhook configuration failed.")
    yield


app = FastAPI(title="Party Wishlist", lifespan=lifespan)
app.mount("/public", StaticFiles(directory=PUBLIC), name="public")

class AuthPayload(BaseModel): initData: str
class WishlistPayload(BaseModel): title: str = Field(min_length=1, max_length=100); party_at: datetime | None = None
class GiftPayload(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    url: HttpUrl | None = None
    price: str | None = Field(None, max_length=60)
    note: str | None = Field(None, max_length=500)

    @field_validator("url", "price", "note", mode="before")
    @classmethod
    def blank_optional_fields_are_none(cls, value):
        """HTML forms send blank optional controls as empty strings."""
        return None if isinstance(value, str) and not value.strip() else value

@app.exception_handler(HTTPException)
async def errors(_, exc): return JSONResponse({"error": exc.detail}, exc.status_code)
def fail(code, msg): raise HTTPException(code, msg)
def b64e(v): return base64.urlsafe_b64encode(v).rstrip(b"=").decode()
def b64d(v): return base64.urlsafe_b64decode(v + "=" * (-len(v) % 4))
def verify(data, token):
    if not token: fail(500, "BOT_TOKEN is not configured")
    values = dict(parse_qsl(data, keep_blank_values=True)); received = values.pop("hash", None)
    check = "\n".join(f"{k}={v}" for k, v in sorted(values.items()))
    secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
    if not received or not hmac.compare_digest(received, hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()): fail(401, "Telegram signature is invalid")
    try: user, date = json.loads(values["user"]), int(values["auth_date"])
    except Exception: fail(401, "Telegram authorization is invalid")
    if not user.get("id") or time.time()-date > 86400: fail(401, "Telegram authorization has expired")
    return user
def sign(tid, s):
    payload=b64e(json.dumps({"telegram_id":tid,"exp":int(time.time()+s.session_days*86400)}).encode())
    return payload+"."+b64e(hmac.new(s.session_secret.encode(),payload.encode(),hashlib.sha256).digest())
def current_user(authorization: str|None=Header(None), db: Session=Depends(get_session), settings: Settings=Depends(get_settings)):
    try:
        payload, sig=(authorization or "").removeprefix("Bearer ").split(".")
        if not hmac.compare_digest(b64d(sig), hmac.new(settings.session_secret.encode(),payload.encode(),hashlib.sha256).digest()): raise ValueError
        data=json.loads(b64d(payload)); assert data["exp"]>time.time()
        user=db.scalar(select(User).where(User.telegram_id==data["telegram_id"])); assert user
        return user
    except Exception: fail(401, "Open the app through Telegram.")
def gift_out(g, mine=False):
    v={"id":g.id,"title":g.title,"url":g.product_url,"price":g.price_note,"note":g.comment}
    if mine: v["reservedByMe"]=True
    return v
def owner_out(w, s):
    bot=s.bot_username.removeprefix("@")
    return {"id":w.id,"title":w.title,"status":w.status.value,"partyAt":w.party_at.isoformat() if w.party_at else None,"inviteToken":w.invite_token,"inviteUrl":f"https://t.me/{bot}?startapp={w.invite_token}" if bot else "","gifts":[gift_out(g) for g in w.gifts if not g.deleted_at]}

async def send_bot_message(chat_id: int, text: str, settings: Settings, include_open_button: bool = False) -> None:
    payload = {"chat_id": chat_id, "text": text}
    if include_open_button:
        payload["reply_markup"] = {
            "inline_keyboard": [[{"text": "Open", "web_app": {"url": mini_app_url(settings)}}]]
        }
    await asyncio.to_thread(telegram_api, "sendMessage", payload, settings)

@app.post("/telegram/webhook", include_in_schema=False)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    settings: Settings = Depends(get_settings),
):
    if not settings.telegram_webhook_secret:
        fail(503, "Telegram webhook is not configured.")
    if not x_telegram_bot_api_secret_token or not hmac.compare_digest(
        x_telegram_bot_api_secret_token, settings.telegram_webhook_secret
    ):
        fail(403, "Invalid Telegram webhook secret.")
    try:
        update = await request.json()
    except json.JSONDecodeError:
        fail(400, "Invalid Telegram update.")
    message = update.get("message") if isinstance(update, dict) else None
    chat = message.get("chat") if isinstance(message, dict) else None
    text = message.get("text", "") if isinstance(message, dict) else ""
    command = text.strip().split(maxsplit=1)[0].split("@", 1)[0] if text else ""
    if not isinstance(chat, dict) or chat.get("type") != "private":
        return {"ok": True}
    if command == "/start":
        await send_bot_message(
            chat["id"],
            "To continue, please open the PresentSituation app.",
            settings,
            include_open_button=True,
        )
    elif command == "/help":
        await send_bot_message(
            chat["id"],
            "The Present Situation - a Telegram Mini App to create wish-lists, share them with friends, and make every occasion a little more special.",
            settings,
            include_open_button=True,
        )
    elif command.startswith("/"):
        await send_bot_message(
            chat["id"],
            "Sorry, this command is unknown.\n\nAvailable commands:\n/start - Open the app\n/help - Learn about the app",
            settings,
            include_open_button=True,
        )
    return {"ok": True}

@app.post("/api/auth/telegram")
def auth(p: AuthPayload, db: Session=Depends(get_session), s: Settings=Depends(get_settings)):
    t=verify(p.initData,s.bot_token); u=db.scalar(select(User).where(User.telegram_id==t["id"]))
    if not u: u=User(telegram_id=t["id"],username=t.get("username"),first_name=t.get("first_name", ""),last_name=t.get("last_name")); db.add(u)
    else: u.username,u.first_name,u.last_name=t.get("username"),t.get("first_name", ""),t.get("last_name")
    db.commit(); return {"token":sign(u.telegram_id,s),"user":{"id":u.telegram_id,"firstName":u.first_name}}
@app.get("/api/wishlists/mine")
def mine(u: User=Depends(current_user),db: Session=Depends(get_session),s: Settings=Depends(get_settings)):
    return [owner_out(w,s) for w in db.scalars(select(Wishlist).where(Wishlist.owner_id==u.id).options(selectinload(Wishlist.gifts))).all()]
@app.post("/api/wishlists",status_code=201)
def create(p: WishlistPayload,u: User=Depends(current_user),db: Session=Depends(get_session),s: Settings=Depends(get_settings)):
    w=Wishlist(owner_id=u.id,title=p.title.strip(),party_at=p.party_at,invite_token=secrets.token_urlsafe(24));
    if not w.title: fail(400, "Enter a title of up to 100 characters.")
    db.add(w); db.commit(); db.refresh(w); return owner_out(w,s)
@app.post("/api/wishlists/{wid}/gifts",status_code=201)
def add(wid:int,p: GiftPayload,u:User=Depends(current_user),db:Session=Depends(get_session)):
    w=db.scalar(select(Wishlist).where(Wishlist.id==wid,Wishlist.owner_id==u.id))
    if not w: fail(404, "Wishlist not found.")
    if w.status != WishlistStatus.ACTIVE: fail(409, "This wishlist cannot be changed.")
    g=Gift(wishlist_id=wid,title=p.title.strip(),product_url=str(p.url) if p.url else None,price_note=p.price,comment=p.note); db.add(g); db.commit(); db.refresh(g); return gift_out(g)
@app.put("/api/gifts/{gid}")
def edit(gid:int,p: GiftPayload,u:User=Depends(current_user),db:Session=Depends(get_session)):
    g=db.scalar(select(Gift).where(Gift.id==gid).options(selectinload(Gift.wishlist)))
    if not g or g.wishlist.owner_id != u.id or g.deleted_at is not None: fail(404, "Gift not found.")
    if g.wishlist.status != WishlistStatus.ACTIVE: fail(409, "This wishlist cannot be changed.")
    title = p.title.strip()
    if not title: fail(400, "Enter a gift name.")
    g.title, g.product_url, g.price_note, g.comment = title, str(p.url) if p.url else None, p.price, p.note
    db.commit(); db.refresh(g); return gift_out(g)
@app.delete("/api/gifts/{gid}",status_code=204)
def remove(gid:int,u:User=Depends(current_user),db:Session=Depends(get_session)):
    g=db.scalar(select(Gift).where(Gift.id==gid).options(selectinload(Gift.wishlist)))
    if not g or g.wishlist.owner_id!=u.id: fail(404, "Gift not found.")
    if g.wishlist.status!=WishlistStatus.ACTIVE: fail(409, "This wishlist cannot be changed.")
    g.deleted_at=datetime.now(timezone.utc); db.commit()
@app.get("/api/invites/{token}")
def invite(token:str,u:User=Depends(current_user),db:Session=Depends(get_session),s:Settings=Depends(get_settings)):
    w=db.scalar(select(Wishlist).where(Wishlist.invite_token==token).options(selectinload(Wishlist.gifts).selectinload(Gift.reservation)))
    if not w: fail(404, "Invite not found.")
    if w.owner_id==u.id: return {"isOwner":True,"list":owner_out(w,s)}
    gifts=[gift_out(g,g.reservation is not None and g.reservation.guest_id==u.id) for g in w.gifts if not g.deleted_at and (not g.reservation or g.reservation.guest_id==u.id)]
    return {"isOwner":False,"list":{"id":w.id,"title":w.title,"status":w.status.value,"partyAt":w.party_at.isoformat() if w.party_at else None,"gifts":gifts}}
@app.post("/api/gifts/{gid}/reserve",status_code=201)
def reserve(gid:int,u:User=Depends(current_user),db:Session=Depends(get_session)):
    g=db.scalar(select(Gift).where(Gift.id==gid).options(selectinload(Gift.wishlist)))
    if not g or g.deleted_at or g.wishlist.owner_id==u.id or g.wishlist.status!=WishlistStatus.ACTIVE: fail(404, "Gift is unavailable.")
    db.add(Reservation(gift_id=gid,guest_id=u.id))
    try: db.commit()
    except IntegrityError: db.rollback(); fail(409, "Another guest has already selected this gift.")
    return {"ok":True}
def cancel(gid,u,db):
    r=db.scalar(select(Reservation).where(Reservation.gift_id==gid,Reservation.guest_id==u.id))
    if not r: fail(404, "Your reservation was not found.")
    db.delete(r); db.commit()
@app.delete("/api/gifts/{gid}/reservation",status_code=204)
def unreserve(gid:int,u:User=Depends(current_user),db:Session=Depends(get_session)): cancel(gid,u,db)
@app.post("/api/gifts/{gid}/unreserve",status_code=204)
def old_unreserve(gid:int,u:User=Depends(current_user),db:Session=Depends(get_session)): cancel(gid,u,db)
@app.get("/health")
def health(): return {"ok":True}
@app.get("/")
def index():
    html = (PUBLIC / "index.html").read_text(encoding="utf-8")
    return HTMLResponse(
        html.replace("__ASSET_VERSION__", ASSET_VERSION),
        headers={"Cache-Control": "no-store, max-age=0"},
    )

# Keep this mount last: FastAPI resolves the API and health routes above first,
# while the browser can load the existing root-relative /app.js and /style.css.
app.mount("/", StaticFiles(directory=PUBLIC, html=True), name="frontend")
