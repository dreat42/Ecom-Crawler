import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import logging
from typing import List, Set, Dict, Tuple
import json
from dataclasses import dataclass, asdict
from collections import deque
import os
from datetime import datetime
from pathlib import Path

@dataclass
class CrawlConfig:
    """Configuration for crawling a specific domain"""
    domain: str
    product_patterns: List[str] = None
    max_depth: int = 3
    max_pages: int = 1000
    
    def __post_init__(self):
        # Default product URL patterns
        if not self.product_patterns:
            self.product_patterns = [
                # Standard product URL patterns
                r'/product[s]?/',
                r'/item[s]?/',
                r'/p/',
                r'/dp/',
                
                # Common product identifiers
                r'(?<=/)[a-zA-Z0-9]{6,}(?=/|$)',  # SKU-like patterns
                r'-pd-',
                r'prod[_-]id',
                
                # Category-based patterns
                r'/(?:men|women|kids|home)/[^/]+/[^/]+$',
                
                # Common e-commerce platforms
                r'/catalog/',
                r'/shop/',
                r'/detail/',
                
                # Query parameter patterns
                r'\?.*(?:product[_-]id|pid|itemid)='
            ]

class ProductURLDetector:
    """Handles sophisticated product URL detection logic"""
    
    def __init__(self):
        # Common non-product URL patterns
        self.exclude_patterns = [
            r'/cart',
            r'/checkout',
            r'/login',
            r'/account',
            r'/search',
            r'/category',
            r'/wishlist'
        ]
        
        # Product identifying HTML elements
        self.product_indicators = {
            'schema': re.compile(r'Product|ItemPage'),
            'class': re.compile(r'product[-_]?(detail|page|view|info)', re.I),
            'id': re.compile(r'product[-_]?(detail|page|view|info)', re.I)
        }

    async def analyze_page_content(self, html: str) -> bool:
        """Analyze page content for product indicators"""
        soup = BeautifulSoup(html, 'html.parser')
        
        # Check schema.org markup
        schema = soup.find('script', type='application/ld+json')
        if schema and self.product_indicators['schema'].search(str(schema)):
            return True
            
        # Check for product-specific elements
        if (soup.find(id=self.product_indicators['id']) or 
            soup.find(class_=self.product_indicators['class'])):
            return True
            
        # Check for common product page elements
        if (soup.find(['select', 'button'], string=re.compile(r'size|color|quantity', re.I)) and
            soup.find(string=re.compile(r'add to (?:cart|bag)', re.I))):
            return True
            
        return False


