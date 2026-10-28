"""Split the ForecastBench market questions into theme files for research.

Writes data/benchmarks/themes/<theme>.json, each a list of
{id, source, question, resolution_criteria, market_resolution_criteria,
 background, close} - freeze_datetime_value (the market price) is STRIPPED:
the m_research protocol bans consulting market prices.
"""
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
QS = json.loads((ROOT / "data/benchmarks/2026-10-25-llm.json").read_text(encoding="utf-8"))
OUT = ROOT / "data/benchmarks/themes"
OUT.mkdir(exist_ok=True)

MARKET = ("kalshi", "manifold", "metaculus", "polymarket")


def theme(q):
    t = q["question"]
    tl = t.lower()
    # ordered rules; first hit wins
    if re.search(r"CPI|federal funds|Federal Reserve|Fed (increase|Hike)|payrolls|unemployment|Wall Street bonus|asking rent|gas prices|Hike.Pause.Hike", t, re.I):
        return "econ_fed"
    if re.search(r"WTI|Crude Oil|Ethereum|Bitcoin|FDV|S&P 500|Musk's net worth|Euro appreciate|Iranian rial|Magnificent Seven|stock market crash|billionaires", t, re.I):
        return "markets_crypto"
    if re.search(r"Taipei|Taichung|Tainan|Kaohsiung|New Taipei|Yilan|Hsinchu|Taitung|Penghu|Lienchiang|Taiwan local", t, re.I):
        return "taiwan"
    if re.search(r"Hormuz|Iran|Houthi|Perim|Saudi Oil|Israel|Knesset|Ben Gvir|Netanyahu|Yemen|strike 8 countries", t, re.I):
        return "mideast"
    if re.search(r"Russia|Ukraine|Vodianske|Kostyantynivka|Sudan|Burhan|Cuba|Maduro|Venezuela|Afghanistan|Taliban", t, re.I):
        return "conflicts"
    if re.search(r"Nigeria|Akwa Ibom|Kaduna|Ebonyi|Adamawa|Oyo State|Spanish general|PSOE|\bPP\b|Romania|Le Pen|Baja California|Zacatecas|Johannesburg|Switzerland|AfD|Moraes|Duterte|Secretary-General of UN|South Sudan|Grynspan", t, re.I):
        return "intl_politics"
    if re.search(r"Senate|governor|governorship|House race|House seat|House election|midterm|Attorney General race|Lieutenant Governor|Blue (tsunami|wave)|Amendment 3|CA-07|AK-AL|turnout|Kamala", t, re.I):
        return "us_elections"
    if re.search(r"Oscar|Grammy|Critics Choice|Rotten Tomatoes|Billboard|Spider-Man|Bad Bunny|film releases|Hunger Games|I Play Rocky|Worlds 2026|NFC South|pro football|Pac-12|Sweeney|Followers|Professor Layton|top artist", t, re.I):
        return "entertainment_sports"
    if re.search(r"\bAI\b|Anthropic|coding model|Waymo|LLM|transistors|Hugging Face|kill switch|chips|PayPal|data center|Millennium Prize", t, re.I):
        return "ai_tech"
    if re.search(r"Alito|FISA|shutdown|Strzok|deport|Gold Cards|Judge|Mike Johnson|Speaker|Section 301|trade agreement|Clean Air Act|airports|screwworm|cage-free|psilocybin|semaglutide|moxidectin|FURA|aerial taxis|World Cup|wastewater|septic", t, re.I):
        return "us_policy_misc"
    return "misc_data"


groups = {}
for q in QS["questions"]:
    if q["source"] not in MARKET or isinstance(q["id"], list):
        continue
    groups.setdefault(theme(q), []).append({
        "id": q["id"], "source": q["source"], "question": q["question"],
        "resolution_criteria": q.get("resolution_criteria"),
        "market_resolution_criteria": q.get("market_info_resolution_criteria"),
        "background": (q.get("background") or "")[:900],
        "close": q.get("market_info_close_datetime"),
    })

for name, qs in sorted(groups.items()):
    (OUT / f"{name}.json").write_text(json.dumps(qs, indent=1), encoding="utf-8")
    print(f"{name:22s} {len(qs)}")
print("total", sum(len(v) for v in groups.values()))
