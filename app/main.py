
import sys,time,json,threading,webbrowser
from pathlib import Path
from http.server import ThreadingHTTPServer,SimpleHTTPRequestHandler
from urllib.parse import urlparse
from datetime import datetime
import requests,feedparser

PORT=8765

THEMES={
"한국-HBM":[
("SK하이닉스","000660","000660.KS","KR"),
("한미반도체","042700","042700.KS","KR"),
("삼성전자","005930","005930.KS","KR"),
("테크윙","089030","089030.KQ","KR"),
("ISC","095340","095340.KQ","KR")
],
"한국-원전":[
("두산에너빌리티","034020","034020.KS","KR"),
("한전기술","052690","052690.KS","KR"),
("한전KPS","051600","051600.KS","KR"),
("비에이치아이","083650","083650.KQ","KR")
],
"한국-금융배당":[
("KB금융","105560","105560.KS","KR"),
("기업은행","024110","024110.KS","KR"),
("신한지주","055550","055550.KS","KR")
],
"미국-AI반도체":[
("엔비디아","NVDA","NVDA","US"),
("AMD","AMD","AMD","US"),
("브로드컴","AVGO","AVGO","US"),
("마이크론","MU","MU","US"),
("마이크로소프트","MSFT","MSFT","US")
],
"미국-빅테크":[
("애플","AAPL","AAPL","US"),
("아마존","AMZN","AMZN","US"),
("메타","META","META","US"),
("테슬라","TSLA","TSLA","US")
],
"미국-ETF":[
("TQQQ","TQQQ","TQQQ","US"),
("SOXL","SOXL","SOXL","US"),
("JEPQ","JEPQ","JEPQ","US"),
("JEPI","JEPI","JEPI","US"),
("SCHD","SCHD","SCHD","US"),
("VNQ","VNQ","VNQ","US")
]
}

def base(*parts):
    b=Path(sys._MEIPASS) if getattr(sys,"frozen",False) else Path(__file__).resolve().parent
    return b.joinpath(*parts)

def infer_theme(title,market):
    x=title.lower()
    if market=="KR":
        if any(k in x for k in ["hbm","메모리","반도체"]): return "한국-HBM"
        if any(k in x for k in ["원전","원자력","체코"]): return "한국-원전"
        if any(k in x for k in ["배당","주주환원","금융"]): return "한국-금융배당"
        return "한국-HBM"
    if any(k in x for k in ["nvidia","amd","broadcom","micron","chip","semiconductor","ai"]): return "미국-AI반도체"
    if any(k in x for k in ["apple","amazon","meta","tesla","microsoft","big tech"]): return "미국-빅테크"
    if any(k in x for k in ["etf","tqqq","soxl","jepq","jepi","schd","vnq"]): return "미국-ETF"
    return "미국-AI반도체"

def news_strength(title):
    s=50
    positives=["수주","계약","승인","급증","투자 확대","공급 확대","사상 최대","record","surge","beats","approval","contract","partnership"]
    negatives=["우려","감소","적자","중단","취소","규제","misses","lawsuit","ban","decline","cut"]
    for k in positives:
        if k.lower() in title.lower(): s+=7
    for k in negatives:
        if k.lower() in title.lower(): s-=8
    return max(20,min(95,s))

