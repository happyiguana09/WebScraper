import sys
from crawl import (
    get_heading_from_html,
    get_first_paragraph_from_html,
    get_urls_from_html,
    get_images_from_html,
)
from get_html import get_html

def main():
    print("Hello from webscraper!")
    if len(sys.argv) < 2:
        print("no website provided")
        sys.exit(1)
    elif len(sys.argv) > 2:
        print("too many arguments provided")
        sys.exit(1)

    print(f"starting crawl of: {sys.argv[1]}...")

    url = sys.argv[1]
    html = get_html(url)

    print(html)



if __name__ == "__main__":
    main()
