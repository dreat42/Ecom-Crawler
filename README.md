# ecom-crawler
a scalable web crawler for e-commerce product URL discovery.
# E-Commerce Product URL Crawler

## Overview
This Python script is an asynchronous web crawler designed to scrape e-commerce websites and extract product URLs. It utilizes `aiohttp`, `BeautifulSoup`, `Playwright`, and `motor` (MongoDB client) for efficient crawling, page content analysis, and data storage.

## Features
- **Asynchronous Crawling**: Uses `asyncio` and `aiohttp` for efficient crawling.
- **Playwright Integration**: Handles JavaScript-rendered pages.
- **Product URL Detection**: Uses heuristic-based URL patterns and content analysis.
- **Configurable Crawling Depth**: Limits the depth of crawling to prevent excessive requests.
- **MongoDB Storage (Optional)**: Saves the extracted data for further processing.
- **Error Handling and Logging**: Captures and logs errors for debugging.
- **Automatic Result Saving**: Stores results in JSON format.

## Installation
Ensure you have Python 3.8+ installed. Install dependencies using:

```sh
pip install -r requirements.txt
```

### Dependencies
- `aiohttp`
- `beautifulsoup4`
- `playwright`
- `motor`
- `asyncio`
- `dataclasses`

## Usage
Run the script using:

```sh
python crawler.py
```

## Configuration
Modify the `domains` list in `main()` to specify the e-commerce sites you want to crawl:

```python
domains = ["www.amazon.in", "www.flipkart.com"]
```

### Customizing Crawling Depth and Page Limits
Modify the `CrawlConfig` class to change settings:

```python
@dataclass
class CrawlConfig:
    domain: str
    max_depth: int = 3   # Maximum depth of crawling
    max_pages: int = 1000  # Maximum pages per domain
```

## Output
- Crawled product URLs are saved in `crawler_results/` as a JSON file.
- Statistics can be printed using:

```python
print("Crawling statistics:", crawler.get_statistics())
```

## Logging
To enable logging, modify the logger settings in `EcommerceCrawler`:

```python
self.logger.setLevel(logging.INFO)
```

## License
This project is open-source and available under the MIT License.