def fetch_news(query,market,hl,gl,ceid):
    try:
        r=requests.get("https://news.google.com/rss/search",
            params={"q":query,"hl":hl,"gl":gl,"ceid":ceid},
            headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        feed=feedparser.parse(r.content)
        out=[]
        for i,e in enumerate(feed.entries[:12]):
            title=e.get("title","")
            out.append({
                "id":f"{market}{i}",
                "title":title,
                "link":e.get("link",""),
                "published":e.get("published",""),
                "source":(e.get("source") or {}).get("title","Google News"),
                "theme":infer_theme(title,market),
                "market":market,
                "newsScore":news_strength(title)
            })
        return out
    except:
        return []

def quote(symbol):
    try:
        r=requests.get(f"https://query1.finance.yahoo.com/v8/finance/chart/{symbol}",
            params={"range":"5d","interval":"5m"},
            headers={"User-Agent":"Mozilla/5.0"},timeout=10)
        result=r.json()["chart"]["result"][0]
        meta=result.get("meta",{})
        price=meta.get("regularMarketPrice") or meta.get("previousClose") or 0
        prev=meta.get("previousClose") or 0
        change=((price-prev)/prev*100) if prev else 0
        closes=[x for x in ((result.get("indicators",{}).get("quote") or [{}])[0].get("close") or []) if x is not None]
        trend=((closes[-1]-closes[0])/closes[0]*100) if len(closes)>1 and closes[0] else 0
        return {
            "price":price,
            "change":change,
            "volume":meta.get("regularMarketVolume") or 0,
            "currency":meta.get("currency","KRW"),
            "trend":trend,
            "source":"Yahoo Finance",
            "marketState":meta.get("marketState","")
        }
    except:
        return {"price":0,"change":0,"volume":0,"currency":"KRW","trend":0,"source":"조회 실패","marketState":""}

def calc_score(q,news_score,rank):
    s=34
    s+=max(-15,min(24,q["change"]*3.1))
    s+=max(-12,min(20,q["trend"]*2.5))
    s+=(8 if q["volume"] else 0)
    s+=max(0,12-rank*2)
    s+=(news_score-50)*0.4
    return max(10,min(98,round(s)))

def reason_for(stock):
    reasons=[]
    if stock["change"]>=3: reasons.append("당일 상승률 강함")
    elif stock["change"]>0: reasons.append("당일 상승 유지")
    if stock["trend"]>=3: reasons.append("5일 추세 강함")
    elif stock["trend"]>0: reasons.append("5일 추세 상승")
    if stock["volume"]>0: reasons.append("거래량 확인")
    if stock["newsScore"]>=60: reasons.append("뉴스 강도 높음")
    if stock.get("leader"): reasons.append("테마 내 대장주")
    return reasons[:4] or ["시장 데이터 참고"]

def build_payload():
    news=(
        fetch_news("HBM OR 반도체 OR 원전 OR 배당 주식","KR","ko","KR","KR:ko")
        + fetch_news("NVIDIA OR AMD OR Broadcom OR AI stocks OR Tesla OR Microsoft OR US stocks","US","en-US","US","US:en")
    )
    grouped={}
    for n in news:
        grouped.setdefault(n["theme"],[]).append(n)

    all_rows=[]
    theme_rows={}
    for theme,items in THEMES.items():
        related_news=grouped.get(theme,[])
        avg_news=round(sum(n["newsScore"] for n in related_news)/len(related_news)) if related_news else 50
        rows=[]
        for i,(name,code,symbol,market) in enumerate(items):
            q=quote(symbol)
            row={
                "name":name,"code":code,"symbol":symbol,"market":market,
                "theme":theme,"newsScore":avg_news,**q
            }
            row["score"]=calc_score(q,avg_news,i)
            rows.append(row)
        rows.sort(key=lambda x:(x["score"],x["volume"]),reverse=True)
        if rows:
            rows[0]["leader"]=True
        for r in rows:
            r["reasons"]=reason_for(r)
        theme_rows[theme]=rows
        all_rows.extend(rows)

    top_all=sorted(all_rows,key=lambda x:(x["score"],x["volume"]),reverse=True)[:10]
    top_kr=sorted([x for x in all_rows if x["market"]=="KR"],key=lambda x:(x["score"],x["volume"]),reverse=True)[:10]
    top_us=sorted([x for x in all_rows if x["market"]=="US"],key=lambda x:(x["score"],x["volume"]),reverse=True)[:10]
    featured=top_all[0] if top_all else None

    news_cards=[]
    for n in news:
        stocks=theme_rows.get(n["theme"],[])[:5]
        news_cards.append({**n,"stocks":stocks,"leader":stocks[0] if stocks else None})

    urgent=[n for n in news_cards if n["newsScore"]>=57][:6]
    return {
        "featured":featured,
        "topAll":top_all,
        "topKR":top_kr,
        "topUS":top_us,
        "news":news_cards,
        "urgent":urgent,
        "updatedAt":datetime.now().isoformat(timespec="seconds")
    }

class Handler(SimpleHTTPRequestHandler):
    def __init__(self,*args,**kwargs):
        super().__init__(*args,directory=str(base("web")),**kwargs)
    def log_message(self,*args): pass
    def do_GET(self):
        if urlparse(self.path).path=="/api/data":
            body=json.dumps(build_payload(),ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.send_header("Content-Length",str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()

if __name__=="__main__":
    server=ThreadingHTTPServer(("127.0.0.1",PORT),Handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    webbrowser.open(f"http://127.0.0.1:{PORT}")
    while True:
        time.sleep(3600)
