import re
from bs4 import BeautifulSoup

class ProductURLDetector:
    """Handles sophisticated product URL detection logic"""
    
    def __init__(self):
        self.exclude_patterns = [
            r'/cart',
            r'/checkout',
            r'/login',
            r'/account',
            r'/search',
            r'/category',
            r'/wishlist'
        ]
        
        self.product_indicators = {
            'schema': re.compile(r'Product|ItemPage'),
            'class': re.compile(r'product[-_]?(detail|page|view|info)', re.I),
            'id': re.compile(r'product[-_]?(detail|page|view|info)', re.I)
        }

    async def analyze_page_content(self, html: str) -> bool:
        """Analyze page content for product indicators"""
        soup = BeautifulSoup(html, 'html.parser')
        
        schema = soup.find('script', type='application/ld+json')
        if schema and self.product_indicators['schema'].search(str(schema)):
            return True
            
        if (soup.find(id=self.product_indicators['id']) or 
            soup.find(class_=self.product_indicators['class'])):
            return True
            
        if (soup.find(['select', 'button'], string=re.compile(r'size|color|quantity', re.I)) and
            soup.find(string=re.compile(r'add to (?:cart|bag)', re.I))):
            return True
            
        return False 