![](http://i.imgur.com/wYi2CkD.png)


## 功能

- 多线程爬取
- 支持中英文网站
- 动态限速
- 智能队列补充机制
- 支持代理和反爬策略



## 配置&运行

运行前需要安装:

```text
beautifulsoup4 - 用于解析HTML内容
jieba - 用于中文分词
nltk - 用于自然语言处理
fake_useragent - 用于生成随机的User-Agent
requests - 用于发送HTTP请求
requests-html - 用于执行JavaScript渲染
```

可以执行以下命令来安装这些库

`pip install beautifulsoup4 jieba nltk fake_useragent requests requests-html`

<br>

运行main.py会生成crawler文件夹, 其下有多个xxx-crawler文件夹, 对应不同的网站

<img src="./img/2025-04-02_23-10-26.png" alt="Description" style="max-width: 80%; height: auto;">

若爬取中文网站, 会生成xxx_org.txt 和 xxx_c.txt文件

<img src="./img/2025-04-02_23-10-48.png" alt="Description" style="max-width: 80%; height: auto;">

若爬取英文网站, 会生成xxx_org.txt 和 xxx_e.txt文件

<img src="./img/2025-04-02_23-11-11.png" alt="Description" style="max-width: 80%; height: auto;">

部分网页较好爬取,爬取失败率较低, 爬取速度较快; 部分网页不好爬取,爬取失败率较高, 爬取速度较慢(因此可能会存在 有acb_org.txt文件, 但是没有abc_c.txt文件 的情况)

有的网站无法爬取, 如非必要, 可以换个网站爬取

<br>

配置要爬取哪些网站在`configs.py`中修改



## 目录结构
- main.py：主程序入口
- spider.py：爬虫核心逻辑
- domain.py：域名解析工具
- general.py：通用文件操作工具
- link_finder.py：链接解析工具
- configs.py：爬虫配置文件



### Links

- [Support thenewboston](https://www.patreon.com/thenewboston)
- [thenewboston.com](https://thenewboston.com/)
- [Facebook](https://www.facebook.com/TheNewBoston-464114846956315/)
- [Twitter](https://twitter.com/bucky_roberts)
- [Google+](https://plus.google.com/+BuckyRoberts)
- [reddit](https://www.reddit.com/r/thenewboston/)
