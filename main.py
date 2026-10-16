import sys
import asyncio
from crawl import crawl_site_async
from get_html import get_html


async def main() -> None:
    if len(sys.argv) < 4:
        print("no website provided")
        sys.exit(1)
    elif len(sys.argv) > 4:
        print("too many arguments provided")
        sys.exit(1)

    print(f"starting crawl of: {sys.argv[1]}...")

    base_url = sys.argv[1]

    if not sys.argv[2].isdigit:
        print("max_concurency must be an integer")
        sys.exit(1)
    if not sys.argv[3].isdigit:
        print("max_pages must be an integer")
        sys.exit(1)
    
    max_concurrency = int(sys.argv[2])
    max_pages = int(sys.argv[3])

    page_data = await crawl_site_async(base_url, max_concurrency, max_pages)

    print(f"Found {len(page_data)} pages:")
    for page in page_data.values():
        print(f"Found {len(page["outgoing_links"])} outgoing links on {page["url"]}")


if __name__ == "__main__":
    asyncio.run(main())
