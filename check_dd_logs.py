import os
import json
import httpx
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

headers = {
    'DD-API-KEY': os.environ.get('DD_API_KEY'),
    'DD-APPLICATION-KEY': os.environ.get('DD_APP_KEY'),
    'Content-Type': 'application/json'
}

base_url = f'https://api.{os.environ.get("DD_SITE", "datadoghq.com")}'
now = datetime.now(timezone.utc)
start = now - timedelta(hours=1)

payload = {
    'filter': {
        'query': 'service:CheckoutAPI',
        'from': start.isoformat(),
        'to': now.isoformat()
    },
    'page': {'limit': 5}
}

print(f"Querying Datadog Logs API: {base_url}...")
resp = httpx.post(f'{base_url}/api/v2/logs/events/search', headers=headers, json=payload)
print(f'Status: {resp.status_code}')

if resp.status_code == 200:
    data = resp.json().get('data', [])
    print(f'Found {len(data)} logs for CheckoutAPI in the last hour')
    if data:
        print("\nSample Log Entry:")
        print(json.dumps(data[0].get('attributes', {}), indent=2))
        
        # Check HTTP Status Code tagging
        http_code = data[0].get('attributes', {}).get('http', {}).get('status_code')
        tags = data[0].get('attributes', {}).get('tags', [])
        
        print("\n--- Validation ---")
        print(f"HTTP Code parsed correctly by Datadog: {http_code}")
        print(f"Tags indexed: {tags}")
else:
    print(f"Error querying Datadog: {resp.text}")
