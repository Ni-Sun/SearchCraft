max_pages = 20  # 设置最大爬取页面数

# 配置多个爬虫任务
CRAWLER_CONFIGS = [
    # CN
    {
        'name': 'cnblogs',     # 博客园
        'homepage': 'https://www.cnblogs.com/',
        'max_pages': max_pages,  # 控制爬取数量
        'language': 'cn',  # en/cn
        'threads': 4,
        'delay': (1, 3)  # 自定义延迟范围
    },
    {
        'name': 'baidu',      # 百度
        'homepage': 'https://www.baidu.com',
        'max_pages': max_pages,
        'language': 'cn',  # en/cn
        'threads': 4
    },
    {
        'name': 'weather_china',    # 中国天气网
        'homepage': 'http://www.weather.com.cn',
        'max_pages': max_pages,
        'language': 'cn',  # en/cn
        'threads': 4
    },
    {
        'name': 'lianjia',      # 链家
        'homepage': 'https://www.lianjia.com',
        'max_pages': max_pages,
        'language': 'cn',  # en/cn
        'threads': 4
    },
    {
        'name': 'bilibili',     # 哔哩哔哩
        'homepage': 'https://www.bilibili.com',
        'max_pages': max_pages,
        'language': 'cn',  # en/cn
        'threads': 4
    },
    {
        'name': 'sina_news',     # 新浪
        'homepage': 'https://news.sina.com.cn',
        'max_pages': max_pages,
        'language': 'cn',  # en/cn
        'threads': 4
    },



    # ENG
    {
        'name': 'wiki',     # Wikipedia
        'homepage': 'https://en.wikipedia.org',
        'max_pages': max_pages,
        'language': 'en',  # en/cn
        'threads': 4
    },
    {
        'name': 'IMDb',     # IMDb
        'homepage': 'https://www.imdb.com',
        'max_pages': max_pages,
        'language': 'en',  # en/cn
        'threads': 4
    },
    {
        'name': 'github',     # GitHub
        'homepage': 'https://github.com',
        'max_pages': max_pages,
        'language': 'en',  # en/cn
        'threads': 4
    },
    {
        'name': 'reddit',     # Reddit
        'homepage': 'https://www.reddit.com',
        'max_pages': max_pages,
        'language': 'en',  # en/cn
        'threads': 4
    },
    {
        'name': 'ebay',     # eBay
        'homepage': 'https://www.ebay.com',
        'max_pages': max_pages,
        'language': 'en',  # en/cn
        'threads': 4
    },
    {
        'name': 'BBC',     # BBC
        'homepage': 'https://www.bbc.com/news',
        'language': 'en',  # en/cn
        'max_pages': max_pages,
        'threads': 4
    },
    {
        'name': 'commcon_crawl',     # Common Crawl
        'homepage': 'https://commoncrawl.org',
        'language': 'en',  # en/cn
        'max_pages': max_pages,
        'threads': 4
    },
]
