"""Refresh transport status from official pages; never infer normal service from a failed fetch."""
import datetime as dt, html, json, pathlib, re, urllib.request
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
      'toyoko':{'status':'公式情報を確認','source':TOKYU}}
try:
 text=fetch(JR)
 section=text.split('運行情報・運休情報',2)[-1].split('振替輸送情報',1)[0]
 # Only mark normal when the live current-status section explicitly says so.
 if '平常運転' in section:
  rail['yokohama']['status']='平常運転'
 elif any(term in section for term in ('遅延','運転見合わせ','運休')):
  rail['yokohama']['status']='運行に影響あり'
  rail['yokohama']['detail']=re.sub(r'\s+',' ',section).strip()[:140]
except Exception as error: print('JR fetch failed:',error)
# Tokyu renders route status through JavaScript; link to official live information.
data['rail']=rail
data['rail_updated_at']=now.strftime('%Y-%m-%d %H:%M')
# Rates are month-specific; clear last month's rate rather than showing it as current.
month=now.strftime('%Y年%m月').replace('年0','年')
if data.get('rates_updated_at')!=month:
 data['rates']={}
 data['rates_updated_at']='当月の金利は未確認'

# Both figures are read from the publisher's own public page.
# Keep the last verified observation if extraction fails, with its original timestamp.
market=data.setdefault('market',{})
try:
 text=fetch('https://indexes.nikkei.co.jp/nkave/index/profile?cid=3&idx=nk225')
 match=re.search(r'日経平均株価\s+([0-9,]+\.[0-9]{2})\s+([+-]?[0-9.]+%)\s+([+-]?[0-9,]+\.[0-9]{2})\s+(20\d{2}\.\d{2}\.\d{2})\((\d{2}:\d{2}|前引)\)',text)
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
