"""
Strava Re-Authorization Helper

Run once to generate a new refresh_token.
Then update STRAVA_REFRESH_TOKEN in Streamlit Secrets.
"""

import http.server
import threading
import webbrowser
import urllib.parse
import requests
import tomllib


# Load secrets
with open(".streamlit/secrets.toml", "rb") as f:
    secrets = tomllib.load(f)

CLIENT_ID = secrets["STRAVA_CLIENT_ID"]
CLIENT_SECRET = secrets["STRAVA_CLIENT_SECRET"]

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
            self.send_header(
                "Content-type",
                "text/html"
            )
            self.end_headers()

            self.wfile.write(
                b"<h2>Authorization successful. You can close this tab.</h2>"
            )
        else:
            self.send_response(400)
            self.end_headers()
            self.wfile.write(
                b"<h2>No authorization code received.</h2>"
            )

    def log_message(self, *args):
        pass


def main():

    auth_url = (
        "https://www.strava.com/oauth/authorize"
        f"?client_id={CLIENT_ID}"
        "&response_type=code"
        f"&redirect_uri={REDIRECT_URI}"
        "&approval_prompt=force"
        f"&scope={SCOPE}"
    )

    server = http.server.HTTPServer(
        ("localhost", 8765),
        CallbackHandler
    )

    thread = threading.Thread(
        target=server.handle_request
    )

    thread.start()

    print("Opening Strava authorization page...")
    webbrowser.open(auth_url)

    thread.join(timeout=120)

    if not auth_code:
        print("Authorization timed out.")
        return


    print("Exchanging authorization code...")

    response = requests.post(
        "https://www.strava.com/oauth/token",
        data={
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET,
            "code": auth_code,
            "grant_type": "authorization_code",
        },
    )

    response.raise_for_status()

    tokens = response.json()


    print("\nSuccess!")
    print("--------------------------------")
    print("New refresh token:")
    print(tokens["refresh_token"])
    print("--------------------------------")

    print(
        """
Copy this value into:

.streamlit/secrets.toml

STRAVA_REFRESH_TOKEN = "new_value_here"
"""
    )


if __name__ == "__main__":
    main()
