"""Google News RSS public feed aggregator. No API key or Google login required."""
import datetime as dt, email.utils, hashlib, html, json, pathlib, re, urllib.parse, urllib.request, xml.etree.ElementTree as ET
ROOT=pathlib.Path(__file__).parent
FEEDS={
 '日経平均':'日経平均 株価 東証 市場',
 '不動産':'不動産 再開発 M&A 倒産 地価',
 '世界情勢':'国際情勢 外交 米中 欧州 ウクライナ',
 '金融市場':'為替 日銀 FRB 金利 債券',
 'ファッション':'アパレル ファッション 業績 買収 出店',
}
now=dt.datetime.now(dt.timezone(dt.timedelta(hours=9)))
path=ROOT/'data'/'news.json';path.parent.mkdir(exist_ok=True)
try: old=json.loads(path.read_text(encoding='utf-8'))['articles']
except (FileNotFoundError,ValueError,KeyError): old=[]
seen={a['id'] for a in old};new=[]
for category,query in FEEDS.items():
 url='https://news.google.com/rss/search?'+urllib.parse.urlencode({'q':query+' when:2d','hl':'ja','gl':'JP','ceid':'JP:ja'})
 try:
  req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0 MorningNewsReader/1.0'})
  with urllib.request.urlopen(req,timeout=25) as f: xml=f.read()
  items=ET.fromstring(xml).findall('./channel/item')
 except Exception as e:
  print(f'Feed error {category}: {e}');continue
 count=0
 for item in items:
  title=html.unescape(item.findtext('title') or '').strip()
  link=(item.findtext('link') or '').strip()
  source=item.find('source');source_name=source.text if source is not None else 'Google News RSS'
  description=html.unescape(re.sub('<[^>]+>',' ',item.findtext('description') or ''))
  description=re.sub(r'\s+',' ',description).strip()
  pub=item.findtext('pubDate') or ''
  try: stamp=email.utils.parsedate_to_datetime(pub).astimezone(dt.timezone(dt.timedelta(hours=9)))
  except Exception: stamp=now
  if not title or not link:continue
  identifier=hashlib.sha256((title+'|'+link).encode()).hexdigest()[:18]
  if identifier in seen:continue
  new.append({'id':identifier,'date':now.strftime('%Y-%m-%d'),'category':category,'title':title,'summary':description[:350] if description else '見出しと情報源を確認してください。','impact':'この記事が事業・市場に与える影響は、リンク先の原文で確認してください。','url':link,'source':source_name,'published':stamp.strftime('%Y-%m-%d %H:%M')})
  seen.add(identifier);count+=1
  if count>=2:break
print(f'Added {len(new)} articles')
all_articles=new+old
# Keep the most recent 60 calendar days of archives.
cutoff=(now.date()-dt.timedelta(days=60)).isoformat()
all_articles=[a for a in all_articles if a.get('date','')>=cutoff]
path.write_text(json.dumps({'updated_at':now.strftime('%Y-%m-%d %H:%M'),'articles':all_articles},ensure_ascii=False,indent=2),encoding='utf-8')