class EcommerceCrawler:
    def __init__(self, domains: List[str], concurrent_sites: int = 5, 
                 concurrent_pages: int = 10):
        self.configs = [CrawlConfig(domain.replace('https://', '').replace('http://', '')) 
                       for domain in domains]
        self.concurrent_sites = concurrent_sites
        self.concurrent_pages = concurrent_pages
        self.results: Dict[str, Set[str]] = {}
        self.seen_urls: Dict[str, Set[str]] = {}
        self.output_dir = Path.home() / "crawler_results"
        self.logger = self._setup_logger()
        self.product_detector = ProductURLDetector()
        
        # Create output directory in user's home
        self.output_dir.mkdir(exist_ok=True)

    async def _crawl_page(self, url: str, config: CrawlConfig, 
                         session: aiohttp.ClientSession, depth: int) -> None:
        """Crawl a single page and process discovered URLs"""
        if depth > config.max_depth or url in self.seen_urls[config.domain]:
            return
            
        self.seen_urls[config.domain].add(url)
        
        try:
            async with session.get(url) as response:
                if response.status != 200:
                    return
                    
                html = await response.text()
                is_product, confidence = await self._is_product_url(url, html, config.product_patterns)
                
                if is_product:
                    self.results[config.domain].add(url)
                    self.logger.info(f"Found product URL: {url} (confidence: {confidence:.2f})")
                
                urls = await self._extract_urls(html, url)
                
                if not urls and depth == 0:  # Try Playwright for homepage
                    urls = await self._crawl_with_playwright(url, config)
                
                tasks = []
                for discovered_url in urls:
                    if len(self.seen_urls[config.domain]) < config.max_pages:
                        task = asyncio.create_task(
                            self._crawl_page(discovered_url, config, session, depth + 1)
                        )
                        tasks.append(task)
                
                if tasks:
                    await asyncio.gather(*tasks)
                
        except Exception as e:
            self.logger.error(f"Error crawling {url}: {str(e)}")

    async def _crawl_site(self, config: CrawlConfig):
        """Crawl a single e-commerce site"""
        self.results[config.domain] = set()
        self.seen_urls[config.domain] = set()
        
        try:
            # Disable SSL certificate verification by using TCPConnector with ssl=False
            connector = aiohttp.TCPConnector(ssl=False)
            async with aiohttp.ClientSession(connector=connector) as session:
                start_url = f"https://{config.domain}"
                await self._crawl_page(start_url, config, session, 0)
                
        except Exception as e:
            self.logger.error(f"Error crawling site {config.domain}: {str(e)}")

    async def crawl(self):
        """Crawl all configured e-commerce sites"""
        tasks = []
        for i in range(0, len(self.configs), self.concurrent_sites):
            batch = self.configs[i:i + self.concurrent_sites]
            batch_tasks = [self._crawl_site(config) for config in batch]
            await asyncio.gather(*batch_tasks)
            tasks.extend(batch_tasks)
    def save_results(self, filename: str = None):
        """Save crawling results to a JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"product_urls_{timestamp}.json"
            
        filepath = os.path.join(self.output_dir, filename)
        
        try:
            results_dict = {
                domain: list(urls) 
                for domain, urls in self.results.items()
            }
            
            with open(filepath, 'w') as f:
                json.dump(results_dict, f, indent=2)
            self.logger.info(f"Results saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving results to {filepath}: {str(e)}")
            # Try saving to current directory as fallback
            fallback_path = f"fallback_{filename}"
            try:
                with open(fallback_path, 'w') as f:
                    json.dump(results_dict, f, indent=2)
                self.logger.info(f"Results saved to fallback location: {fallback_path}")
            except Exception as e2:
                self.logger.error(f"Failed to save results to fallback location: {str(e2)}")


    def get_statistics(self) -> Dict:
        """Get crawling statistics"""
        return {
            domain: {
                'product_urls': len(urls),
                'total_pages_crawled': len(self.seen_urls[domain])
            }
            for domain, urls in self.results.items()
        }

    def save_logs(self, filename: str):
        """Save crawling logs to a file"""
        for handler in self.logger.handlers[:]:
            self.logger.removeHandler(handler)
            
        file_handler = logging.FileHandler(filename)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

          
    def _setup_logger(self):
        """Configure logging for the crawler"""
        logger = logging.getLogger('ecommerce_crawler')
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        return logger

    async def _is_product_url(self, url: str, html: str, 
                             patterns: List[str]) -> Tuple[bool, float]:
        """
        Determine if URL is a product page using multiple heuristics
        Returns: (is_product, confidence_score)
        """
        # Check exclusion patterns first
        if any(re.search(pattern, url, re.IGNORECASE) 
               for pattern in self.product_detector.exclude_patterns):
            return False, 0.0
            
        confidence = 0.0
        
        # URL pattern matching
        if any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns):
            confidence += 0.4
            
        # Path depth heuristic (product pages often have deeper paths)
        path_segments = urlparse(url).path.strip('/').split('/')
        if 2 <= len(path_segments) <= 4:
            confidence += 0.2
            
        # Content analysis
        if await self.product_detector.analyze_page_content(html):
            confidence += 0.4
            
        return confidence >= 0.6, confidence

    async def _extract_urls(self, html: str, base_url: str) -> Set[str]:
        """Extract and normalize all URLs from HTML content"""
        soup = BeautifulSoup(html, 'html.parser')
        urls = set()
        
        for anchor in soup.find_all('a', href=True):
            url = urljoin(base_url, anchor['href'])
            parsed = urlparse(url)
            # Only include URLs from same domain
            if parsed.netloc == urlparse(base_url).netloc:
                urls.add(url)
                
        return urls


async def main():
    domains = ["www.amazon.in"] #, "www.flipkart.com"]
    crawler = EcommerceCrawler(domains)
    await crawler.crawl()
    crawler.save_results()
    print("Crawling statistics:", crawler.get_statistics())


if __name__ == "__main__":
    # asyncio.run(main())
    loop = asyncio.get_event_loop()  
    # If the loop is already running, schedule the main coroutine:
    if loop.is_running(): 
        asyncio.create_task(main())
    # Otherwise, run the loop until complete:
    else:
        loop.run_until_complete(main())
