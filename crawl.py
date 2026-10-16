from urllib.parse import urlsplit, urljoin
from bs4 import BeautifulSoup, Tag
import aiohttp, asyncio
from types import TracebackType
from typing import TypedDict
from get_html import safe_get_html

def normalize_url(url: str) -> str:
    parsed_url = urlsplit(url)
    full_path = f"{parsed_url.netloc}{parsed_url.path}"
    full_path = full_path.rstrip("/")
    return full_path.lower()


def get_heading_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    h_tag = soup.find("h1") or soup.find("h2")
    return h_tag.get_text(strip=True) if isinstance(h_tag, Tag) else ""


def get_first_paragraph_from_html(html: str) -> str:
    soup = BeautifulSoup(html, "html.parser")
    main = soup.find("main")
    if isinstance(main, Tag):
        p_tag = main.find("p")
    else:
        p_tag = soup.find("p")

    return p_tag.get_text(strip=True) if isinstance(p_tag, Tag) else ""


def get_urls_from_html(html: str, base_url: str) -> list[str]:
    urls = []
    soup = BeautifulSoup(html, "html.parser")
    anchors = soup.find_all("a")

    for anchor in anchors:
        if not isinstance(anchor, Tag):
            continue
        href = anchor.get("href")
        if isinstance(href, str) and href:
            try:
                absolute_url = urljoin(base_url, href)
                urls.append(absolute_url)
            except Exception as e:
                print(f"{str(e)}: {href}")

    return urls


def get_images_from_html(html: str, base_url: str) -> list[str]:
    images = []
    soup = BeautifulSoup(html, "html.parser")
    imgs = soup.find_all("img")

    for img in imgs:
        if not isinstance(img, Tag):
            continue
        src = img.get("src")
        if isinstance(src, str) and src:
            try:
                full_src = urljoin(base_url, src)
                images.append(full_src)
            except Exception as e:
                print(f"{str(e)}: {src}")

    return images

class PageData(TypedDict):
    url: str
    heading: str
    first_paragraph: str
    outgoing_links: list[str]
    image_urls: list[str]


def extract_page_data(html: str, page_url: str) -> PageData:
    return {
        "url": page_url,
        "heading": get_heading_from_html(html),
        "first_paragraph": get_first_paragraph_from_html(html),
        "outgoing_links": get_urls_from_html(html, page_url),
        "image_urls": get_images_from_html(html, page_url),
    }

def crawl_page(base_url: str,
               current_url: str | None = None,
               page_data: dict[str, PageData] | None = None,
) -> dict[str, PageData]:
    if page_data is None:
        page_data = {}
    if current_url is None:
        current_url = base_url
    
    base_domain = urlsplit(base_url)
    current_domain = urlsplit(current_url)

    if base_domain.netloc != current_domain.netloc:
        return page_data

    curr_norm_url = normalize_url(current_url)

    if curr_norm_url in page_data:
        return page_data

    html = safe_get_html(current_url)
    if html is None:
        return page_data

    print(f"extracting html from {curr_norm_url}")
    page_data[curr_norm_url] = extract_page_data(html, current_url)

    for link in page_data[curr_norm_url]["outgoing_links"]:
        print(f"crawling next page: {link}")
        page_data = crawl_page(base_url, link, page_data)

    return page_data


class AsyncCrawler:
    def __init__(self, base_url: str, max_concurrency: int, max_pages: int) -> None:
        self.base_url = base_url
        self.base_domain = urlsplit(base_url).netloc
        self.page_data: dict[str, PageData] = {}
        self.visited: set[str] = set()
        self.lock = asyncio.Lock()
        self.max_concurrency = max_concurrency
        self.max_pages = max_pages
        self.semaphore = asyncio.Semaphore(self.max_concurrency)
        self.session: aiohttp.ClientSession | None = None
        self.should_stop = False
        self.all_tasks: set[asyncio.Task[None]] = set()

    async def __aenter__(self) -> "AsyncCrawler":
        self.session = aiohttp.ClientSession()
        return self

    async def __aexit__(
            self,
            exc_type: type[BaseException] | None,
            exc_val: BaseException | None,
            exc_tb: TracebackType | None,
        ) -> None:
        if self.session is not None:
            await self.session.close()

    async def add_page_visit(self, normalized_url):
        async with self.lock:
            if self.should_stop:
                return False
            if normalize_url in self.visited:
                return False
            if len(self.visited) >= self.max_pages:
                self.should_stop = True
                print("Reached maximum number of pages to crawl.")
                return False
            self.visited.add(normalized_url)
            return True

    async def get_html(self, url):
        if self.session is None:
            return None
        try:
            async with self.session.get(url) as resp:
                if resp.status > 399:
                    print(f"Error: HTTP {resp.status} for {url}")
                    return None

                content_type = resp.headers.get("content-type", "")
                if "text/html" not in content_type:
                    print(f"Error: Non-HTML content {content_type} for {url}")
                    return None

                return await resp.text()

        except Exception as e:
                print(f"Network error while fetching {url}: {e}")
                return None

    async def crawl_page(self, current_url: str) -> None:
        if self.should_stop:
            return

        current_url_obj = urlsplit(current_url)
        if current_url_obj.netloc != self.base_domain:
            return

        norm_url = normalize_url(current_url)

        is_new = await self.add_page_visit(norm_url)
        if not is_new:
            return

        async with self.semaphore:
            print(f"Crawling {current_url} (Active: {self.max_concurrency - self.semaphore._value})")
            html = await self.get_html(current_url)
            if html is None:
                return

            page_info = extract_page_data(html, current_url)
            async with self.lock:
                self.page_data[norm_url] = page_info

            next_urls = page_info["outgoing_links"]

        if self.should_stop:
            return

        tasks: list[asyncio.Task[None]] = []
        for next_url in next_urls:
            task = asyncio.create_task(self.crawl_page(next_url))
            tasks.append(task)
            self.all_tasks.add(task)

        if tasks:
            try:
                await asyncio.gather(*tasks, return_exceptions=True)
            finally:
                for task in tasks:
                    self.all_tasks.discard(task)

    async def crawl(self) -> dict[str, PageData]:
        await self.crawl_page(self.base_url)
        return self.page_data


async def crawl_site_async(base_url: str, max_pages: int, max_concurrency: int) -> dict[str, PageData]:
    async with AsyncCrawler(base_url, max_pages, max_concurrency) as crawler:
        return await crawler.crawl()
