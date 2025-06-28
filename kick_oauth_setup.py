#!/usr/bin/env python3
"""
Kick.com OAuth Setup Script
Use this script to authenticate with Kick and get your OAuth tokens
Run this once to get your tokens, then add them to your .env file
"""

import os
import base64
import hashlib
import webbrowser
from http.server import HTTPServer, BaseHTTPRequestHandler
import urllib.parse
import requests

# Replace with your actual credentials from https://kick.com/developer/applications
CLIENT_ID = "01JVQYSMAP1GCW6TJ7XR0PTDQX"
CLIENT_SECRET = "4e1b6d83048783e6d2c746d4c3b017bbc9b61a5e2040a16cf83cc34ee2c9ce0b"
REDIRECT_URI = "http://localhost:8080/callback"
SCOPES = [
    "user:read", "channel:read", "channel:write", "chat:write",
    "streamkey:read", "events:subscribe"
]

def generate_pkce_pair():
    """Generate PKCE code verifier and challenge"""
    verifier = base64.urlsafe_b64encode(os.urandom(40)).rstrip(b'=').decode('utf-8')
    challenge = base64.urlsafe_b64encode(
        hashlib.sha256(verifier.encode('utf-8')).digest()
    ).rstrip(b'=').decode('utf-8')
    return verifier, challenge

class OAuthCallbackHandler(BaseHTTPRequestHandler):
    """Handle OAuth callback from Kick"""
    def do_GET(self):
        parsed = urllib.parse.urlparse(self.path)
        query = urllib.parse.parse_qs(parsed.query)
        self.server.auth_code = query.get("code", [None])[0]

        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"<h1>Authorization successful. You may now close this window.</h1>")
    
    def log_message(self, format, *args):
        """Suppress server logs"""
        pass

def run_local_server():
    """Run local server to catch OAuth callback"""
    server = HTTPServer(("localhost", 8080), OAuthCallbackHandler)
    print("✅ Waiting for authorization callback...")
    server.handle_request()
    return server.auth_code

def exchange_code_for_token(code, verifier):
    """Exchange authorization code for access token"""
    token_url = "https://id.kick.com/oauth/token"
    payload = {
        "grant_type": "authorization_code",
        "code": code,
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET,
        "redirect_uri": REDIRECT_URI,
        "code_verifier": verifier
    }
    headers = {
        "Content-Type": "application/x-www-form-urlencoded"
    }
    response = requests.post(token_url, data=payload, headers=headers)
    return response.json()

def save_to_env_file(token_data):
    """Save tokens to .env file"""
    env_path = ".env"
    
    # Read existing .env file
    env_content = ""
    if os.path.exists(env_path):
        with open(env_path, 'r') as f:
            env_content = f.read()
    
    # Update Kick tokens
    access_token = token_data.get('access_token', '')
    refresh_token = token_data.get('refresh_token', '')
    
    # Remove existing Kick token lines
    lines = env_content.split('\n')
    lines = [line for line in lines if not line.startswith(('KICK_ACCESS_TOKEN=', 'KICK_REFRESH_TOKEN='))]
    
    # Add new Kick tokens
    lines.append(f"KICK_ACCESS_TOKEN={access_token}")
    lines.append(f"KICK_REFRESH_TOKEN={refresh_token}")
    
    # Write back to .env file
    with open(env_path, 'w') as f:
        f.write('\n'.join(line for line in lines if line.strip()))
    
    print(f"✅ Tokens saved to {env_path}")

def main():
    """Main OAuth flow"""
    print("🚀 Kick.com OAuth Setup for AI Moderator Bot")
    print("=" * 50)
    
    # Check if CLIENT_ID and CLIENT_SECRET are set
    if CLIENT_ID == "YOUR_CLIENT_ID" or CLIENT_SECRET == "YOUR_CLIENT_SECRET":
        print("❌ Please update CLIENT_ID and CLIENT_SECRET in this script")
        print("   Get them from: https://kick.com/developer/applications")
        return
    
    print(f"📋 Client ID: {CLIENT_ID}")
    print(f"🔗 Redirect URI: {REDIRECT_URI}")
    print(f"🎯 Scopes: {', '.join(SCOPES)}")
    print()
    
    # Generate PKCE
    verifier, challenge = generate_pkce_pair()
    scope_str = " ".join(SCOPES)
    state = base64.urlsafe_b64encode(os.urandom(16)).decode()

    # Build authorization URL
    auth_url = (
        f"https://id.kick.com/oauth/authorize"
        f"?response_type=code"
        f"&client_id={CLIENT_ID}"
        f"&redirect_uri={urllib.parse.quote(REDIRECT_URI)}"
        f"&scope={urllib.parse.quote(scope_str)}"
        f"&code_challenge={challenge}"
        f"&code_challenge_method=S256"
        f"&state={state}"
    )

    print("🔗 Opening browser to authenticate with Kick...")
    webbrowser.open(auth_url)

    # Get authorization code
    code = run_local_server()
    if not code:
        print("❌ Authorization code not received.")
        return

    print("📥 Authorization code received. Requesting tokens...")
    
    # Exchange code for tokens
    token_data = exchange_code_for_token(code, verifier)

    if "access_token" in token_data:
        print("✅ Access token retrieved successfully!")
        print()
        print("🎉 OAuth Setup Complete!")
        print("-" * 30)
        print(f"Access Token: {token_data['access_token'][:20]}...")
        print(f"Refresh Token: {token_data.get('refresh_token', 'N/A')[:20]}...")
        print(f"Token Type: {token_data.get('token_type', 'Bearer')}")
        print(f"Expires In: {token_data.get('expires_in', 'Unknown')} seconds")
        print()
        
        # Save to .env file
        save_to_env_file(token_data)
        print()
        print("✅ Setup Complete! You can now:")
        print("   1. Start your AI Moderator Bot")
        print("   2. Select 'Kick' platform in the web interface")
        print("   3. Enter your Kick channel name")
        print("   4. Start moderating with voice commands!")
        
    else:
        print("❌ Failed to get tokens:")
        print(token_data)

if __name__ == "__main__":
    main() 