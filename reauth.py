"""
Strava Re-Authorization Helper
Run this once to get a fresh refresh_token, then paste it into strava.py.
"""

import http.server
import threading
import webbrowser
import urllib.parse
import requests

CLIENT_ID = "157795"
CLIENT_SECRET = "b6ae0a8b3d49e9e82e3dcd5a91ab406663a1d103"
REDIRECT_URI = "http://localhost:8765"
SCOPE = "activity:read_all"

auth_code = None

class CallbackHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        global auth_code
        parsed = urllib.parse.urlparse(self.path)
        params = urllib.parse.parse_qs(parsed.query)
        if "code" in params:
            auth_code = params["code"][0]
            self.send_response(200)
            self.send_header("Content-type", "text/html")
            self.end_headers()
            self.wfile.write(b"<h2>Authorization successful! You can close this tab.</h2>")
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(b"<h2>No code received.</h2>")

    def log_message(self, *args):
        pass  # suppress request logs


def main():
    auth_url = (
        f"https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        f"&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        f"&approval_prompt=force"
        f"&scope={SCOPE}"
    )

    # Start local server to catch the callback
    server = http.server.HTTPServer(("localhost", 8765), CallbackHandler)
    thread = threading.Thread(target=server.handle_request)
    thread.start()

    print("Opening Strava authorization page in your browser …")
    print(f"\nIf it doesn't open automatically, visit:\n{auth_url}\n")
    webbrowser.open(auth_url)

    thread.join(timeout=120)

    if not auth_code:
        print("ERROR: Did not receive authorization code within 2 minutes.")
        return

    print("Authorization code received. Exchanging for tokens …")

    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
        }
    )
    response.raise_for_status()
    tokens = response.json()

    new_refresh_token = tokens["refresh_token"]
    new_access_token = tokens["access_token"]

    print("\n" + "=" * 55)
    print("  New tokens received!")
    print(f"  Refresh token : {new_refresh_token}")
    print(f"  Access token  : {new_access_token}")
    print("=" * 55)
    print("\nUpdating REFRESH_TOKEN in strava.py automatically …")

    with open("strava.py", "r") as f:
        content = f.read()

    # Replace the old refresh token line
    import re
    updated = re.sub(
        r'REFRESH_TOKEN\s*=\s*"[^"]*"',
        f'REFRESH_TOKEN = "{new_refresh_token}"',
        content
    )

    with open("strava.py", "w") as f:
        f.write(updated)

    print("Done! strava.py has been updated with your new refresh token.")
    print("You can now run:  python3 strava.py")


if __name__ == "__main__":
    main()
