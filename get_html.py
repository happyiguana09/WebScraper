import requests

def get_html(url):
    try:
        resp = requests.get(url, headers={"User-Agent": "BootCrawler/1.0"})
    except Exception as e:
        raise Exception(f"network error while fetching {url}: {e}")

    if resp.status_code > 399:
        raise Exception(f"got HTTP error: {resp.status_code} {resp.reason}")

    if resp.headers["Content-Type"] != "text/html":
        raise Exception(f"got non-HTML response: {resp.headers.get("Content-Type", "")}")

    return resp.text
    
def safe_get_html(url: str) -> str | None:
    try:
        return get_html(url)
    except Exception as e:
        print(f"{e}")
        return None