"""
scripts/test_email.py
------------------------
Standalone SMTP test — sends one real test email using whatever's in your
.env, completely independent of the Flask app or the register/forgot-
password flow. Run this FIRST when debugging email, since it gives you
the exact error immediately instead of digging through server logs.

Usage:
    python scripts/test_email.py you@example.com

A successful run means SMTP is genuinely working — if register/forgot-
password still don't email you after this passes, restart the Flask
server (env vars are only read once, at startup — editing .env while
the server is running has no effect until you restart it).
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv  # noqa: E402

load_dotenv()

import auth  # noqa: E402


def main():
    if len(sys.argv) != 2:
        print("Usage: python scripts/test_email.py you@example.com")
        sys.exit(1)

    to_email = sys.argv[1]

    print("Checking configuration...")
    host = os.getenv("SMTP_HOST")
    port = os.getenv("SMTP_PORT")
    user = os.getenv("SMTP_USER")
    password = os.getenv("SMTP_PASSWORD")

    missing = [name for name, val in
               [("SMTP_HOST", host), ("SMTP_PORT", port), ("SMTP_USER", user), ("SMTP_PASSWORD", password)]
               if not val]
    if missing:
        print(f"\n❌ Not configured — missing from .env: {', '.join(missing)}")
        print("   Add these to .env, save the file, then run this script again.")
        print("   (For Gmail: SMTP_HOST=smtp.gmail.com, SMTP_PORT=587, SMTP_USER=your Gmail address,")
        print("    SMTP_PASSWORD=a 16-character App Password from")
        print("    https://myaccount.google.com/apppasswords — NOT your normal Gmail password.)")
        sys.exit(1)

    print(f"   SMTP_HOST={host}")
    print(f"   SMTP_PORT={port}")
    print(f"   SMTP_USER={user}")
    print(f"   SMTP_PASSWORD={'*' * len(password)} ({len(password)} characters)")
    print(f"\nSending a test email to {to_email}...")

    result = auth.send_email(
        to_email, "Krushi SMTP test",
        "If you're reading this, your Krushi SMTP configuration is working correctly. "
        "Real emails (welcome message, password reset codes) will now be delivered for real.",
    )

    if result["sent"]:
        print(f"\n✅ Sent successfully — check {to_email}'s inbox (and spam folder).")
        print("   If register/forgot-password in the web app still don't email you, restart the")
        print("   Flask server (`python app.py`) — env vars are only read once at startup.")
    else:
        print(f"\n❌ Send failed: {result.get('detail', 'unknown error')}")
        print("   Common causes:")
        print("   - Using your normal Gmail password instead of an App Password")
        print("   - 2-Step Verification not turned on for the Gmail account (required before")
        print("     App Passwords can be generated)")
        print("   - Wrong port (587 for STARTTLS, which is what this app uses)")
        print("   - Your network/firewall blocking outbound port 587")


if __name__ == "__main__":
    main()
