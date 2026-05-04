import ssl
import os
 
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["CURL_CA_BUNDLE"] = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
 
import time
import random
import json
import socket
import requests
import feedparser
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path
 
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
 
_old_getaddrinfo = socket.getaddrinfo
def _new_getaddrinfo(*args, **kwargs):
    res = _old_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET]
socket.getaddrinfo = _new_getaddrinfo
 
st.set_page_config(
    page_title="High-Frequency Sports EV+ Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)
 
st.markdown("""
<style>
html, body, [data-testid="stAppViewContainer"] * { color: #FFFFFF !important; }
.stMarkdown, .stText, p, span, label, div { color: #FFFFFF !important; }
h1, h2, h3, h4, h5, h6 { color: #FFFFFF !important; font-weight: bold !important; }
.stButton button { color: #FFFFFF !important; }
[data-testid="stDataFrame"] table, [data-testid="stTable"] table {
    background: #0f172a !important; color: #FFFFFF !important;
}
[data-testid="stDataFrame"] th, [data-testid="stDataFrame"] td,
[data-testid="stTable"] th, [data-testid="stTable"] td {
    background: #111827 !important; color: #FFFFFF !important;
    border-color: #2a2d3e !important;
}
.stApp { background-color: #0e1117 !important; color: #FFFFFF !important; }
[data-testid="stSidebar"] { background-color: #0a0e27 !important; }
[data-testid="stSidebar"] * { color: #FFFFFF !important; }
.stTabs [role="tab"] { color: #FFFFFF !important; font-weight: bold; }
.stTabs [role="tab"][aria-selected="true"] {
    color: #00D9FF !important; border-bottom: 3px solid #00D9FF !important;
}
.metric-box {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f172a 100%);
    border: 2px solid #00D9FF; border-radius: 8px;
    padding: 20px; margin: 10px 0;
}
.metric-title { font-size: 12px; color: #888; font-weight: bold;
    text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 28px; color: #00D9FF; font-weight: bold; margin-top: 5px; }
.api-badge-live {
    background: #0e2a1a; border: 1px solid #22c55e; color: #22c55e;
    font-size: 11px; font-weight: 700; padding: 2px 10px;
    border-radius: 20px; letter-spacing: .6px;
}
.api-badge-warn {
    background: #1a1a0a; border: 1px solid #f59e0b; color: #f59e0b;
    font-size: 11px; font-weight: 700; padding: 2px 10px;
    border-radius: 20px; letter-spacing: .6px;
}
.api-badge-error {
    background: #2d0a0a; border: 1px solid #ef4444; color: #ef4444;
    font-size: 11px; font-weight: 700; padding: 2px 10px;
    border-radius: 20px; letter-spacing: .6px;
}
.event-card {
    background: #1a1d2e; border: 1px solid #2a2d3e; border-radius: 8px;
    padding: 12px 16px; margin-bottom: 8px;
}
.event-date { font-size: 11px; color: #00D9FF; font-weight: 700;
    text-transform: uppercase; letter-spacing: 1px; margin-bottom: 4px; }
.event-match { font-size: 15px; font-weight: 700; color: #FFFFFF; }
.event-meta { font-size: 11px; color: #8892a4; margin-top: 2px; }
body { overscroll-behavior-y: none !important; overflow-x: hidden !important; }
input, select, textarea {
    background-color: #111827 !important; color: #FFFFFF !important;
    border-color: #2a2d3e !important;
}
#MainMenu { visibility: hidden; } footer { visibility: hidden; } header { visibility: hidden; }
</style>
""", unsafe_allow_html=True)
 
# ============================================================================
# CONSTANTS
# ============================================================================
REFRESH_INTERVAL     = 15
PAPER_TRADE_INTERVAL = 1200
MIN_EV_THRESHOLD     = 0.02
MIN_EDGE_THRESHOLD   = 0.03
INJURY_PENALTY       = 0.05
CB_STAKE_MULTIPLIER  = 0.50
MAX_SINGLE_STAKE_PCT = 0.20
KELLY_FRACTIONS      = {"Safe": 0.25, "Moderate": 0.50, "Aggressive": 0.75}
 
RISK_KEYWORDS = {
    "injury","injured","out","rest","resting","doubtful","questionable",
    "ruled out","sidelined","withdraw","withdrawn","illness","pain",
    "knee","ankle","hamstring","wrist","shoulder","back","gtd","game time decision",
}
 
TODAY      = datetime.now().strftime("%Y-%m-%d")
TODAY_ESPN = datetime.now().strftime("%Y%m%d")
 
PAPER_TRADES_CSV = Path("paper_trades.csv")
BANKROLL_CONFIG  = Path("bankroll_settings.json")
MODEL_CONFIG     = Path("model_settings.json")
 
RSS_FEEDS_NBA    = ["https://www.espn.com/espn/rss/nba/news"]
RSS_FEEDS_TENNIS = ["https://www.espn.com/espn/rss/tennis/news"]
 
# ============================================================================
# NETWORK HELPERS
# ============================================================================
def _make_session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.verify    = False
    return s
 
def _resolve_host(hostname: str) -> bool:
    try:
        socket.getaddrinfo(hostname, 443, socket.AF_INET)
        return True
    except Exception:
        return False
 
# ============================================================================
# NBA — ESPN scoreboard (today)
# ============================================================================
def fetch_nba_live() -> tuple:
    host = "site.api.espn.com"
    if not _resolve_host(host):
        return pd.DataFrame(), f"DNS FAILED: {host}", None
 
    url     = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={TODAY_ESPN}"
    session = _make_session()
    try:
        resp = session.get(url, verify=False, timeout=15)
        if resp.status_code != 200:
            return pd.DataFrame(), f"ESPN HTTP {resp.status_code}", None
 
        events = resp.json().get("events", [])
        if not events:
            return pd.DataFrame(), f"No NBA games scheduled for {TODAY}", None
 
        rows = []
        for event in events:
            try:
                comp      = event["competitions"][0]
                home_team = next(t for t in comp["competitors"] if t["homeAway"] == "home")
                away_team = next(t for t in comp["competitors"] if t["homeAway"] == "away")
                home_name = home_team["team"]["displayName"]
                away_name = away_team["team"]["displayName"]
                status    = event.get("status", {}).get("type", {}).get("description", "Scheduled")
                game_time = event.get("date", "")
                if game_time:
                    try:
                        dt = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
                        game_time = dt.strftime("%I:%M %p ET")
                    except Exception:
                        game_time = ""
 
                h_odds, a_odds = None, None
                for o in comp.get("odds", []):
                    home_ml = o.get("homeTeamOdds", {}).get("moneyLine")
                    away_ml = o.get("awayTeamOdds", {}).get("moneyLine")
                    if home_ml:
                        h_odds = round(1 + 100/abs(home_ml), 2) if home_ml < 0 else round(1 + home_ml/100, 2)
                    if away_ml:
                        a_odds = round(1 + 100/abs(away_ml), 2) if away_ml < 0 else round(1 + away_ml/100, 2)
                    break
 
                rows.append({
                    "Match":      f"{home_name} vs {away_name}",
                    "Time":       game_time,
                    "Status":     status,
                    "Home Odds":  h_odds,
                    "Away Odds":  a_odds,
                    "Home Team":  home_name,
                    "Risk Meter": 30,
                    "_source":    "ESPN",
                })
            except (KeyError, TypeError, StopIteration):
                continue
 
        if not rows:
            return pd.DataFrame(), "NBA parse error", None
        return pd.DataFrame(rows), "live (ESPN)", None
 
    except Exception as e:
        return pd.DataFrame(), f"ERROR: {e}", None
 
# ============================================================================
# NBA SCHEDULE — next 7 days
# ============================================================================
def fetch_nba_schedule(days: int = 7) -> list:
    """Returns list of upcoming NBA games for the next N days."""
    session = _make_session()
    all_events = []
    for i in range(1, days + 1):
        date     = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
        date_str = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        url      = f"https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard?dates={date}"
        try:
            resp   = session.get(url, verify=False, timeout=10)
            events = resp.json().get("events", [])
            for event in events:
                try:
                    comp      = event["competitions"][0]
                    home_team = next(t for t in comp["competitors"] if t["homeAway"] == "home")
                    away_team = next(t for t in comp["competitors"] if t["homeAway"] == "away")
                    home_name = home_team["team"]["displayName"]
                    away_name = away_team["team"]["displayName"]
                    game_time = event.get("date", "")
                    try:
                        dt = datetime.fromisoformat(game_time.replace("Z", "+00:00"))
                        time_str = dt.strftime("%I:%M %p ET")
                    except Exception:
                        time_str = "TBD"
                    all_events.append({
                        "Date":  date_str,
                        "Time":  time_str,
                        "Match": f"{home_name} vs {away_name}",
                        "Sport": "🏀 NBA",
                    })
                except (KeyError, TypeError, StopIteration):
                    continue
        except Exception:
            continue
    return all_events
 
# ============================================================================
# TENNIS — ESPN ATP + WTA scoreboard (today)
# ============================================================================
def fetch_tennis_live() -> tuple:
    host    = "site.api.espn.com"
    session = _make_session()
    if not _resolve_host(host):
        return pd.DataFrame(), f"DNS FAILED: {host}"
 
    for tour, slug in [("ATP", "atp"), ("WTA", "wta")]:
        url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{slug}/scoreboard?dates={TODAY_ESPN}"
        try:
            resp   = session.get(url, verify=False, timeout=15)
            if resp.status_code != 200:
                continue
            events = resp.json().get("events", [])
            if not events:
                continue
            rows = []
            for event in events:
                try:
                    comp      = event["competitions"][0]
                    home_team = next(t for t in comp["competitors"] if t["homeAway"] == "home")
                    away_team = next(t for t in comp["competitors"] if t["homeAway"] == "away")
                    p1 = home_team.get("athlete", {}).get("displayName") \
                         or home_team.get("team", {}).get("displayName", "P1")
                    p2 = away_team.get("athlete", {}).get("displayName") \
                         or away_team.get("team", {}).get("displayName", "P2")
                    tournament = event.get("season", {}).get("slug", tour)
                    status     = event.get("status", {}).get("type", {}).get("description", "Scheduled")
                    p1_odds, p2_odds = None, None
                    for o in comp.get("odds", []):
                        home_ml = o.get("homeTeamOdds", {}).get("moneyLine")
                        away_ml = o.get("awayTeamOdds", {}).get("moneyLine")
                        if home_ml:
                            p1_odds = round(1 + 100/abs(home_ml), 2) if home_ml < 0 else round(1 + home_ml/100, 2)
                        if away_ml:
                            p2_odds = round(1 + 100/abs(away_ml), 2) if away_ml < 0 else round(1 + away_ml/100, 2)
                        break
                    rows.append({
                        "Match":      f"{p1} vs {p2}",
                        "Tournament": tournament,
                        "Tour":       tour,
                        "Status":     status,
                        "P1 Odds":    p1_odds,
                        "P2 Odds":    p2_odds,
                        "Risk Meter": 30,
                        "_source":    f"ESPN {tour}",
                    })
                except (KeyError, TypeError, StopIteration):
                    continue
            if rows:
                return pd.DataFrame(rows), f"live (ESPN {tour})"
        except Exception:
            continue
 
    return pd.DataFrame(), f"No tennis matches scheduled for {TODAY}"
 
# ============================================================================
# TENNIS SCHEDULE — next 7 days
# ============================================================================
def fetch_tennis_schedule(days: int = 7) -> list:
    session    = _make_session()
    all_events = []
    for i in range(1, days + 1):
        date     = (datetime.now() + timedelta(days=i)).strftime("%Y%m%d")
        date_str = (datetime.now() + timedelta(days=i)).strftime("%Y-%m-%d")
        for tour, slug in [("ATP", "atp"), ("WTA", "wta")]:
            url = f"https://site.api.espn.com/apis/site/v2/sports/tennis/{slug}/scoreboard?dates={date}"
            try:
                resp   = session.get(url, verify=False, timeout=10)
                events = resp.json().get("events", [])
                for event in events:
                    try:
                        comp      = event["competitions"][0]
                        home_team = next(t for t in comp["competitors"] if t["homeAway"] == "home")
                        away_team = next(t for t in comp["competitors"] if t["homeAway"] == "away")
                        p1 = home_team.get("athlete", {}).get("displayName") \
                             or home_team.get("team", {}).get("displayName", "P1")
                        p2 = away_team.get("athlete", {}).get("displayName") \
                             or away_team.get("team", {}).get("displayName", "P2")
                        tournament = event.get("season", {}).get("slug", tour)
                        all_events.append({
                            "Date":  date_str,
                            "Time":  "TBD",
                            "Match": f"{p1} vs {p2}",
                            "Sport": f"🎾 {tour} — {tournament}",
                        })
                    except (KeyError, TypeError, StopIteration):
                        continue
            except Exception:
                continue
    return all_events
 
# ============================================================================
# AI ENRICHMENT
# ============================================================================
def enrich_with_ai_estimates(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    ai_prob_list, edge_list, ev_list, raw_list = [], [], [], []
    for _, row in df.iterrows():
        h_odds = row.get("Home Odds") or row.get("P1 Odds")
        a_odds = row.get("Away Odds") or row.get("P2 Odds")
        if not h_odds or not a_odds:
            ai_prob_list.append(None); edge_list.append(None)
            ev_list.append(None);     raw_list.append(None)
            continue
        risk    = int(row.get("Risk Meter", 30))
        imp_h   = 1.0 / h_odds
        imp_a   = 1.0 / a_odds
        overrnd = imp_h + imp_a
        fair_h  = imp_h / overrnd if overrnd else 0.5
        adj     = -0.04 if risk >= 65 else (-0.01 if risk >= 35 else 0.02)
        ai_h    = max(0.02, min(0.98, fair_h + adj))
        if ai_h <= imp_h + MIN_EDGE_THRESHOLD:
            ai_h = min(0.98, imp_h + MIN_EDGE_THRESHOLD)
        if risk >= 70:
            ai_h = max(0.02, ai_h - INJURY_PENALTY)
        ai_prob_list.append(round(ai_h * 100, 1))
        edge_list.append(round((ai_h - imp_h) * 100, 2))
        ev_list.append(round(ai_h * (h_odds - 1) - (1.0 - ai_h), 4))
        raw_list.append(ai_h)
    df["AI Prob %"]    = ai_prob_list
    df["Edge %"]       = edge_list
    df["EV+"]          = ev_list
    df["_ai_prob_raw"] = raw_list
    return df
 
# ============================================================================
# KELLY STAKES
# ============================================================================
def calculate_stakes(df: pd.DataFrame, bankroll: float, risk_level: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy(); stakes = []
    for _, row in df.iterrows():
        h_odds = row.get("Home Odds") or row.get("P1 Odds")
        raw    = row.get("_ai_prob_raw")
        if not h_odds or raw is None:
            stakes.append(None); continue
        prob = float(raw)
        b    = h_odds - 1
        edge = prob * b - (1.0 - prob)
        if edge <= 0:
            stakes.append(0.0)
        else:
            capped = min(edge / b * KELLY_FRACTIONS.get(risk_level, 0.5), MAX_SINGLE_STAKE_PCT)
            stakes.append(round(capped * bankroll * CB_STAKE_MULTIPLIER, 2))
    df["Stake (C$)"] = stakes
    return df
 
# ============================================================================
# PAPER TRADING
# ============================================================================
def load_paper_trades() -> list:
    if not PAPER_TRADES_CSV.exists():
        return []
    try:
        df = pd.read_csv(PAPER_TRADES_CSV)
        for col in ["odds","ev_plus","stake","ai_prob","edge_pct"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        for col in ["timestamp","match","strategy","status","result"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
        return df.to_dict("records")
    except Exception as e:
        st.warning(f"Could not load paper trades: {e}"); return []
 
def save_paper_trades(trades: list) -> None:
    try:
        pd.DataFrame(trades).to_csv(PAPER_TRADES_CSV, index=False)
    except Exception as e:
        st.error(f"Could not save paper trades: {e}")
 
def identify_best_trade(df_nba, df_tennis):
    frames = [df for df in [df_nba, df_tennis] if df is not None and not df.empty]
    if not frames:
        return None
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["EV+","Edge %"])
    filtered = all_df[(all_df["EV+"] > MIN_EV_THRESHOLD) &
                      (all_df["Edge %"] >= MIN_EDGE_THRESHOLD * 100)]
    if filtered.empty:
        return None
    return all_df.loc[filtered["EV+"].idxmax()]
 
def execute_paper_trade(df_nba, df_tennis) -> bool:
    best = identify_best_trade(df_nba, df_tennis)
    if best is None:
        return False
    trades = load_paper_trades()
    h_col  = "Home Odds" if pd.notna(best.get("Home Odds")) else "P1 Odds"
    trades.append({
        "id":        f"{best.get('Match','?')}_{datetime.now().strftime('%H%M%S')}",
        "timestamp": datetime.now().isoformat(),
        "match":     best.get("Match","Unknown"),
        "odds":      best.get(h_col, 0),
        "ev_plus":   best.get("EV+", 0),
        "stake":     best.get("Stake (C$)", 0),
        "ai_prob":   best.get("_ai_prob_raw", 0.5),
        "edge_pct":  best.get("Edge %", 0),
        "strategy":  "EV+ High Edge" if best.get("EV+",0) > 0.05 else "Value Trade",
        "status":    "PENDING",
        "result":    "",
    })
    save_paper_trades(trades); return True
 
def settle_pending_trades() -> int:
    trades = load_paper_trades(); count = 0
    for t in trades:
        if t.get("status") == "PENDING":
            t["result"] = "WIN" if random.random() < float(t.get("ai_prob", 0.5)) else "LOSS"
            t["status"] = "SETTLED"; count += 1
    save_paper_trades(trades); return count
 
def calculate_success_rate() -> dict:
    trades = load_paper_trades(); total = wins = 0
    for t in trades:
        r = str(t.get("result","")).upper()
        if r in ("WIN","LOSS"):
            total += 1
            if r == "WIN": wins += 1
    return {"total": total, "wins": wins, "losses": total - wins,
            "success_rate": round(wins/total*100,1) if total else 0.0}
 
# ============================================================================
# CONFIG
# ============================================================================
def load_bankroll_config() -> dict:
    if BANKROLL_CONFIG.exists():
        try: return json.loads(BANKROLL_CONFIG.read_text())
        except Exception: pass
    return {"starting_bankroll":1500.0,"min_stake":10.0,
            "max_stake":500.0,"max_drawdown_pct":25.0,"kelly_fraction":"Moderate"}
 
def save_bankroll_config(cfg):
    try: BANKROLL_CONFIG.write_text(json.dumps(cfg, indent=2))
    except Exception as e: st.error(f"Could not save: {e}")
 
def load_model_config() -> dict:
    if MODEL_CONFIG.exists():
        try: return json.loads(MODEL_CONFIG.read_text())
        except Exception: pass
    return {"model_confidence":1.0,"edge_threshold_pct":3.0,
            "injury_penalty_pct":5.0,"form_factor":0.5,"odds_weight":0.5}
 
def save_model_config(cfg):
    try: MODEL_CONFIG.write_text(json.dumps(cfg, indent=2))
    except Exception as e: st.error(f"Could not save: {e}")
 
# ============================================================================
# RSS HEADLINES
# ============================================================================
def fetch_rss_headlines(feed_urls: list) -> list:
    headlines = []
    for url in feed_urls:
        try:
            feed = feedparser.parse(url)
            headlines.extend(e.title for e in feed.entries[:8])
        except Exception: continue
    return headlines[:12]
 
def detect_injury_alert(headline: str) -> bool:
    return any(kw in (headline or "").lower() for kw in RISK_KEYWORDS)
 
# ============================================================================
# BACKTESTING
# ============================================================================
def run_backtest(days: int = 30) -> dict:
    trades  = load_paper_trades()
    settled = [t for t in trades if t.get("status") == "SETTLED"]
    if not trades:  return {"error": "No trades to backtest"}
    if not settled: return {"error": "No settled trades — execute and settle some paper trades first"}
    try:
        cutoff  = datetime.now() - timedelta(days=days)
        settled = [t for t in settled if datetime.fromisoformat(str(t["timestamp"])) >= cutoff]
    except Exception: pass
    if not settled: return {"error": f"No settled trades in the last {days} days"}
    total    = len(settled)
    wins     = sum(1 for t in settled if str(t.get("result","")).upper() == "WIN")
    staked   = sum(float(t.get("stake",  0)) for t in settled)
    total_ev = sum(float(t.get("ev_plus",0)) for t in settled)
    win_s    = [float(t.get("stake",0)) for t in settled if str(t.get("result","")).upper()=="WIN"]
    loss_s   = [float(t.get("stake",0)) for t in settled if str(t.get("result","")).upper()=="LOSS"]
    avg_win  = round(sum(win_s)/len(win_s),   2) if win_s  else 0.0
    avg_loss = round(sum(loss_s)/len(loss_s), 2) if loss_s else 0.0
    return {
        "total_trades":  total, "wins": wins, "losses": total-wins,
        "win_rate":      round(wins/total*100, 2),
        "roi":           round(total_ev/staked*100, 2) if staked else 0.0,
        "avg_win":       avg_win, "avg_loss": avg_loss,
        "profit_factor": round(avg_win/avg_loss, 2) if avg_loss else 0.0,
        "total_stake":   round(staked, 2), "total_ev": round(total_ev, 4),
    }
 
# ============================================================================
# DISPLAY HELPERS
# ============================================================================
def _badge(label: str) -> str:
    low = label.lower()
    if "live" in low:
        return f'<span class="api-badge-live">&#9679; {label}</span>'
    if "no " in low or "scheduled" in low:
        return f'<span class="api-badge-warn">&#8212; {label}</span>'
    return f'<span class="api-badge-error">&#9888; {label}</span>'
 
def _safe_numeric(df, cols):
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df
 
def _render_schedule(events: list, sport_filter: str = "All"):
    if not events:
        st.info("No upcoming events found for the next 7 days.")
        return
    df = pd.DataFrame(events)
    if sport_filter != "All":
        df = df[df["Sport"].str.contains(sport_filter, case=False)]
    if df.empty:
        st.info(f"No upcoming {sport_filter} events in the next 7 days.")
        return
    grouped = df.groupby("Date")
    for date, group in grouped:
        try:
            dt       = datetime.strptime(date, "%Y-%m-%d")
            day_label = dt.strftime("%A, %B %d")
        except Exception:
            day_label = date
        st.markdown(f"### 📅 {day_label}")
        for _, row in group.iterrows():
            st.markdown(
                f"<div class='event-card'>"
                f"<div class='event-date'>{row['Sport']} &nbsp;·&nbsp; {row['Time']}</div>"
                f"<div class='event-match'>{row['Match']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
 
# ============================================================================
# MAIN
# ============================================================================
def main():
    defaults = {
        "last_paper_trade":    datetime.now() - timedelta(seconds=PAPER_TRADE_INTERVAL),
        "last_rerun_time":     datetime.now(),
        "show_tennis_sidebar": False,
        "schedule_cache":      [],
        "schedule_fetched":    None,
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v
 
    with st.sidebar:
        st.subheader("⚙️ Settings")
        bankroll   = st.number_input("Bankroll (C$)", min_value=100.0, value=1500.0, step=100.0)
        risk_level = st.radio("Kelly Risk Level", ["Safe","Moderate","Aggressive"], index=1)
        st.divider()
        st.subheader("📡 Data Sources")
        nba_ph    = st.empty()
        tennis_ph = st.empty()
        st.divider()
        st.subheader("🎾 Tennis Preview")
        if st.button("📊 Toggle Tennis Matches"):
            st.session_state.show_tennis_sidebar = not st.session_state.show_tennis_sidebar
        tennis_sidebar_ph = st.empty()
 
    col_title, col_live = st.columns([4,1])
    with col_title:
        st.markdown("<h1 style='margin:0'>📈 High-Frequency Sports EV+ Dashboard</h1>",
                    unsafe_allow_html=True)
    with col_live:
        live_mode = st.checkbox("🔴 LIVE MODE", value=False)
 
    if live_mode:
        elapsed = (datetime.now() - st.session_state.last_rerun_time).total_seconds()
        if elapsed >= REFRESH_INTERVAL:
            st.session_state.last_rerun_time = datetime.now()
            time.sleep(0.1); st.rerun()
        else:
            st.info(f"🔄 Live mode — next refresh in {max(0, REFRESH_INTERVAL - int(elapsed))}s")
            time.sleep(1)
 
    # Fetch today's data
    nba_raw,    nba_status,    _ = fetch_nba_live()
    tennis_raw, tennis_status    = fetch_tennis_live()
 
    df_nba    = calculate_stakes(enrich_with_ai_estimates(nba_raw),    bankroll, risk_level)
    df_tennis = calculate_stakes(enrich_with_ai_estimates(tennis_raw), bankroll, risk_level)
 
    nba_ph.markdown(f"NBA: {_badge(nba_status)}", unsafe_allow_html=True)
    tennis_ph.markdown(f"Tennis: {_badge(tennis_status)}", unsafe_allow_html=True)
 
    if st.session_state.show_tennis_sidebar:
        with tennis_sidebar_ph.container():
            if df_tennis is not None and not df_tennis.empty:
                pc = [c for c in ["Match","P1 Odds","P2 Odds","EV+"] if c in df_tennis.columns]
                st.dataframe(df_tennis[pc].head(6), hide_index=True)
            else:
                st.info(tennis_status)
 
    if (datetime.now() - st.session_state.last_paper_trade).total_seconds() >= PAPER_TRADE_INTERVAL:
        execute_paper_trade(df_nba, df_tennis)
        settle_pending_trades()
        st.session_state.last_paper_trade = datetime.now()
 
    # Fetch schedule once per session (cached)
    schedule_age = None
    if st.session_state.schedule_fetched:
        schedule_age = (datetime.now() - st.session_state.schedule_fetched).total_seconds()
    if not st.session_state.schedule_cache or not schedule_age or schedule_age > 3600:
        nba_sched    = fetch_nba_schedule(7)
        tennis_sched = fetch_tennis_schedule(7)
        st.session_state.schedule_cache  = nba_sched + tennis_sched
        st.session_state.schedule_fetched = datetime.now()
 
    # TABS
    tabs = st.tabs([
        "🏆 Live Hub","🏀 NBA","🎾 Tennis","📅 Upcoming","📈 Analytics","🔧 Advanced Settings"
    ])
 
    # ── TAB 1: Live Hub ───────────────────────────────────────────────────────
    with tabs[0]:
        st.markdown("<div class='metric-box'><div class='metric-title'>💰 Best Trade Right Now</div>",
                    unsafe_allow_html=True)
        best = identify_best_trade(df_nba, df_tennis)
        if best is not None:
            st.markdown(
                f"<div class='metric-value'>{best.get('Match','N/A')}</div>"
                f"<p><b>EV+:</b> {best.get('EV+',0):.4f} &nbsp;|&nbsp;"
                f"<b>Edge:</b> {best.get('Edge %',0):.2f}% &nbsp;|&nbsp;"
                f"<b>Stake:</b> C${best.get('Stake (C$)',0):.2f} &nbsp;|&nbsp;"
                f"<b>AI Prob:</b> {best.get('AI Prob %',0):.1f}%</p>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='metric-value'>No qualifying trade — "
                "odds post ~2hrs before tip-off</div>", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
        st.divider()
 
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("🏀 NBA Today")
            if not df_nba.empty:
                dc = [c for c in ["Match","Time","Status","Home Odds","Away Odds","EV+","Stake (C$)"]
                      if c in df_nba.columns]
                st.dataframe(_safe_numeric(df_nba, dc)[dc], hide_index=True)
                if df_nba["Home Odds"].isna().all():
                    st.caption("ℹ️ Odds post ~2hrs before tip-off. EV+ calculates automatically.")
            else:
                st.info(f"🏀 {nba_status}")
 
        with col2:
            st.subheader("🎾 Tennis Today")
            if not df_tennis.empty:
                dc = [c for c in ["Match","Tour","Status","P1 Odds","P2 Odds","EV+","Stake (C$)"]
                      if c in df_tennis.columns]
                st.dataframe(_safe_numeric(df_tennis, dc)[dc], hide_index=True)
            else:
                st.info(f"🎾 {tennis_status}")
 
        st.divider()
        st.subheader("📰 Injury & News Alerts")
        nba_headlines    = fetch_rss_headlines(RSS_FEEDS_NBA)
        tennis_headlines = fetch_rss_headlines(RSS_FEEDS_TENNIS)
        all_headlines    = nba_headlines + tennis_headlines
        alerts           = [h for h in all_headlines if detect_injury_alert(h)]
        non_alerts       = [h for h in nba_headlines if not detect_injury_alert(h)][:3]
        if alerts:
            for a in alerts[:5]:
                st.warning(f"⚠️ {a}")
        if non_alerts:
            st.divider()
            st.caption("📰 Latest NBA News")
            for h in non_alerts:
                st.markdown(f"• {h}")
        if not alerts and not non_alerts:
            st.info("✅ No alerts — news feed unavailable.")
 
    # ── TAB 2: NBA ────────────────────────────────────────────────────────────
    with tabs[1]:
        st.header("🏀 NBA Markets")
        if not df_nba.empty:
            dc = [c for c in ["Match","Time","Status","Home Odds","Away Odds",
                               "AI Prob %","Edge %","EV+","Stake (C$)"] if c in df_nba.columns]
            st.dataframe(_safe_numeric(df_nba, dc)[dc], hide_index=True)
            if df_nba["Home Odds"].isna().all():
                st.info("ℹ️ Games loaded from ESPN. Odds post ~2 hours before tip-off — "
                        "EV+ and Stakes calculate automatically once odds appear.")
            st.divider()
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Games Today", len(df_nba))
            ev_valid = df_nba["EV+"].dropna()
            c2.metric("Avg EV+", f"{ev_valid.mean():.4f}" if not ev_valid.empty else "Pending")
            edge_valid = df_nba["Edge %"].dropna()
            c3.metric("Playable", int((edge_valid >= MIN_EDGE_THRESHOLD*100).sum()))
            stake_valid = pd.to_numeric(df_nba.get("Stake (C$)", pd.Series()), errors="coerce")
            c4.metric("Total Stake C$", f"{stake_valid.sum():,.2f}")
        else:
            st.info(f"🏀 {nba_status}")
 
    # ── TAB 3: Tennis ─────────────────────────────────────────────────────────
    with tabs[2]:
        st.header("🎾 Tennis Markets")
        if not df_tennis.empty:
            dc = [c for c in ["Match","Tournament","Tour","Status","P1 Odds","P2 Odds",
                               "AI Prob %","Edge %","EV+","Stake (C$)"] if c in df_tennis.columns]
            st.dataframe(_safe_numeric(df_tennis, dc)[dc], hide_index=True)
            st.divider()
            c1,c2,c3,c4 = st.columns(4)
            c1.metric("Matches", len(df_tennis))
            ev_valid = df_tennis["EV+"].dropna()
            c2.metric("Avg EV+", f"{ev_valid.mean():.4f}" if not ev_valid.empty else "Pending")
            edge_valid = df_tennis["Edge %"].dropna()
            c3.metric("Playable", int((edge_valid >= MIN_EDGE_THRESHOLD*100).sum()))
            stake_valid = pd.to_numeric(df_tennis.get("Stake (C$)", pd.Series()), errors="coerce")
            c4.metric("Total Stake C$", f"{stake_valid.sum():,.2f}")
        else:
            st.info(f"🎾 {tennis_status}")
            st.caption("ESPN covers ATP/WTA Grand Slams and major events. "
                       "Challenger-level matches (like those on Rainbet) are not in ESPN's feed. "
                       "Check back during Roland Garros, Wimbledon, or US Open weeks.")
 
    # ── TAB 4: UPCOMING EVENTS ────────────────────────────────────────────────
    with tabs[3]:
        st.header("📅 Upcoming Events — Next 7 Days")
        schedule = st.session_state.schedule_cache
 
        col_filter, col_refresh = st.columns([3,1])
        with col_filter:
            sport_filter = st.selectbox("Filter by sport", ["All","NBA","ATP","WTA"], index=0)
        with col_refresh:
            if st.button("🔄 Refresh Schedule"):
                nba_sched    = fetch_nba_schedule(7)
                tennis_sched = fetch_tennis_schedule(7)
                st.session_state.schedule_cache   = nba_sched + tennis_sched
                st.session_state.schedule_fetched = datetime.now()
                schedule = st.session_state.schedule_cache
                st.success("✅ Schedule refreshed.")
 
        if schedule:
            fetched_at = st.session_state.schedule_fetched
            if fetched_at:
                st.caption(f"Last fetched: {fetched_at.strftime('%H:%M:%S')} — "
                           f"{len(schedule)} events found")
        st.divider()
        _render_schedule(schedule, sport_filter)
 
        if not schedule:
            st.info("No upcoming events loaded yet. Click Refresh Schedule above.")
 
    # ── TAB 5: Analytics ──────────────────────────────────────────────────────
    with tabs[4]:
        st.header("📈 Paper Trading & Analytics")
 
        st.info("ℹ️ **How paper trading works:** When odds are live, click Execute Paper Trade "
                "to log the best qualifying trade (EV+ > 0.02, Edge > 3%). "
                "Then click Settle to simulate the outcome based on AI probability. "
                "Backtesting runs on your actual logged trades.")
 
        c1,c2 = st.columns(2)
        with c1:
            if st.button("▶️ Execute Paper Trade"):
                if execute_paper_trade(df_nba, df_tennis):
                    st.success("✅ Trade logged to paper_trades.csv")
                else:
                    st.warning("⚠️ No trade met criteria. Odds may not be posted yet — "
                               "try again closer to tip-off.")
        with c2:
            if st.button("✅ Settle Pending Trades"):
                n = settle_pending_trades()
                if isinstance(n, int) and n > 0:
                    st.success(f"✅ Settled {n} trade(s).")
                else:
                    st.info("No pending trades to settle.")
 
        st.divider()
        with st.expander("🗑️ Clear All Paper Trades"):
            st.warning("This will permanently delete all paper trade history.")
            if st.button("⚠️ Confirm — Delete All Trades"):
                try:
                    PAPER_TRADES_CSV.unlink(missing_ok=True)
                    st.success("✅ All trades cleared. Refresh the page.")
                except Exception as e:
                    st.error(f"Could not delete: {e}")
        stats = calculate_success_rate()
        st.markdown("<div class='metric-box'><div class='metric-title'>🎯 AI Success Rate</div>",
                    unsafe_allow_html=True)
        st.markdown(
            f"<div class='metric-value'>{stats['success_rate']:.1f}%</div>"
            f"<p><b>Wins:</b> {stats['wins']} &nbsp;|&nbsp;"
            f"<b>Losses:</b> {stats['losses']} &nbsp;|&nbsp;"
            f"<b>Total Settled:</b> {stats['total']}</p>",
            unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
 
        st.divider()
        st.subheader("📋 Trade History")
        trades = load_paper_trades()
        if trades:
            tdf = pd.DataFrame(trades)
            col_order = ["timestamp","match","odds","ev_plus","stake",
                         "ai_prob","edge_pct","strategy","result","status"]
            tdf = tdf[[c for c in col_order if c in tdf.columns]]
            tdf = tdf.rename(columns={
                "timestamp":"Time","match":"Match","odds":"Odds","ev_plus":"EV+",
                "stake":"Stake (C$)","ai_prob":"AI Prob","edge_pct":"Edge %",
                "strategy":"Strategy","result":"Result","status":"Status"})
            for col in ["Odds","EV+","Stake (C$)","AI Prob","Edge %"]:
                if col in tdf.columns:
                    tdf[col] = pd.to_numeric(tdf[col], errors="coerce")
            st.dataframe(tdf, hide_index=True)
            st.divider()
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Total",   len(trades))
            c2.metric("Settled", len([t for t in trades if t.get("status")=="SETTLED"]))
            c3.metric("Pending", len([t for t in trades if t.get("status")=="PENDING"]))
            c4.metric("Avg Stake C$",
                      f"{sum(float(t.get('stake',0)) for t in trades)/len(trades):,.2f}")
            c5.metric("Avg EV+",
                      f"{sum(float(t.get('ev_plus',0)) for t in trades)/len(trades):.4f}")
        else:
            st.info("No paper trades yet. Odds load ~2hrs before games — "
                    "come back then and click Execute Paper Trade.")
 
    # ── TAB 6: Advanced Settings ──────────────────────────────────────────────
    with tabs[5]:
        st.header("🔧 Advanced Settings")
        bankroll_cfg = load_bankroll_config()
        model_cfg    = load_model_config()
        s1,s2,s3     = st.tabs(["💰 Bankroll","🤖 Model","📊 Backtesting"])
 
        with s1:
            st.subheader("💰 Bankroll Management")
            c1,c2 = st.columns(2)
            with c1:
                br  = st.number_input("Starting Bankroll (C$)", min_value=100.0,
                                      value=float(bankroll_cfg["starting_bankroll"]), step=100.0)
                mn  = st.number_input("Min Stake (C$)", min_value=1.0,
                                      value=float(bankroll_cfg["min_stake"]), step=1.0)
            with c2:
                mx  = st.number_input("Max Stake (C$)", min_value=10.0,
                                      value=float(bankroll_cfg["max_stake"]), step=10.0)
                mdd = st.slider("Max Drawdown (%)", 1, 50, int(bankroll_cfg["max_drawdown_pct"]))
            kf = st.selectbox("Kelly Fraction",
                              ["Safe (0.25x)","Moderate (0.50x)","Aggressive (0.75x)"], index=1)
            if st.button("💾 Save Bankroll Settings"):
                save_bankroll_config({"starting_bankroll":br,"min_stake":mn,
                                      "max_stake":mx,"max_drawdown_pct":mdd,
                                      "kelly_fraction":kf.split(" ")[0]})
                st.success("✅ Saved.")
 
        with s2:
            st.subheader("🤖 Model Tuning")
            c1,c2 = st.columns(2)
            with c1:
                mc = st.slider("Model Confidence",0.5,2.0,float(model_cfg["model_confidence"]),0.05)
                et = st.slider("Edge Threshold (%)",1,10,int(model_cfg["edge_threshold_pct"]))
            with c2:
                ip = st.slider("Injury Penalty (%)",1,20,int(model_cfg["injury_penalty_pct"]))
                ff = st.slider("Form Factor",0.0,1.0,float(model_cfg["form_factor"]),0.05)
            ow = st.slider("Odds Weight",0.0,1.0,float(model_cfg["odds_weight"]),0.05)
            if st.button("💾 Save Model Settings"):
                save_model_config({"model_confidence":mc,"edge_threshold_pct":et,
                                   "injury_penalty_pct":ip,"form_factor":ff,"odds_weight":ow})
                st.success("✅ Saved.")
 
        with s3:
            st.subheader("📊 Backtesting")
            st.info("Backtesting runs on your real paper trade history. "
                    "Execute and settle trades in the Analytics tab to build history.")
            days = st.selectbox("Period (days)",[7,14,30,60,90],index=2)
            if st.button("▶️ Run Backtest"):
                res = run_backtest(days)
                if "error" in res:
                    st.error(f"❌ {res['error']}")
                else:
                    st.success(f"✅ Backtest complete — last {days} days")
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Trades",    res["total_trades"])
                    c2.metric("Win Rate",  f"{res['win_rate']:.1f}%")
                    c3.metric("ROI",       f"{res['roi']:.2f}%")
                    c4.metric("P. Factor", f"{res['profit_factor']:.2f}")
                    c5,c6,c7 = st.columns(3)
                    c5.metric("Wins",   res["wins"])
                    c6.metric("Losses", res["losses"])
                    c7.metric("Staked (C$)", f"{res['total_stake']:,.2f}")
 
    st.divider()
    st.markdown(
        "<p style='text-align:center;font-size:12px;color:#666;'>"
        "📈 High-Frequency Sports EV+ Dashboard &nbsp;|&nbsp;"
        "NBA + Tennis via ESPN &nbsp;|&nbsp; All amounts in CAD"
        "</p>", unsafe_allow_html=True)
 
if __name__ == "__main__":
    main()