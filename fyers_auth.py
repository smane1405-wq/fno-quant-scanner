"""
╔══════════════════════════════════════════════════════════════════════╗
║   🔐 FYERS AUTOMATED AUTHENTICATION (Chrome Auto-Redirect)           ║
║   Saves access_token.txt for Smane1405 Live Scanner                  ║
╚══════════════════════════════════════════════════════════════════════╝
"""

import webbrowser
from urllib.parse import urlparse, parse_qs
from fyers_apiv3 import fyersModel

# --- Fyers App Credentials ---
CLIENT_ID    = "4O0N8E4C4S-100"                          # App Client ID
SECRET_KEY   = "UI0P3KTRB4"                              # Secret key
REDIRECT_URI = "https://127.0.0.1/"
TOKEN_FILE   = "access_token.txt"


def generate_auth_url():
    """OAuth URL तयार करणे आणि Chrome/Default Browser मध्ये स्वयंचलितरीत्या उघडणे"""
    session = fyersModel.SessionModel(
        client_id    = CLIENT_ID,
        secret_key   = SECRET_KEY,
        redirect_uri = REDIRECT_URI,
        response_type= "code",
        grant_type   = "authorization_code",
    )
    return session, session.generate_authcode()


def extract_auth_code(redirect_url: str) -> str:
    """रिडायरेक्ट झालेल्या URL मधून auth_code आपोआप काढणे"""
    parsed = urlparse(redirect_url)
    code   = parse_qs(parsed.query).get("auth_code", [None])[0]
    if not code:
        raise ValueError(
            "❌ auth_code सापडला नाही!\n"
            "   कृपया ब्राऊझरच्या ॲड्रेस बारमधील संपूर्ण URL कॉपी करून पेस्ट करा."
        )
    return code


def generate_token(session, auth_code: str) -> str:
    """auth_code च्या बदल्यात Access Token जनरेट करणे"""
    session.set_token(auth_code)
    response = session.generate_token()

    if "access_token" not in response:
        raise RuntimeError(
            f"❌ Access Token जनरेट होण्यात अडचण आली.\n"
            f"   Response: {response}\n"
            f"   Client ID किंवा Secret Key तपासा."
        )
    return response["access_token"]


def save_token(token: str):
    """Access Token फाईलमध्ये सेव्ह करणे"""
    with open(TOKEN_FILE, "w") as f:
        f.write(token)
    print(f"\n  ✅ Access Token सेव्ह झाला  →  {TOKEN_FILE}")
    print(f"  ℹ️  Token Preview: {token[:20]}...{token[-6:]}")


def verify_token(token: str):
    """लॉगिन यशस्वी झाल्याची खात्री करण्यासाठी Fyers Profile Verify करणे"""
    fyers = fyersModel.FyersModel(
        client_id = CLIENT_ID,
        token     = token,
        is_async  = False,
        log_path  = "",
    )
    resp = fyers.get_profile()
    if resp.get("code") == 200:
        name = resp["data"].get("name", "Unknown")
        pan  = resp["data"].get("pan_number", "")
        print(f"\n  ✅ यशस्वीरीत्या लॉग इन झाले : {name} (PAN: {pan})")
        print(f"  🚀 Token ACTIVE आहे! आता तुम्ही Live Scanner किंवा Background Engine वापरू शकता.")
    else:
        print(f"\n  ⚠️  Profile check returned: {resp}")
        print(f"      टोकन सेव्ह झाले आहे — पुढे चालू ठेवू शकता.")


def main():
    print("\n" + "═"*60)
    print("  🔐  FYERS AUTOMATED AUTHENTICATION  —  SMANE1405")
    print("═"*60)

    # Step 1 — Auto-open in Chrome Browser
    print("\n  Step 1 ▸ Fyers लॉगिन पेज Chrome ब्राऊझरमध्ये उघडत आहे...")
    session, auth_url = generate_auth_url()
    print(f"           URL: {auth_url[:72]}...")
    webbrowser.open(auth_url)

    # Step 2 — Paste Redirect URL
    print("\n  Step 2 ▸ ब्राऊझरमध्ये Fyers PIN/OTP टाकून लॉग इन करा.")
    print("           लॉग इन झाल्यावर रिडायरेक्ट झालेली संपूर्ण URL कॉपी करा.")
    redirect_url = input("\n  रिडायरेक्ट झालेली URL येथे पेस्ट करा: ").strip()

    # Step 3 — Extract Auth Code
    print("\n  Step 3 ▸ auth_code एक्स्ट्रॅक्ट होत आहे...")
    auth_code = extract_auth_code(redirect_url)

    # Step 4 — Generate Token
    print("\n  Step 4 ▸ Access Token जनरेट होत आहे...")
    access_token = generate_token(session, auth_code)

    # Step 5 — Save
    save_token(access_token)

    # Step 6 — Verify
    print("\n  Step 5 ▸ Profile call द्वारे टोकन व्हॅलिडेट करत आहे...")
    verify_token(access_token)

    print("\n" + "═"*60)
    print("  🎉 पूर्ण झाले! आता तुम्ही python background_engine.py रन करू शकता.")
    print("═"*60 + "\n")


if __name__ == "__main__":
    main()