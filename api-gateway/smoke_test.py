import argparse
import json
import sys

import httpx


def run(base_url: str, token: str, username: str, include_chatbot: bool) -> int:
    headers = {"Authorization": f"Bearer {token}"}

    with httpx.Client(timeout=180.0) as client:
        health = client.get(f"{base_url}/health")
        print(f"/health -> {health.status_code}")
        if health.status_code != 200:
            print("Health check failed:", health.text)
            return 1

        payload = {
            "username": username,
            "include_chatbot": include_chatbot,
            "analysis_payload": {
                "username": username,
                "scrape_comments": True,
                "export_csv": True,
            },
        }

        resp = client.post(f"{base_url}/workflow/run", headers=headers, json=payload)
        print(f"/workflow/run -> {resp.status_code}")
        try:
            data = resp.json()
            print(json.dumps(data, indent=2)[:5000])
        except Exception:
            print(resp.text)

        return 0 if resp.status_code == 200 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke test for API Gateway workflow")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Gateway base URL")
    parser.add_argument("--token", required=True, help="Google OAuth access token")
    parser.add_argument("--username", required=True, help="Instagram username to process")
    parser.add_argument("--include-chatbot", action="store_true", help="Also run chatbot step")
    args = parser.parse_args()

    return run(args.base_url, args.token, args.username, args.include_chatbot)


if __name__ == "__main__":
    sys.exit(main())
