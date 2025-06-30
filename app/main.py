from fastapi import FastAPI, HTTPException, Request, Depends
from fastapi.responses import RedirectResponse, HTMLResponse
from pydantic import BaseModel, HttpUrl
import psycopg2
import redis
import base62
from threading import Thread
import requests
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.utils import get_openapi
from fastapi.security import OAuth2PasswordBearer
from app.routers.auth import router as auth_router
from app.core.security import decode_token

app = FastAPI()

# ✅ Include Auth Router
app.include_router(auth_router)

# ✅ Swagger JWT security scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login")


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="FastAPI",
        version="1.0.0",
        description="Your project description here",
        routes=app.routes,
    )
    openapi_schema["components"]["securitySchemes"] = {
        "BearerAuth": {
            "type": "http",
            "scheme": "bearer",
            "bearerFormat": "JWT"
        }
    }

    for path in openapi_schema["paths"]:
        for method in openapi_schema["paths"][path]:
            openapi_schema["paths"][path][method]["security"] = [{"BearerAuth": []}]

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi


# ✅ Test Protected Endpoint


# ✅ Static files and templates
app.mount("/static", StaticFiles(directory="app/static"), name="static")
templates = Jinja2Templates(directory="app/templates")

# ✅ PostgreSQL connection
conn = psycopg2.connect(
    host="db",  # ✅ Correct
    port="5432",
    database="yourdb",
    user="youruser",
    password="yourpassword"
)


# ✅ Redis
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)

# ✅ Pydantic request model
class URLRequest(BaseModel):
    original_url: HttpUrl
    custom_alias: str = None

@app.get("/dashboard", response_class=HTMLResponse)
def show_dashboard(request: Request):
    return templates.TemplateResponse("dashboard.html", {"request": request})

# ✅ Fetch original URL by short code
def get_url_by_short_code(short_code: str) -> str | None:
    cur = conn.cursor()
    cur.execute("SELECT original_url FROM urls WHERE short_code = %s", (short_code,))
    row = cur.fetchone()
    return row[0] if row else None

# ✅ Rate limiting functions
def rate_limiter(short_code: str):
    key = f"rate:{short_code}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 60)
    if count > 100:
        raise HTTPException(status_code=429, detail="Rate limit exceeded")

def ip_rate_limiter(request: Request):
    ip = request.client.host
    key = f"iprate:{ip}"
    count = r.incr(key)
    if count == 1:
        r.expire(key, 60)
    if count > 200:
        raise HTTPException(status_code=429, detail="Too many requests from your IP")

# ✅ Country lookup
def get_country(ip):
    try:
        res = requests.get(f"https://ipwho.is/{ip}", timeout=2)
        data = res.json()
        if data.get("success") and data.get("country"):
            return data["country"]
    except:
        pass
    return "Undefined"

# ✅ Log click async
def log_click(short_code, request):
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM urls WHERE short_code = %s", (short_code,))
        url_row = cur.fetchone()
        if not url_row:
            return
        url_id = url_row[0]
        ip_address = request.client.host
        referrer = request.headers.get("referer", "") or "Direct"
        user_agent = request.headers.get("user-agent", "") or "Unknown"
        country = get_country(ip_address)
        cur.execute("""
            INSERT INTO clicks (url_id, ip_address, referrer, user_agent, country)
            VALUES (%s, %s, %s, %s, %s)
        """, (url_id, ip_address, referrer, user_agent, country))
        conn.commit()
    except:
        pass

# ✅ POST /shorten
@app.post("/shorten")
def shorten(req: URLRequest, request: Request):
    try:
        cur = conn.cursor()
        if req.custom_alias:
            cur.execute("SELECT 1 FROM urls WHERE short_code = %s", (req.custom_alias,))
            if cur.fetchone():
                raise HTTPException(status_code=400, detail="Custom alias already in use")
            short_code = req.custom_alias
            cur.execute(
                "INSERT INTO urls (original_url, short_code) VALUES (%s, %s) RETURNING id",
                (str(req.original_url), short_code)
            )
        else:
            cur.execute("INSERT INTO urls (original_url) VALUES (%s) RETURNING id", (str(req.original_url),))
            url_id = cur.fetchone()[0]
            short_code = base62.encode(url_id)
            cur.execute("UPDATE urls SET short_code = %s WHERE id = %s", (short_code, url_id))
        conn.commit()
        host = request.headers.get("host", "")
        return {"short_url": f"http://{host}/{short_code}"}
    except:
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ✅ GET /{short_code} with click tracking
@app.get("/{short_code}")
def redirect(short_code: str, request: Request, _: None = Depends(rate_limiter), __: None = Depends(ip_rate_limiter)):
    try:
        cached_url = r.get(f"url:{short_code}")
        if cached_url:
            Thread(target=log_click, args=(short_code, request)).start()
            return RedirectResponse(cached_url, status_code=307)

        original_url = get_url_by_short_code(short_code)
        if not original_url:
            raise HTTPException(status_code=404, detail="Short code not found")

        r.setex(f"url:{short_code}", 3600, original_url)
        Thread(target=log_click, args=(short_code, request)).start()
        return RedirectResponse(original_url, status_code=307)
    except:
        raise HTTPException(status_code=500, detail="Internal Server Error")

# ✅ Analytics endpoint
@app.get("/analytics/{short_code}", tags=["Analytics"])
def analytics(short_code: str):
    try:
        cur = conn.cursor()
        cur.execute("SELECT id FROM urls WHERE short_code = %s", (short_code,))
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Short URL not found")
        url_id = row[0]

        cur.execute("SELECT COUNT(*) FROM clicks WHERE url_id = %s", (url_id,))
        total_clicks = cur.fetchone()[0]

        cur.execute("SELECT country, COUNT(*) FROM clicks WHERE url_id = %s GROUP BY country", (url_id,))
        by_country = [{"country": r[0], "clicks": r[1]} for r in cur.fetchall()]

        cur.execute("SELECT user_agent, COUNT(*) FROM clicks WHERE url_id = %s GROUP BY user_agent", (url_id,))
        by_user_agent = [{"user_agent": r[0], "clicks": r[1]} for r in cur.fetchall()]

        cur.execute("SELECT referrer, COUNT(*) FROM clicks WHERE url_id = %s GROUP BY referrer", (url_id,))
        by_referrer = [{"referrer": r[0], "clicks": r[1]} for r in cur.fetchall()]

        return {
            "short_code": short_code,
            "total_clicks": total_clicks,
            "by_country": by_country,
            "by_user_agent": by_user_agent,
            "by_referrer": by_referrer
        }
    except:
        raise HTTPException(status_code=500, detail="Internal Server Error")
