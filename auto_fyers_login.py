import base64
import hashlib
import os
import sys
import pyotp
import cloudscraper
from urllib.parse import parse_qs, urlparse

FYERS_ID = os.environ.get("FYERS_ID", "").strip()
APP_ID = os.environ.get("APP_ID", "").strip()
SECRET_KEY = os.environ.get("SECRET_KEY", "").strip()
PIN = os.environ.get("PIN", "").strip()
TOTP_KEY = os.environ.get("TOTP_KEY", "").strip()

REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
TOKEN_FILE = "access_token.txt"

def get_totp():
    return pyotp.TOTP(TOTP_KEY).now()

def auto_generate_token():
    if not (FYERS_ID and APP_ID and SECRET_KEY and PIN and TOTP_KEY):
        print("ERROR: Missing secrets!")
        sys.exit(1)

    # Cloudflare WAF bypass session
    scraper = cloudscraper.create_scraper(
        browser={
            'browser': 'chrome',
            'platform': 'windows',
            'desktop': True
        }
    )

    # 1. Send Login OTP Request
    send_otp_url = "https://api-t1.fyers.in/api/v3/generate-authcode"
    payload_1 = {
        "fy_id": base64.b64encode(FYERS_ID.encode()).decode(),
        "app_id": "2"
    }
    r1 = scraper.post(send_otp_url, json=payload_1, timeout=15)
    try:
        res1 = r1.json()
    except Exception:
        print("Step 1 Blocked by Cloudflare:", r1.text[:200])
        sys.exit(1)

    req_key = res1.get("request_key")
    if not req_key:
        print("Failed to get request_key:", res1)
        sys.exit(1)

    # 2. Verify TOTP
    verify_totp_url = "https://api-t1.fyers.in/api/v3/verify-totp"
    payload_2 = {
        "request_key": req_key,
        "otp": get_totp()
    }
    r2 = scraper.post(verify_totp_url, json=payload_2, timeout=15)
    res2 = r2.json()
    req_key_2 = res2.get("request_key")
    if not req_key_2:
        print("TOTP verification failed:", res2)
        sys.exit(1)

    # 3. Verify PIN
    verify_pin_url = "https://api-t1.fyers.in/api/v3/verify-pin"
    payload_3 = {
        "request_key": req_key_2,
        "identity_type": "pin",
        "identifier": base64.b64encode(PIN.encode()).decode()
    }
    r3 = scraper.post(verify_pin_url, json=payload_3, timeout=15)
    res3 = r3.json()
    auth_token = res3.get("data", {}).get("token")
    if not auth_token:
        print("PIN verification failed:", res3)
        sys.exit(1)

    # 4. Generate Auth Code
    headers_token = {
        "Authorization": f"Bearer {auth_token}",
        "Content-Type": "application/json; charset=UTF-8"
    }
    app_prefix = APP_ID.split("-")[0]
    token_payload = {
        "fyers_id": FYERS_ID,
        "app_id": app_prefix,
        "redirect_uri": REDIRECT_URI,
        "appType": "100",
        "code_challenge": "",
        "state": "smane_auth",
        "scope": "",
        "nonce": "",
        "response_type": "code",
        "create_cookie": True
    }
    r4 = scraper.post("https://api-t1.fyers.in/api/v3/token", headers=headers_token, json=token_payload, timeout=15)
    res4 = r4.json()
    redirect_url = res4.get("Url")
    if not redirect_url:
        print("Failed to get redirect URL:", res4)
        sys.exit(1)

    parsed_url = urlparse(redirect_url)
    auth_code = parse_qs(parsed_url.query).get("auth_code", [None])[0]

    # 5. Exchange Auth Code for Access Token
    validate_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    app_id_hash = hashlib.sha256((APP_ID + ":" + SECRET_KEY).encode()).hexdigest()

    validate_payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code
    }
    r5 = scraper.post(validate_url, json=validate_payload, timeout=15)
    res5 = r5.json()
    access_token = res5.get("access_token")

    if access_token:
        print("SUCCESS: New Access Token Generated Successfully!")
        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)
        return True
    else:
        print("Access Token validation failed:", res5)
        sys.exit(1)

if __name__ == "__main__":
    auto_generate_token()
