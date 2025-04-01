import os
import hashlib
import time
import random
from fake_useragent import UserAgent
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from link_finder import LinkFinder
from domain import *
from general import *
from datetime import datetime



# Sets to keep track of queued and crawled URLs
class Spider:
    def __init__(self, project_name, base_url, domain_name, max_pages=100):
        self.max_pages = max_pages
        self.crawled_count = 0
        self.project_name = project_name
        self.base_url = base_url
        self.domain_name = domain_name
        self.queue_file = self.project_name + '/queue.txt'
        self.crawled_file = self.project_name + '/crawled.txt'
        self.queue = set()
        self.crawled = set()
        self.boot()
        self.crawl_page('First spider', self.base_url)

    def save_original_content(self, url, content):
        # 创建下载目录
        download_dir = os.path.join(self.project_name, 'downloads')
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # 生成唯一文件名
        filename = url.replace('https://', '').replace('http://', '')
        filename = filename.replace('/', '_')[:150]  # 防止文件名过长
        # 移除或替换不支持的字符(文件名不能包含特殊字符,否则无法保存)
        invalid_chars = ['<', '>', ':', '"', '/', '\\', '|', '?', '*', '&']
        for char in invalid_chars:
            filename = filename.replace(char, '_')
        if not filename.endswith('.txt'):
            filename += '_org.txt'

        # 写入文件
        filepath = os.path.join(download_dir, filename)
        try:
            with open(filepath, 'w') as f:
                f.write(content)
            print(f'Saved: {filename}')
        except Exception as e:
            print(f'Save failed: {filename} - {str(e)}')

    # Creates directory and files for project on first run and starts the spider
    def boot(self):
        create_project_dir(self.project_name)
        create_data_files(self.project_name, self.base_url)
        self.queue = file_to_set(self.queue_file)
        self.crawled = file_to_set(self.crawled_file)


    def crawl_page(self, thread_name, page_url):
        if self.crawled_count >= self.max_pages:
            return

        try:
            if page_url not in self.crawled:
                print(f'{thread_name} now crawling {page_url}')
                links = self.gather_links(page_url)
                self.add_links_to_queue(links)
                self.queue.remove(page_url)
                self.crawled.add(page_url)
                self.update_files()

                # 达到限制时清空队列
                if self.crawled_count >= self.max_pages:
                    self.queue.clear()
                    set_to_file(self.queue, self.queue_file)
                # time.sleep(random.uniform(1, 7))  # 增加延迟

        except Exception as e:
            print(f'Critical error at {page_url}: {str(e)}')
            # 自动将失败URL移出队列
            if page_url in self.queue:
                self.queue.remove(page_url)
            self.update_files()

    def gather_links(self, page_url):
        finder = LinkFinder(self.base_url, page_url)  # 必须提前初始化
        html_string = ''

        try:
            # 增强型请求头
            headers = {
                'User-Agent': UserAgent().random,
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
                'Referer': 'https://www.google.com/',
                'DNT': '1'
            }
            req = Request(url=page_url, headers=headers, method='GET')

            with urlopen(req, timeout=10) as response:
                if 'text/html' in response.getheader('Content-Type'):
                    html_bytes = response.read()
                    # 增强编码检测
                    try:
                        html_string = html_bytes.decode('utf-8')
                    except UnicodeDecodeError:
                        html_string = html_bytes.decode('gb18030', errors='replace')

                    self.save_original_content(page_url, html_string)

                finder.feed(html_string)

        except HTTPError as e:
            print(f'HTTP {e.code} Error → {page_url}')
            # 知乎特定处理：403错误自动跳过
            if e.code == 403:
                with open('blocked_ips.txt', 'a') as f:
                    f.write(f'{datetime.now()} | {page_url}\n')
                return set()  # 返回空集合避免后续处理
        except Exception as e:
            print(f'严重错误 @ {page_url}: {str(e)}')
        finally:
            return finder.page_links()

    # Saves queue data to project files
    def add_links_to_queue(self, links):
        if self.crawled_count >= self.max_pages:
            return

        for url in links:
            if (url in self.queue) or (url in self.crawled):
                continue
            if self.domain_name != get_domain_name(url):
                continue
            self.queue.add(url)

    def update_files(self):
        set_to_file(self.queue, self.queue_file)
        set_to_file(self.crawled, self.crawled_file)
        download_dir = os.path.join(self.project_name, 'downloads')
        self.crawled_count = len(os.listdir(download_dir))
        # return flag
