import base64
import os
import pyotp
import requests
from urllib.parse import parse_qs, urlparse

FYERS_ID = os.environ.get("FYERS_ID")
APP_ID = os.environ.get("APP_ID")
SECRET_KEY = os.environ.get("SECRET_KEY")
PIN = os.environ.get("PIN")
TOTP_KEY = os.environ.get("TOTP_KEY")

REDIRECT_URI = "https://trade.fyers.in/api-login/redirect-uri/index.html"
TOKEN_FILE = "access_token.txt"

def get_totp():
    return pyotp.TOTP(TOTP_KEY).now()

def auto_generate_token():
    session = requests.Session()
    
    # 1. Send Login OTP Request
    send_otp_url = "https://api-t1.fyers.in/api/v3/generate-authcode"
    payload_1 = {
        "fy_id": base64.b64encode(FYERS_ID.encode()).decode(),
        "app_id": "2"
    }
    r1 = session.post(send_otp_url, json=payload_1)
    req_key = r1.json().get("request_key")
    if not req_key:
        print("Failed to get request_key:", r1.text)
        return False

    # 2. Verify TOTP
    verify_totp_url = "https://api-t1.fyers.in/api/v3/verify-totp"
    payload_2 = {
        "request_key": req_key,
        "otp": get_totp()
    }
    r2 = session.post(verify_totp_url, json=payload_2)
    req_key_2 = r2.json().get("request_key")
    if not req_key_2:
        print("TOTP verification failed:", r2.text)
        return False

    # 3. Verify PIN
    verify_pin_url = "https://api-t1.fyers.in/api/v3/verify-pin"
    payload_3 = {
        "request_key": req_key_2,
        "identity_type": "pin",
        "identifier": base64.b64encode(PIN.encode()).decode()
    }
    r3 = session.post(verify_pin_url, json=payload_3)
    auth_token = r3.json().get("data", {}).get("token")
    if not auth_token:
        print("PIN verification failed:", r3.text)
        return False

    # 4. Generate Auth Code
    headers = {"Authorization": f"Bearer {auth_token}"}
    token_payload = {
        "fyers_id": FYERS_ID,
        "app_id": APP_ID.split("-")[0],
        "redirect_uri": REDIRECT_URI,
        "appType": "100",
        "code_challenge": "",
        "state": "smane_auth",
        "scope": "",
        "nonce": "",
        "response_type": "code",
        "create_cookie": True
    }
    r4 = session.post("https://api-t1.fyers.in/api/v3/token", headers=headers, json=token_payload)
    redirect_url = r4.json().get("Url")
    if not redirect_url:
        print("Failed to get redirect URL:", r4.text)
        return False

    parsed_url = urlparse(redirect_url)
    auth_code = parse_qs(parsed_url.query).get("auth_code", [None])[0]

    # 5. Exchange Auth Code for Access Token
    validate_url = "https://api-t1.fyers.in/api/v3/validate-authcode"
    app_id_hash = base64.sha256((APP_ID + ":" + SECRET_KEY).encode()).hexdigest()
    
    validate_payload = {
        "grant_type": "authorization_code",
        "appIdHash": app_id_hash,
        "code": auth_code
    }
    r5 = requests.post(validate_url, json=validate_payload)
    access_token = r5.json().get("access_token")

    if access_token:
        print("SUCCESS! New Access Token Generated.")
        with open(TOKEN_FILE, "w") as f:
            f.write(access_token)
        return True
    else:
        print("Access Token validation failed:", r5.text)
        return False

if __name__ == "__main__":
    auto_generate_token()
