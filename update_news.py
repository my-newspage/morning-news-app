"""Focused public RSS brief; no credentials or AI summary service required."""
import datetime as dt
import email.utils
import hashlib
import html
import json
import pathlib
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

ROOT = pathlib.Path(__file__).parent
JST = dt.timezone(dt.timedelta(hours=9))
NOW = dt.datetime.now(JST)
PATH = ROOT / 'data/news.json'
EXCLUDE = re.compile(r'クイズ|占い|ランキング|まとめ|一覧|求人|レディース|ウィメンズ|女性限定|婦人服|写真\d+/\d+', re.I)
LANES = [
    ('金融市場', '', '(日銀 OR FRB OR 金利 OR 株式市場 OR 債券市場) when:2d', 2, ''),
    ('世界情勢', '', '(国際情勢 OR 世界経済 OR 外交 OR ウクライナ OR 気候会議) when:2d', 2, ''),
    ('不動産', '', '不動産 (住宅 OR マンション OR 再開発 OR 中古 OR 地価) (発表 OR 調査) when:4d', 3, ''),
]

def get(url):
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0 MorningNewsReader/2.0'})
    with urllib.request.urlopen(req, timeout=25) as response:
        return response.read()

def feed(query):
    url = 'https://news.google.com/rss/search?' + urllib.parse.urlencode(
        {'q': query, 'hl': 'ja', 'gl': 'JP', 'ceid': 'JP:ja'})
    return ET.fromstring(get(url)).findall('./channel/item')

def fashion_articles():
    found = []
    # Both sources link to the original article and provide its actual thumbnail.
    try:
        page = get('https://www.houyhnhnm.jp/news/').decode('utf-8', 'ignore')
        cards = re.finditer(r'<a href="(https://www\.houyhnhnm\.jp/news/\d+/)"[^>]*>\s*<div class="img">\s*<img data-original="([^"]+)" alt="([^"]+)".*?<time[^>]+data-time="([^"]+)"', page, re.S)
        for card in cards:
            url, image, title, stamp = card.groups()
            published = dt.datetime.fromisoformat(stamp).astimezone(JST)
            if NOW - published > dt.timedelta(days=7) or EXCLUDE.search(title):
                continue
            found.append(make_fashion(html.unescape(title), url, 'HOUYHNHNM', published, image, '元記事で商品の詳細を確認してください。'))
    except Exception as exc:
        print(f'Fashion source error HOUYHNHNM: {exc}')
    try:
        items = ET.fromstring(get('https://www.fashionsnap.com/rss.xml')).findall('./channel/item')
        for item in items:
            title = html.unescape(item.findtext('title') or '').strip()
            url = item.findtext('link') or ''
            if not title or not url or EXCLUDE.search(title):
                continue
            published = email.utils.parsedate_to_datetime(item.findtext('pubDate')).astimezone(JST)
            if NOW - published > dt.timedelta(days=7):
                continue
            description = html.unescape(item.findtext('description') or '')
            match = re.search(r'<img[^>]+src="(https://[^"]+)"', description)
            if not match:
                continue
            summary = re.sub(r'\s+', ' ', re.sub('<[^>]+>', ' ', description)).strip()
            summary = summary.replace('このコンテンツは FASHIONSNAP が配信しています。', '').strip()[:180]
            found.append(make_fashion(title, url, 'FASHIONSNAP', published, match.group(1), summary))
    except Exception as exc:
        print(f'Fashion source error FASHIONSNAP: {exc}')
    return sorted(found, key=lambda a: a['published'], reverse=True)

def make_fashion(title, url, source, published, image, summary):
    return {'id': hashlib.sha256(url.encode()).hexdigest()[:18], 'date': NOW.strftime('%Y-%m-%d'),
            'category': 'ファッション', 'title': title, 'summary': summary, 'url': url,
            'image': image, 'source': source, 'published': published.strftime('%Y-%m-%d %H:%M'),
            'impact': '価格・発売日・在庫は元記事とブランド公式情報で確認してください。'}

