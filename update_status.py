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
PATH.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
