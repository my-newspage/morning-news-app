"""Refresh transport status from official pages; never infer normal service from a failed fetch."""
import datetime as dt, html, json, pathlib, re, unicodedata, urllib.request
from html.parser import HTMLParser

ROOT=pathlib.Path(__file__).parent
PATH=ROOT/'data/status.json'
JST=dt.timezone(dt.timedelta(hours=9))
JR='https://traininfo.jreast.co.jp/train_info/line.aspx?gid=1&lineid=yokohamaline'
TOKYU='https://www.tokyu.co.jp/unten2/unten.html'

class Text(HTMLParser):
 def __init__(self): super().__init__(); self.parts=[]
 def handle_data(self, data): self.parts.append(data)

def fetch(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=20) as response:
  body=response.read().decode('utf-8','replace')
 parser=Text();parser.feed(body)
 return ' '.join(parser.parts)

try: data=json.loads(PATH.read_text(encoding='utf-8'))
except (OSError,ValueError): data={}
now=dt.datetime.now(JST)
rail={'yokohama':{'status':'情報を確認できません','source':JR},
      'toyoko':{'status':'情報を確認できません','source':TOKYU}}
YAHOO={'yokohama':'https://transit.yahoo.co.jp/diainfo/31/0',
       'toyoko':'https://transit.yahoo.co.jp/diainfo/112/0'}
def yahoo_status(url, now):
 try:
  page=fetch(url)
  # Ignore the social post list: it can include old, unrelated, or contradictory reports.
  main=page.split('この路線に関するつぶやき',1)[0].split('に関するつぶやき',1)[0]
  m=re.search(r'(\d{1,2})月(\d{1,2})日\s*(\d{1,2})時(\d{1,2})分更新',main)
  if not m: return None
  month,day,hour,minute=map(int,m.groups())
  stamp=now.replace(month=month,day=day,hour=hour,minute=minute,second=0,microsecond=0)
  if stamp>now+dt.timedelta(minutes=5): stamp=stamp.replace(year=now.year-1)
  if now-stamp>dt.timedelta(hours=3): return None
  section=main[m.end():]
  status=re.search(r'列車遅延|運転見合わせ|運休|ダイヤ乱れ|平常運転',section)
  if not status: return None
  label=status.group()
  tail=section[status.end():].strip()
  detail=re.split(r'（\d{1,2}月\d{1,2}日\s*\d{1,2}時\d{1,2}分掲載）',tail,1)[0]
  detail=re.sub(r'\s+',' ',detail).strip()[:160]
  if label=='平常運転': detail=''
  return {'status':label,'detail':detail,'source':url,'source_name':'Yahoo!路線情報','source_updated_at':stamp.strftime('%Y-%m-%d %H:%M')}
 except Exception as error:
  print('Yahoo fetch failed:',url,error)
  return None

for key,url in YAHOO.items():
 result=yahoo_status(url,now)
 if result: rail[key]=result
# An official JR disruption takes priority; never infer normal from an unscoped page.
try:
 text=fetch(JR)
 section=text.split('運行情報・運休情報',2)[-1].split('振替輸送情報',1)[0]
 if rail['yokohama']['status']=='情報を確認できません' and '横浜線' in section and any(term in section for term in ('遅延','運転見合わせ','運休')):
  rail['yokohama']={'status':'運行に影響あり','detail':re.sub(r'\\s+',' ',section).strip()[:140],
                     'source':JR,'source_name':'JR東日本'}
except Exception as error: print('JR fetch failed:',error)
# Tokyu route data is rendered through JavaScript; Yahoo status remains attributed to Yahoo.
data['rail']=rail
data['rail_updated_at']=now.strftime('%Y-%m-%d %H:%M')
# Each lender publishes its own month label. Never relabel a stale source.
FLAT35='https://www.simulation.jhf.go.jp/flat35/kinri/index.php/rates/top/'
MUFG='https://www.bk.mufg.jp/kariru/jutaku/yuuguu/index.html'

class RateText(Text):
 def handle_starttag(self, tag, attrs):
  if tag=='img':
   alt=dict(attrs).get('alt') or ''
   if 'にお借り入れの場合' in alt:
    self.parts.append(alt)

def rate_text(body):
 for encoding in ('utf-8','euc_jp','cp932'):
  try:
   decoded=body.decode(encoding)
   break
  except UnicodeDecodeError:
   continue
 else: raise ValueError('Unrecognized rate-page encoding')
 parser=RateText()
 parser.feed(decoded)
 return ' '.join(unicodedata.normalize('NFKC',' '.join(parser.parts)).split())

