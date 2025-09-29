from pydrive2.auth import GoogleAuth

gauth = GoogleAuth()

# Force offline access (refresh token) and required scope
gauth.settings['client_config_file'] = "client_secrets.json"  # your client secrets
gauth.settings['get_refresh_token'] = True
gauth.settings['oauth_scope'] = ['https://www.googleapis.com/auth/drive']

# Authenticate (browser will open)
gauth.LocalWebserverAuth()

# Save credentials for next time
gauth.SaveCredentialsFile("token.json")

print("Authentication successful! token.json created with refresh token.")