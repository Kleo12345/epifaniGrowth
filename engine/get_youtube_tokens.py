"""
Helper script to perform one-time OAuth 2.0 authentication to get the YouTube Refresh Token.
Launches a temporary local server on port 8080 to handle the callback.
"""
import os
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, urlparse
import requests
from dotenv import load_dotenv

load_dotenv()

PORT = 8080
REDIRECT_URI = f"http://localhost:{PORT}"
SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]

authorization_code = None


class OAuthCallbackHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        global authorization_code
        query = parse_qs(urlparse(self.path).query)
        
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()

        if "code" in query:
            authorization_code = query["code"][0]
            html = """
            <html>
                <body style="font-family: Arial, sans-serif; text-align: center; padding: 50px; background-color: #121214; color: #ffffff;">
                    <h2 style="color: #00f2ff;">✓ Authentication Successful!</h2>
                    <p>You can close this tab and return to your terminal.</p>
                </body>
            </html>
            """
            self.wfile.write(html.encode("utf-8"))
        else:
            self.wfile.write(b"No authorization code received.")

    def log_message(self, format, *args):
        # Suppress logging in terminal
        return


def get_tokens(client_id, client_secret):
    # Step 1: Generate Authorization URL
    auth_url = (
        "https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={client_id}&"
        f"redirect_uri={REDIRECT_URI}&"
        f"response_type=code&"
        f"scope={' '.join(SCOPES)}&"
        "access_type=offline&"
        "prompt=consent"
    )

    print("\n======================================================================")
    print("EPIFANI GROWTH ENGINE — YOUTUBE OAUTH SETUP")
    print("======================================================================\n")
    print("Please open the following link in your browser to authorize your account:")
    print(f"\n{auth_url}\n")
    print("Opening browser automatically...")
    
    # Try to open browser
    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    # Start local HTTP server to catch redirect code
    server = HTTPServer(("localhost", PORT), OAuthCallbackHandler)
    while authorization_code is None:
        server.handle_request()

    # Step 2: Exchange Authorization Code for Refresh Token
    token_url = "https://oauth2.googleapis.com/token"
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": authorization_code,
        "redirect_uri": REDIRECT_URI,
        "grant_type": "authorization_code",
    }

    print("\nExchanging code for tokens...")
    resp = requests.post(token_url, data=payload)
    if resp.status_code != 200:
        print(f"Error exchanging token: {resp.text}")
        sys.exit(1)

    tokens = resp.json()
    refresh_token = tokens.get("refresh_token")
    access_token = tokens.get("access_token")

    print("\n======================================================================")
    print("✓ SUCCESS! Paste the following lines into your .env file:")
    print("======================================================================\n")
    print(f"YOUTUBE_CLIENT_ID={client_id}")
    print(f"YOUTUBE_CLIENT_SECRET={client_secret}")
    print(f"YOUTUBE_REFRESH_TOKEN={refresh_token}")
    print("\n======================================================================\n")


if __name__ == "__main__":
    client_id = os.getenv("YOUTUBE_CLIENT_ID")
    client_secret = os.getenv("YOUTUBE_CLIENT_SECRET")

    if not client_id or not client_secret or "your_client_id_here" in client_id:
        print("\n[!] Please specify YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET first.")
        print("You can add them to your .env file or input them below:")
        client_id = input("Client ID: ").strip()
        client_secret = input("Client Secret: ").strip()

    if not client_id or not client_secret:
        print("Error: Client ID and Client Secret are required.")
        sys.exit(1)

    get_tokens(client_id, client_secret)
