from dataclasses import dataclass
from typing import List

@dataclass
class CrawlConfig:
    """Configuration for crawling a specific domain"""
    domain: str
    product_patterns: List[str] = None
    max_depth: int = 3
    max_pages: int = 1000
    
    def __post_init__(self):
        if not self.product_patterns:
            self.product_patterns = [
                r'/product[s]?/',
                r'/item[s]?/',
                r'/p/',
                r'/dp/',
                
                r'(?<=/)[a-zA-Z0-9]{6,}(?=/|$)',  
                r'-pd-',
                r'prod[_-]id',
                
                r'/(?:men|women|kids|home)/[^/]+/[^/]+$',
                
                r'/catalog/',
                r'/shop/',
                r'/detail/',
                
                r'\?.*(?:product[_-]id|pid|itemid)='
            ] 