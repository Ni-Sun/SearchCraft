import os
import re
import jieba
import hashlib
import time
import random
import nltk
from nltk.corpus import stopwords
from nltk.stem import PorterStemmer
from nltk.tokenize import word_tokenize
from fake_useragent import UserAgent
from urllib.error import HTTPError
from urllib.request import urlopen, Request
from link_finder import LinkFinder
from domain import *
from general import *
from datetime import datetime
from bs4 import BeautifulSoup
from urllib import parse
import requests
import requests.adapters
from requests.packages.urllib3.util.ssl_ import create_urllib3_context


# Sets to keep track of queued and crawled URLs
class Spider:
    def __init__(self, project_name, base_url, domain_name, language = 'en', max_pages=100):
        self.language = language
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
        self.stemmer = PorterStemmer()
        self._check_nltk_resources()

    def _check_nltk_resources(self):
        try:
            nltk.data.find('tokenizers/punkt')
        except LookupError:
            nltk.download('punkt', quiet=True)

        try:
            nltk.data.find('tokenizers/punkt_tab')
        except LookupError:
            nltk.download('punkt_tab', quiet=True)

        # 同时确保停用词资源存在
        try:
            nltk.data.find('corpora/stopwords')
        except LookupError:
            nltk.download('stopwords', quiet=True)


    def _initialize_text_processor(self):
        # 初始化停用词表（需要用户自行准备）
        self.stopwords = set()
        try:
            with open('stopwords.txt', 'r', encoding='utf-8') as f:
                for line in f:
                    self.stopwords.add(line.strip())
        except FileNotFoundError:
            print("未找到停用词文件，使用默认停用词表")
            self.stopwords = {'的', '了', '在', '是', '我', '有', '和', '就', '不', '人'}


    # 中文文本处理流水线
    def _process_chinese_text(self, raw_text):
        # 清洗HTML标签
        clean_text = re.sub(r'<[^>]+>', '', raw_text)
        # 中文分词
        words = jieba.lcut(clean_text)
        # 去除停用词和非中文字符
        filtered = [
            word.strip() for word in words
            if word.strip() and
               word not in self.stopwords and
               re.match(r'[\u4e00-\u9fa5]', word)
        ]
        return ' '.join(filtered)

    # 英文文本处理流水线
    # def _process_english_text(self, raw_text):
    #     # 清洗HTML标签
    #     clean_text = re.sub(r'<[^>]+>', '', raw_text)
    #
    #     # 转换小写
    #     text_lower = clean_text.lower()
    #
    #     # 移除特殊字符（保留字母、数字和空格）
    #     text_clean = re.sub(r'[^a-zA-Z0-9\s]', '', text_lower)
    #
    #     # 分词
    #     tokens = word_tokenize(text_clean)
    #
    #     # 去除停用词
    #     filtered = [
    #         word for word in tokens
    #         if word not in self.stopwords and len(word) > 2
    #     ]
    #
    #     # 词干提取
    #     stemmed = [self.stemmer.stem(word) for word in filtered]
    #
    #     return ' '.join(stemmed)

    def _process_english_text(self, raw_text):
        # 加强版HTML清洗
        clean_text = BeautifulSoup(raw_text, 'html.parser').get_text(' ', strip=True)

        # 预处理特殊格式
        text = clean_text.lower()
        text = re.sub(r'\b(https?://|www\.)\S+\b', ' ', text)  # 移除URL
        text = re.sub(r'@\w+', ' ', text)  # 移除@提及
        text = re.sub(r'#\w+', ' ', text)  # 移除标签

        # 处理技术术语粘连（驼峰命名转换）
        text = re.sub(r'([a-z])([A-Z])', r'\1 \2', text)  # CamelCase -> Camel Case
        text = re.sub(r'(\d+)([a-zA-Z])', r'\1 \2', text)  # 数字字母分离
        text = re.sub(r'([a-zA-Z])(\d+)', r'\1 \2', text)

        # 保留必要标点（如连字符、撇号）
        text = re.sub(r"[^a-zA-Z0-9'\-\.]", ' ', text)  # 保留基本字符

        # 增强分词处理
        try:
            # 使用改进的分词策略
            tokens = word_tokenize(text, language='english')
        except:
            # 备用分词方案
            tokens = re.findall(r"[\w'-]+|[.!?]", text)

        # 智能停用词过滤（保留否定形式）
        filtered = [
            word for word in tokens
            if word.lower() not in self.stopwords
               and len(word) > 1
               and not word.isdigit()
        ]

        # 词干提取优化（保留常见名词）
        common_nouns = {'data', 'analysis', 'system'}  # 自定义保留词表
        stemmed = []
        for word in filtered:
            if word in common_nouns:
                stemmed.append(word)
            else:
                stemmed.append(self.stemmer.stem(word))

        # 后处理修正
        processed = ' '.join(stemmed)
        processed = re.sub(r"\s+['-]\s+", '', processed)  # 修复分离的撇号
        processed = re.sub(r'\b(\w+)\s+-\s+(\w+)\b', r'\1-\2', processed)  # 恢复连字符单词
        return processed

    def save_original_content(self, url, content):
        # 创建下载目录
        download_dir = os.path.join(self.project_name, 'downloads')
        if not os.path.exists(download_dir):
            os.makedirs(download_dir)

        # 生成唯一文件名
        filename = url.replace('https://', '').replace('http://', '')
        filename = re.sub(r'[\\/*?:"<>|&\u200b]', '_', filename)[:150] # 限制文件名长度
        filename = re.sub(r'__', '_', filename)
        if not filename.endswith('.txt'):
            filename += '_org.txt'

        # 写入文件 xxx_org.txt
        filepath = os.path.join(download_dir, filename)
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
            print(f'Saved: {filename}')
        except Exception as e:
            print(f'Save failed: {filename} - {str(e)}')


        # 初始化文本处理器
        if not hasattr(self, 'stopwords'):
            self._initialize_text_processor()

        # 写入文件 xxx_c.txt / xxx_e.txt
        processed_filename = filename.replace('_org.txt', '_c.txt' if self.language == 'cn' else '_e.txt')
        try:
            processed = self._process_chinese_text(content) if self.language == 'cn' else self._process_english_text(content)
            processed_path = os.path.join(download_dir, processed_filename)

            with open(processed_path, 'w', encoding='utf-8') as f:
                f.write(processed)
        except Exception as e:
            print(f'Save failed: {processed_filename} - {str(e)}')

        if os.path.exists(download_dir):
            # 统计≥1KB的文件数量
            self.crawled_count = sum(
                1 for filename in os.listdir(download_dir)
                if os.path.isfile(os.path.join(download_dir, filename))
                and os.path.getsize(os.path.join(download_dir, filename)) >= 1024
            )

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


    # Saves queue data to project files
    def gather_links(self, page_url):
        """增强版链接抓取方法，包含反爬策略和结构化数据解析"""
        links = set()
        html_string = ''
        session = None

        try:
            # ================== 请求配置 ==================
            config = {
                'enable_js': False,  # 是否启用JS渲染
                'proxy': None,  # 代理服务器 {'http': 'x.x.x.x:xx', 'https': 'x.x.x.x:xx'}
                'timeout': 20,
                'max_retries': 2
            }

            # ================== 请求头生成 ==================
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.6943.127 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'zh-CN,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'no-cache',
                'Connection': 'keep-alive',
                'Pragma': 'no-cache',
                'Referer': 'https://www.cnblogs.com/',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'same-origin',
                'Sec-Fetch-User': '?1',
                'Upgrade-Insecure-Requests': '1'
            }

            # ================== TLS指纹对抗 ==================
            class TLSAdapter(requests.adapters.HTTPAdapter):
                def init_poolmanager(self, *args, **kwargs):
                    ctx = create_urllib3_context()
                    ctx.options |= 0x4  # OP_LEGACY_SERVER_CONNECT
                    kwargs['ssl_context'] = ctx
                    return super().init_poolmanager(*args, **kwargs)

            # ================== 创建会话 ==================
            session = requests.Session()
            session.mount('https://', TLSAdapter())

            # ================== 请求执行 ==================
            for attempt in range(config['max_retries']):
                try:
                    # 动态延迟控制
                    time.sleep(1)

                    # 代理配置
                    proxies = config['proxy'] if attempt > 0 else None

                    if config['enable_js']:
                        # 使用requests-html执行JS渲染
                        from requests_html import HTMLSession
                        js_session = HTMLSession()
                        response = js_session.get(
                            page_url,
                            headers=headers,
                            timeout=config['timeout'],
                            proxies=proxies
                        )
                        response.html.render(timeout=30)
                        html_string = response.html.html
                    else:
                        # 普通请求
                        response = session.get(
                            page_url,
                            headers=headers,
                            timeout=config['timeout'],
                            allow_redirects=True,
                            proxies=proxies
                        )
                        response.encoding = response.apparent_encoding
                        html_string = response.text

                    # 保存原始内容
                    self.save_original_content(page_url, html_string)
                    break  # 请求成功则跳出重试循环

                except (requests.exceptions.SSLError, requests.exceptions.ProxyError) as e:
                    print(f"安全错误 @ {page_url}: {str(e)}")
                    if attempt == config['max_retries'] - 1:
                        raise
                    time.sleep(5 ** (attempt + 1))  # 指数退避
                except requests.exceptions.RequestException as e:
                    print(f"请求失败 @ {page_url}: {str(e)}")
                    if attempt == config['max_retries'] - 1:
                        raise
                    time.sleep(2 ** (attempt + 1))

            # ================== 响应处理 ==================
            # 处理特殊状态码
            if response.status_code in [403, 429]:
                with open(f'{self.project_name}/blocked.log', 'a') as f:
                    f.write(f"{datetime.now().isoformat()}|{page_url}|{response.status_code}\n")
                return links

            # 更新Cookie
            if session.cookies:
                session.cookies.clear_expired_cookies()

            # ================== 内容解析 ==================
            # 使用BeautifulSoup解析
            soup = BeautifulSoup(html_string, 'html.parser')

            # 博客园特定解析
            if 'www.cnblogs.com' in self.domain_name:
                # 文章页解析
                if '/p/' in page_url:
                    article = {
                        'title': '',
                        'content': '',
                        'author': '',
                        'publish_time': '',
                        'url': page_url,
                        'crawl_time': datetime.now().isoformat()
                    }

                    # 标题提取
                    title_tag = soup.find('a', {'id': 'cb_post_title_url'}) or soup.find('h1', {'class': 'postTitle'})
                    if title_tag:
                        article['title'] = title_tag.get_text().strip()

                    # 正文提取
                    content_div = soup.find('div', {'id': 'cnblogs_post_body'}) or soup.find('div', {'class': 'post'})
                    if content_div:
                        # 清理无关元素
                        for elem in content_div.find_all(['script', 'style', 'footer']):
                            elem.decompose()
                        article['content'] = content_div.get_text().strip()

                    # 作者信息
                    author_div = soup.find('div', {'id': 'blog_post_info'})
                    if author_div:
                        author_link = author_div.find('a')
                        if author_link:
                            article['author'] = author_link.get_text().strip()

                    # 发布时间
                    time_span = soup.find('span', {'id': 'post-date'}) or soup.find('span', {'class': 'post-time'})
                    if time_span:
                        article['publish_time'] = time_span.get_text().strip()

                    # 保存结构化数据
                    if article['title']:  # 有效性检查
                        self.save_structured_data(article, page_url)

                # 分页处理
                pagination = soup.find('div', {'class': 'pager'})
                if pagination:
                    for link in pagination.find_all('a'):
                        href = link.get('href')
                        if href and not href.startswith('javascript'):
                            full_url = parse.urljoin(self.base_url, href)
                            links.add(full_url)

            # 通用链接发现
            finder = LinkFinder(self.base_url, page_url)
            finder.feed(html_string)
            links.update(finder.page_links())

        except Exception as e:
            print(f'严重错误 @ {page_url}: {str(e)}')
            import traceback
            traceback.print_exc()
            with open(f'{self.project_name}/error.log', 'a') as f:
                f.write(f"{datetime.now().isoformat()}|{page_url}|{str(e)}\n")
        finally:
            # 资源清理
            if session:
                session.close()
            return links

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
        # download_dir = os.path.join(self.project_name, 'downloads')
        # if os.path.exists(download_dir):
        #     self.crawled_count = len(os.listdir(download_dir))
