import os
import time
import random
import certifi
from urllib import parse
from datetime import datetime
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from domain import get_domain_name
from general import *
from link_finder import LinkFinder
from bs4 import BeautifulSoup
import requests
import requests.adapters
from urllib3.util.ssl_ import create_urllib3_context

# 导入自定义模块
from text_processor import TextProcessor
from es_client import ElasticsearchClient
from file_manager import FileManager


class Spider:
    def __init__(self, project_name, base_url, domain_name, language='en', max_pages=100):
        # 基础配置
        self.project_name = project_name
        self.base_url = base_url
        self.domain_name = domain_name
        self.language = language
        self.max_pages = max_pages
        self.crawled_count = 0

        # 初始化模块
        self.text_processor = TextProcessor(language)
        self.es_client = ElasticsearchClient()
        self.file_manager = FileManager(project_name)

        # 队列管理
        self.queue_file = f'{project_name}/queue.txt'
        self.crawled_file = f'{project_name}/crawled.txt'
        self.queue = set()
        self.crawled = set()

        # 启动初始化
        self._boot()
        self.crawl_page('First spider', self.base_url)

    def _boot(self):
        """初始化爬虫环境"""
        create_project_dir(self.project_name)
        create_data_files(self.project_name, self.base_url)
        self.queue = file_to_set(self.queue_file)
        self.crawled = file_to_set(self.crawled_file)

    def crawl_page(self, thread_name, page_url):
        """核心爬取方法"""
        if self._reach_crawl_limit():
            return

        if page_url not in self.crawled:
            try:
                print(f'{thread_name} now crawling {page_url}')
                html_content, links = self._fetch_and_parse(page_url)

                if html_content:
                    self._process_content(page_url, html_content)
                    self._update_crawl_state(page_url, links)

                if self._reach_crawl_limit():
                    self._clear_queue()

            except Exception as e:
                print(f'Critical error at {page_url}: {str(e)}')
                self._handle_crawl_error(page_url)

    def _fetch_and_parse(self, page_url):
        """获取页面内容并解析链接"""
        session = None
        try:
            # 创建带TLS指纹的会话
            session = self._create_secure_session()
            html_content = self._fetch_content(session, page_url)

            if not html_content:
                return None, set()

            # 解析链接和保存内容
            links = self._extract_links(page_url, html_content)
            return html_content, links

        finally:
            if session:
                session.close()

    def _create_secure_session(self):
        """创建安全会话"""

        class TLSAdapter(requests.adapters.HTTPAdapter):
            def init_poolmanager(self, *args, **kwargs):
                ctx = create_urllib3_context()
                ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
                kwargs['ssl_context'] = ctx
                return super().init_poolmanager(*args, **kwargs)

        session = requests.Session()
        session.mount('https://', TLSAdapter())
        return session

    def _fetch_content(self, session, page_url):
        """执行带重试机制的请求"""
        for attempt in range(3):
            try:
                response = session.get(
                    page_url,
                    headers=self._generate_headers(page_url),
                    timeout=20,
                    allow_redirects=True,
                    verify=certifi.where(),
                    proxies={
                        'http': None,
                        'https': None
                    }
                )
                response.encoding = response.apparent_encoding
                return response.text

            except requests.exceptions.RequestException as e:
                print(f"Attempt {attempt + 1} failed: {str(e)}")
                time.sleep(2 ** attempt)

        print(f"Failed to fetch {page_url} after 3 attempts")
        return None

    def _process_content(self, url, content):
        """处理并存储内容"""
        content = BeautifulSoup(content, 'html.parser').get_text(' ', strip=True)

        # 保存原始内容
        self.file_manager.save_content(url, content, 'org')

        # 处理文本内容
        processed_text = self.text_processor.process_text(content)

        # 保存处理后的内容
        suffix = 'c' if self.language == 'cn' else 'e'
        self.file_manager.save_content(url, processed_text, suffix)

        # 索引到Elasticsearch
        self._index_to_es(url, processed_text, content)

        # 更新统计计数
        self.crawled_count = self.file_manager.get_valid_file_count()

    def _index_to_es(self, url, processed, original):
        """索引文档到Elasticsearch"""
        document = {
            "url": url,
            "content": original.strip()[:10_000],
            "processed_content": processed,
            "language": self.language,
            "timestamp": datetime.now().isoformat()
        }

        # 重试机制
        for attempt in range(3):
            result = self.es_client.index_document(document)
            if result and result['result'] in ['created', 'updated']:
                return
            time.sleep(attempt)
        print(f"索引失败：{url}")
        return

    def _extract_links(self, page_url, html_content):
        """从HTML内容中提取链接"""
        soup = BeautifulSoup(html_content, 'html.parser')

        # 使用LinkFinder提取链接
        finder = LinkFinder(self.base_url, page_url)
        finder.feed(html_content)
        links = finder.page_links()

        # 补充从BeautifulSoup提取的链接
        for link in soup.find_all('a', href=True):
            url = parse.urljoin(page_url, link['href'])
            if get_domain_name(url) == self.domain_name:
                links.add(url)
        return links

    def _generate_headers(self, page_url):
        """生成动态请求头"""
        return {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Referer': f'{parse.urlparse(page_url).scheme}://{parse.urlparse(page_url).netloc}/',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept-Language': 'en-US,en;q=0.9',
            'Cache-Control': 'no-cache'
        }

    def _update_crawl_state(self, page_url, links):
        """更新爬取状态"""
        self.queue.remove(page_url)
        self.crawled.add(page_url)
        self._add_new_links(links)
        self._save_progress()

    def _add_new_links(self, links):
        """将新链接添加到队列"""
        for url in links:
            if url not in self.queue and url not in self.crawled:
                if get_domain_name(url) == self.domain_name:
                    self.queue.add(url)

    def _save_progress(self):
        """保存当前进度"""
        set_to_file(self.queue, self.queue_file)
        set_to_file(self.crawled, self.crawled_file)

    def _reach_crawl_limit(self):
        """检查是否达到爬取限制"""
        return self.crawled_count >= self.max_pages

    def _clear_queue(self):
        """清空爬取队列"""
        self.queue.clear()
        self._save_progress()

    def _handle_crawl_error(self, page_url):
        """处理爬取错误"""
        if page_url in self.queue:
            self.queue.remove(page_url)
        self._save_progress()
        with open(f'{self.project_name}/error.log', 'a') as f:
            f.write(f"{datetime.now().isoformat()}|{page_url}\n")


def create_project_dir(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def create_data_files(project_name, base_url):
    queue = os.path.join(project_name, 'queue.txt')
    crawled = os.path.join(project_name, 'crawled.txt')
    if not os.path.isfile(queue):
        with open(queue, 'w') as f:
            f.write(base_url + '\n')
    if not os.path.isfile(crawled):
        with open(crawled, 'w') as f:
            f.write('')