def flat35_rate(page, month):
 heading='新機構団信付きの【フラット35】等の借入金利水準('+month+')'
 if heading not in page: return None
 section=page.split(heading,1)[1].split('【フラット20】',1)[0]
 result=re.search(r'【フラット35】\s*借入期間\s*:\s*21年以上35年以下\s*融資率\s*金利の範囲\s*最も多い金利\s*9割以下\s*年\s*[0-9.]+\s*%\s*[〜~]\s*(?:年\s*)?[0-9.]+\s*%\s*年\s*(\d{1,2}\.\d{1,3})\s*%',section)
 return result.group(1) if result else None

def mufg_rate(page, month):
 _, marker, tail=page.partition('新規お借り入れの金利')
 section, next_heading, _=tail.partition('お借り換えの金利')
 if not marker or not next_heading: return None
 dates_and_rates=re.findall(r'(20\d{2}年\d{1,2}月)\s*にお借り入れの場合\s*変動金利は\s*年\s*(\d{1,2}\.\d{1,3})\s*%', section)
 result=re.search(r'【ずーっと一律優遇コース】\s*適用金利\s*変動金利\s*年\s*(\d{1,2}\.\d{1,3})\s*%\s*\(\s*店頭表示金利',section)
 if not result or set(dates_and_rates)!={(month,result.group(1))}: return None
 return result.group(1)

def rate_page(url):
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
 with urllib.request.urlopen(req,timeout=12) as response:
  return rate_text(response.read())

def refresh_rates(data, now, read_page=rate_page):
 month=f'{now.year}年{now.month}月'
 saved=data.get('rates') or {}
 rates={}
 for key,url,parse,conditions in (
  ('flat35',FLAT35,flat35_rate,'21〜35年・融資率9割以下・新機構団信付きの最頻金利'),
  ('mufg',MUFG,mufg_rate,'新規借入・ずーっと一律優遇コース適用金利'),
 ):
  previous=saved.get(key) or {}
  prior_month=previous.get('month',data.get('rates_updated_at'))
  value=previous.get('percent') if prior_month==month else None
  if not value:
   try: value=parse(read_page(url),month)
   except Exception as error: print('Rate source unavailable:', key, error)
  if value:
   rates[key]={'percent':value,'conditions':conditions,'source':url,'month':month}
  else:
   rates[key]={'conditions':month+'分の金利は未確認','source':url}
 data['rates']=rates
 n=sum('percent' in rate for rate in rates.values())
 data['rates_updated_at']=month if n==2 else month+('（一部未確認）' if n else '（未確認）')

refresh_rates(data, now)

# Both figures are read from the publisher's own public page.
# Keep the last verified observation if extraction fails, with its original timestamp.
market=data.setdefault('market',{})
try:
 text=fetch('https://indexes.nikkei.co.jp/nkave/index/profile?cid=3&idx=nk225')
 match=re.search(r'日経平均株価\s+([0-9,]+\.[0-9]{2})\s+([+-]?[0-9.]+%)\s+([+-]?[0-9,]+\.[0-9]{2})\s+(20\d{2}\.\d{2}\.\d{2})\(\s*\*?\s*(\d{2}:\d{2}|前引|大引)\s*\)',text)
 if match:
  value,_,change,date,time=match.groups()
  market['nikkei']={'value':value,'change':change,'time':date.replace('.','-')+' '+time,'source':'https://indexes.nikkei.co.jp/nkave/index/profile?cid=3&idx=nk225'}
 else: print('Nikkei figure missing from source')
except Exception as error: print('Nikkei fetch failed:',error)
try:
 text=fetch('https://trust.sbishinseibank.co.jp/sp/market_rates/')
 match=re.search(r'米ドル/円\s+([0-9]+\.[0-9]+)\s+前日比\s+([+-]?[0-9]+\.[0-9]+)\s+更新日時\s+(20\d{2}/\d{2}/\d{2} \d{2}:\d{2})',text)
 if match:
  value,change,time=match.groups()
  market['usdjpy']={'value':value,'change':change,'time':time.replace('/','-'),'source':'https://trust.sbishinseibank.co.jp/sp/market_rates/'}
 else: print('USD/JPY figure missing from source')
except Exception as error: print('USD/JPY fetch failed:',error)
PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
