from flask import Flask, request
from kiteconnect import KiteConnect
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)

app = Flask(__name__)

# Your credentials
API_KEY = "your_api_key_here"
API_SECRET = "your_api_secret_here"

kite = KiteConnect(api_key=API_KEY)

def json_serial(obj):
    """JSON serializer for datetime objects"""
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

@app.route('/callback')
def callback():
    request_token = request.args.get('request_token')

    if not request_token:
        return "Error: No request token received", 400

    try:
        # Exchange request_token for access_token
        data = kite.generate_session(request_token, api_secret=API_SECRET)
        access_token = data["access_token"]

        # Save access token (this is what matters)
        with open('access_token.txt', 'w') as f:
            f.write(access_token)

        # Save full session data with datetime handling
        with open('session_data.json', 'w') as f:
            json.dump(data, f, indent=2, default=json_serial)

        logging.info(f"✅ Access token saved: {access_token}")

        return f"""
        <h2>✅ Login Successful!</h2>
        <p><strong>Access token saved to access_token.txt</strong></p>
        <p>Token: <code>{access_token}</code></p>
        <p>You can now close this window and run your trading bot!</p>
        <hr>
        <p>Press Ctrl+C in terminal to stop the Flask server.</p>
        """

    except Exception as e:
        logging.error(f"❌ Error: {e}")
        return f"<h2>❌ Error:</h2><pre>{str(e)}</pre>", 500

if __name__ == '__main__':
    login_url = kite.login_url()
    print("\n" + "="*60)
    print("🔗 OPEN THIS URL IN BROWSER:")
    print(login_url)
    print("="*60 + "\n")

    app.run(port=5000, debug=False)
