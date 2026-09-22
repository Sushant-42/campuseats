import time
import random
import requests


CATALOG_URL = "http://localhost:8001"


def check_item(item_id):
    url = f"{CATALOG_URL}/items/{item_id}"

    for attempt in range(3):
        try:
            response = requests.get(url, timeout=2)

            if response.status_code == 200:
                return response.json()

            if response.status_code == 404:
                return None

        except requests.RequestException:
            pass

        if attempt < 2:
            delay = (2 ** attempt) + random.uniform(0, 0.5)
            time.sleep(delay)

    return None