def parse(item, category, pattern):
    title = html.unescape(item.findtext('title') or '').strip()
    link = (item.findtext('link') or '').strip()
    source = item.find('source')
    publisher = source.text.strip() if source is not None and source.text else 'Google News RSS'
    if not title or not link or EXCLUDE.search(title):
        return None
    try:
        published = email.utils.parsedate_to_datetime(item.findtext('pubDate')).astimezone(JST)
    except (TypeError, ValueError):
        return None
    if published > NOW + dt.timedelta(hours=1) or NOW - published > dt.timedelta(days=7):
        return None
    description = html.unescape(re.sub('<[^>]+>', ' ', item.findtext('description') or ''))
    summary = re.sub(r'\s+', ' ', description).strip()[:260] or '見出しと出典を確認してください。'
    return {
        'id': hashlib.sha256((title + '|' + link).encode()).hexdigest()[:18],
        'date': NOW.strftime('%Y-%m-%d'), 'category': category, 'title': title,
        'summary': summary, 'url': link, 'source': publisher,
        'published': published.strftime('%Y-%m-%d %H:%M'),
        'impact': '価格・発売日・販売店・在庫はリンク先の公式情報で確認してください。' if category == 'ファッション' else '詳細は出典で確認してください。',
    }

try:
    old = json.loads(PATH.read_text(encoding='utf-8')).get('articles', [])
except (FileNotFoundError, ValueError):
    old = []
seen = {a['id'] for a in old}
new = []
fashion = fashion_articles()
for lane, quota, pattern in [
    ('靴', 2, r'スニーカー|シューズ|靴|ローファー|MOC|ニューバランス|ミズノ|Vans|コンバース|HOKA'),
    ('小物', 1, r'バッグ|財布|ウォレット|腕時計|帽子|キャップ|眼鏡|サングラス'),
    ('服', 1, r'ジャケット|ニット|スウェット|シャツ|コート|パンツ|Tシャツ')]:
    count = 0
    for article in fashion:
        if article['id'] in seen or not re.search(pattern, article['title'], re.I):
            continue
        new.append(article)
        seen.add(article['id'])
        count += 1
        if count >= quota:
            break
for category, lane, query, quota, pattern in LANES:
    try:
        candidates = [parse(item, category, pattern) for item in feed(query)]
    except Exception as exc:
        print(f'Feed error {category}/{lane}: {exc}')
        continue
    candidates = sorted((a for a in candidates if a), key=lambda a: a['published'], reverse=True)
    count = 0
    for article in candidates:
        if article['id'] in seen:
            continue
        new.append(article)
        seen.add(article['id'])
        count += 1
        if count >= quota:
            break

cutoff = (NOW.date() - dt.timedelta(days=60)).isoformat()
articles = new + [a for a in old if a.get('date', '') >= cutoff]
sales = []
if dt.date(2026, 11, 20) <= NOW.date() <= dt.date(2026, 11, 26):
    sales = [
        {'title': 'ユニクロ感謝祭', 'summary': '11月20〜26日開催。メンズのヒートテック、フリースなどが対象。サイズ別在庫は公式ページで確認。', 'url': 'https://www.uniqlo.com/jp/ja/special-feature/kanshasai'},
        {'title': 'GU感謝祭', 'summary': '11月20〜26日開催。メンズ冬物などがアプリ会員向け特価。価格・在庫は公式ページで確認。', 'url': 'https://www.gu-global.com/jp/ja/feature/special/men?tagCategory=outer'},
    ]
PATH.write_text(json.dumps({'updated_at': NOW.strftime('%Y-%m-%d %H:%M'), 'articles': articles,
                            'sales': sales, 'today_count': len(new)}, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'Added {len(new)} articles; fashion {sum(a["category"] == "ファッション" for a in new)}')
