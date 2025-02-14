import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import re
import logging
from typing import List, Set, Dict, Tuple
import json
from datetime import datetime
from pathlib import Path
import os

from src.config.crawl_config import CrawlConfig
from src.detectors.product_detector import ProductURLDetector

class EcommerceCrawler:
    def __init__(self, domains: List[str] = None, configs: List[CrawlConfig] = None, 
                 concurrent_sites: int = 5, concurrent_pages: int = 10):
        if configs:
            self.configs = configs
        else:
            self.configs = [CrawlConfig(domain.replace('https://', '').replace('http://', '')) 
                           for domain in domains]
        self.concurrent_sites = concurrent_sites
        self.concurrent_pages = concurrent_pages
        self.results: Dict[str, Set[str]] = {}
        self.seen_urls: Dict[str, Set[str]] = {}
        self.output_dir = Path("urls")
        self.logger = self._setup_logger()
        self.product_detector = ProductURLDetector()
        
        self.output_dir.mkdir(exist_ok=True)
        
        urls_file = self.output_dir / "urls.json"
        with open(urls_file, 'w') as f:
            json.dump({}, f, indent=2)

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

    def save_results(self, filename: str = "urls.json"):
        """Save crawling results to a JSON file"""
        filepath = self.output_dir / filename
        
        try:
            results_dict = {}
            for domain, urls in self.results.items():
                results_dict[domain] = sorted(list(urls))
            

            with open(filepath, 'w') as f:
                json.dump(results_dict, f, indent=2)
            
            self.logger.info(f"Results saved to {filepath}")
            
        except Exception as e:
            self.logger.error(f"Error saving results to {filepath}: {str(e)}")

    def get_statistics(self) -> Dict:
        """Get crawling statistics"""
        return {
            domain: {
                'product_urls': len(urls),
                'total_pages_crawled': len(self.seen_urls[domain])
            }
            for domain, urls in self.results.items()
        }

    def _setup_logger(self):
        """Configure logging for the crawler"""
        BLUE = '\033[94m'
        GREEN = '\033[92m'
        RED = '\033[91m'
        DARK_GREEN = '\033[32m'
        YELLOW = '\033[93m'
        RESET = '\033[0m'
        
        class ColoredFormatter(logging.Formatter):
            def format(self, record):
                original_msg = record.msg
                
                if "Found product URL:" in str(record.msg):
               
                    prefix, url_part = original_msg.split("Found product URL:")
                    url, confidence = url_part.rsplit(" (confidence:", 1)
                    record.msg = f"{BLUE}Found product URL:{GREEN}{url}{RESET} (confidence:{confidence})"
                elif "Results saved to" in str(record.msg):
                    record.msg = f"{DARK_GREEN}{original_msg}{RESET}"
                elif "Crawling statistics:" in str(record.msg):
                    record.msg = f"{YELLOW}{original_msg}{RESET}"
                elif record.levelno == logging.ERROR:
                    record.msg = f"{RED}{original_msg}{RESET}"
                else:
                    record.msg = f"{GREEN}{original_msg}{RESET}"
                    
                return super().format(record)
        
        logger = logging.getLogger('crawler') 
        logger.setLevel(logging.INFO)
        
        handler = logging.StreamHandler()
        formatter = ColoredFormatter('%(message)s') 
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        
        return logger

    async def _is_product_url(self, url: str, html: str, 
                             patterns: List[str]) -> Tuple[bool, float]:
        """
        Determine if URL is a product page using multiple heuristics
        Returns: (is_product, confidence_score)
        """
        if any(re.search(pattern, url, re.IGNORECASE) 
               for pattern in self.product_detector.exclude_patterns):
            return False, 0.0
            
        confidence = 0.0
        
        if any(re.search(pattern, url, re.IGNORECASE) for pattern in patterns):
            confidence += 0.4
            
        path_segments = urlparse(url).path.strip('/').split('/')
        if 2 <= len(path_segments) <= 4:
            confidence += 0.2
            
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
            if parsed.netloc == urlparse(base_url).netloc:
                urls.add(url)
                
        return urls 