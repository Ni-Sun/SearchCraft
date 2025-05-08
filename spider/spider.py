import os
import re
# import jieba
import hashlib
import time
import certifi
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
from urllib3.util.ssl_ import create_urllib3_context
from elasticsearch import Elasticsearch

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
        self.es_endpoint = "http://localhost:9200"
        self.es = Elasticsearch(
                [self.es_endpoint],
                verify_certs=False,
                ssl_show_warn=False
            )
        self._check_and_create_index()

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

    def _check_and_create_index(self):
        # 确保web_content索引存在
        if not self.es.indices.exists(index="web_content"):
            index_config = {
                "mappings": {
                    "properties": {
                        "content": {
                            "type": "text",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "language": {
                            "type": "text",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "processed_content": {
                            "type": "text",
                            "analyzer": "ik_smart",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        },
                        "timestamp": {"type": "date"},
                        "url": {
                            "type": "text",
                            "fields": {
                                "keyword": {"type": "keyword", "ignore_above": 256}
                            }
                        }
                    }
                },
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1
                }
            }
            self.es.indices.create(index="web_content", body=index_config)
            print("已创建web_content索引")


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

    # 新增ES文档写入方法
    def _index_to_es(self, url, processed_text, original_content):
        document = {
            "url": url,
            "content": original_content,
            "processed_content": processed_text,
            "language": self.language,
            "timestamp": datetime.now().isoformat()
        }

        try:
            response = self.es.index(
                index="web_content",
                document=document,
                pipeline="ent-search-generic-ingestion"
            )
            if response['result'] not in ['created', 'updated']:
                print(f"索引失败：{url}")
        except Exception as e:
            print(f"ES写入异常：{str(e)}")
            # 失败重试逻辑
            self._retry_failed_document(document)

    def _retry_failed_document(self, document, max_retries=3):
        for attempt in range(max_retries):
            try:
                self.es.index(
                    index="web_content",
                    document=document,
                    timeout='30s'
                )
                return True
            except:
                time.sleep(2 ** attempt)
        return False

    # 对处理结果进行去重
    def Deduplication(self, content):
        s=set()
        for i in content:
            s.add(i)
        content=list(s)
        return

    # 中文文本处理流水线
    def _process_chinese_text(self, raw_text):
        # 清洗HTML标签
        clean_text = re.sub(r'<[^>]+>', '', raw_text)

        try:
            # 通过ES的_analyze接口进行分词和停用词处理
            response = requests.post(
                f"{self.es_endpoint}/_analyze",
                json={
                    "analyzer": "ik_max_word",  # 使用IK分词器
                    "text": clean_text
                },
                timeout=5,
                headers={'Connection': 'close'},  # 明确关闭连接
                verify=False  # 如果是本地测试可跳过证书验证
            )

            if response.status_code == 200:
                # 提取分词结果并过滤
                tokens = [token['token'] for token in response.json()['tokens']]
                filtered = [
                    word for word in tokens
                    if word.strip() and
                       word not in self.stopwords and
                       re.match(r'[\u4e00-\u9fa5]', word)
                ]
                self.Deduplication(filtered)
                return ' '.join(filtered)
            else:
                print(f"ES分词失败：{response.text}")
                return ""

        except Exception as e:
            print(f"ES连接异常：{str(e)}")
            # 降级方案：使用简易分词
            return ' '.join(re.findall(r'[\u4e00-\u9fa5]+', clean_text))


    # 英文文本处理流水线
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

        self.Deduplication(processed)
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
            return  # 如果原始内容保存失败，终止后续操作


        # 初始化文本处理器
        if not hasattr(self, 'stopwords'):
            self._initialize_text_processor()

        # 写入文件 xxx_c.txt / xxx_e.txt
        processed_filename = filename.replace('_org.txt', '_c.txt' if self.language == 'cn' else '_e.txt')
        try:
            processed = self._process_chinese_text(content) if self.language == 'cn' else self._process_english_text(content)
            processed_path = os.path.join(download_dir, processed_filename)

            # 写入Elasticsearch
            self._index_to_es(url, processed, content)

            with open(processed_path, 'w', encoding='utf-8') as f:
                f.write(processed)
        except Exception as e:
            print(f'Save failed: {processed_filename} - {str(e)}')

        # 统计≥1KB的文件数量
        if os.path.exists(download_dir):
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
                'Referer': f'{urlparse(page_url).scheme}://{urlparse(page_url).netloc}/',  # 动态生成当前域名
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
                            proxies=proxies,
                            verify=certifi.where()  # 使用certifi的证书库
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
