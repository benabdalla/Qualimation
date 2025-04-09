import json
import requests
from requests.auth import HTTPBasicAuth
from requests.models import Response
import os
import requests

# Constants
AUTH_URL = "https://xray.cloud.getxray.app/api/v2/authenticate"
CLIENT_ID = "1CFA19C10AFD4DDDB7F85EE6E56035A3"
CLIENT_SECRET = "4d6317a9dab393ae67f7947b273e6e1820315efc25a42d51ddb4f47a869ab2b7"
IMPORT_URL = "https://xray.cloud.getxray.app/api/v2/import/execution/"
BASE_URL = "https://xray.cloud.getxray.app/"
PROJECTXRAYID = "CDT"


# 1️⃣ Authenticate and Get JWT Token
def get_auth_token() -> str:
    auth_payload = {
        "client_id": CLIENT_ID,
        "client_secret": CLIENT_SECRET
    }

    headers = {
        "Content-Type": "application/json"
    }

    response = requests.post(AUTH_URL, json=auth_payload, headers=headers)

    if response.status_code == 200:
        try:
            # json_response = response.json()  # Vérifier si la réponse est JSON
            token = response.json()

            if token:
                return token
            else:
                print("Authentication succeeded but no token found in response.")

                return None

        except requests.exceptions.JSONDecodeError:
            print("Authentication failed: Response is not in JSON format.")
            print("Raw response:", response.text)
            return None

    else:
        print(f"Authentication failed: HTTP {response.status_code}")
        print("Response:", response.text)  # Afficher le contenu de la réponse
        return None


def import_test_results(token: str, path: str) -> None:
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    with open(path, "r", encoding="utf-8") as file:
        data = file.read()

    print("📂 JSON Data Being Sent:", data)  # Print JSON content before sending
    response = requests.post(IMPORT_URL, headers=headers, data=data)

    print(f"🔴 Response Code: {response.status_code}")
    print(f"🔴 Response Body: {response.text}")

# Example usage
if __name__ == "__main__":
    token = get_auth_token()
    import_test_results(token, "reports/xray_report.json")
    # import_feature_file_to_xray(token, "path/to/your/feature_file.feature")
