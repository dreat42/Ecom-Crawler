from flask import Flask, jsonify, request
import asyncio
import argparse
import json
from src.crawler.ecommerce_crawler import EcommerceCrawler
from src.config.crawl_config import CrawlConfig
import os

app = Flask(__name__)

@app.route('/crawl', methods=['POST'])
def crawl():
    data = request.get_json()
    if not data or 'domains' not in data:
        return jsonify({'error': 'No domains provided'}), 400
    
    domains = data['domains']
    max_depth = data.get('max_depth', 3)
    max_pages = data.get('max_pages', 1000)
    
    configs = [
        CrawlConfig(
            domain=domain.replace('https://', '').replace('http://', ''),
            max_depth=max_depth,
            max_pages=max_pages
        ) for domain in domains
    ]
    
    crawler = EcommerceCrawler(configs=configs)
    
    async def run_crawler():
        await crawler.crawl()
        crawler.save_results("urls.json")
        return crawler.get_statistics()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    statistics = loop.run_until_complete(run_crawler())
    
    return jsonify({
        'status': 'success',
        'statistics': statistics
    })

port = int(os.getenv('PORT', 5000))

if __name__ == '__main__':
    app.run(host='0.0.0.0',  port=port) 