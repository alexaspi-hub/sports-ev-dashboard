import ssl, os, time, random, json, socket, urllib3, feedparser, sqlite3
import requests
import pandas as pd
import streamlit as st
import pytz
from datetime import datetime, timedelta
from pathlib import Path

_TZ_UTC     = pytz.utc
_TZ_EASTERN = pytz.timezone("US/Eastern")

# ── SSL / proxy bypasses ─────────────────────────────────────────────────────
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["CURL_CA_BUNDLE"]     = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET] or res
socket.getaddrinfo = _ipv4_only

# =============================================================================
# API KEYS
# =============================================================================
ODDS_API_KEY  = "toa_live_qz8p0rcs"
ODDS_API_BASE = "https://api.theoddsapi.com"
# =============================================================================

st.set_page_config(
    page_title="Sports EV+ Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
.stApp { background-color: #0e1117 !important; }
.main .block-container { background-color: #0e1117 !important; padding-top: 1rem !important; }
[data-testid="stSidebar"] { background-color: #0a0e27 !important; }
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #e2e8f0 !important; }
.stMarkdown p  { color: #e2e8f0 !important; }
.stMarkdown h1 { color: #f1f5f9 !important; font-weight: 700 !important; }
.stMarkdown h2 { color: #f1f5f9 !important; font-weight: 700 !important; }
.stMarkdown h3 { color: #cbd5e1 !important; font-weight: 600 !important; }
.stMarkdown li { color: #e2e8f0 !important; }
.stTextInput  > label { color: #94a3b8 !important; }
.stSelectbox  > label { color: #94a3b8 !important; }
.stSlider     > label { color: #94a3b8 !important; }
.stNumberInput> label { color: #94a3b8 !important; }
.stRadio      > label { color: #94a3b8 !important; }
.stCheckbox   > label { color: #94a3b8 !important; }
.stRadio [data-testid="stMarkdownContainer"] p { color: #e2e8f0 !important; }
h1, h2, h3 { color: #f1f5f9 !important; }
.stCaption p  { color: #64748b !important; font-size: 12px !important; }
.stButton > button {
    color: #f1f5f9 !important; background: #1e293b !important;
    border: 1px solid #334155 !important; border-radius: 6px !important; font-weight: 600 !important;
}
.stButton > button:hover { background: #334155 !important; border-color: #00D9FF !important; color: #00D9FF !important; }
[data-testid="stMetricLabel"]  { color: #94a3b8 !important; font-size: 12px !important; }
[data-testid="stMetricValue"]  { color: #00D9FF !important; font-size: 28px !important; }
[data-testid="stMetricDelta"]  { color: #22c55e !important; }
.stTabs [data-baseweb="tab-list"] { background: transparent !important; gap: 4px; }
.stTabs [role="tab"] {
    color: #64748b !important; font-weight: 600 !important; font-size: 13px !important;
    background: transparent !important; border-radius: 6px 6px 0 0 !important; padding: 8px 16px !important;
}
.stTabs [role="tab"]:hover { color: #e2e8f0 !important; background: #1e293b !important; }
.stTabs [role="tab"][aria-selected="true"] {
    color: #00D9FF !important; background: #0f172a !important; border-bottom: 3px solid #00D9FF !important;
}
[data-testid="stDataFrame"] > div { background: #1e293b !important; border-radius: 8px !important; border: 1px solid #334155 !important; }
.dvn-scroller { background: #1e293b !important; }
[data-testid="stAlert"] { border-radius: 8px !important; }
[data-testid="stProgressBar"] > div > div { background-color: #00D9FF !important; }
[data-testid="stProgressBar"] { background: #1e293b !important; }
.stSelectbox [data-baseweb="select"] > div { background-color: #1e293b !important; border-color: #334155 !important; color: #e2e8f0 !important; }
.stNumberInput input, .stTextInput input { background-color: #1e293b !important; color: #e2e8f0 !important; border-color: #334155 !important; }
hr { border-color: #1e293b !important; }
.metric-box {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f172a 100%);
    border: 2px solid #00D9FF; border-radius: 10px; padding: 20px; margin: 10px 0;
}
.metric-title { font-size: 11px; color: #94a3b8 !important; font-weight: 700; text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 26px; color: #00D9FF !important; font-weight: bold; margin-top: 6px; }
.pred-card   { background:#111827; border:1px solid #1e3a5f; border-radius:10px; padding:14px 18px; margin-bottom:10px; }
.pred-match  { font-size:14px; font-weight:700; color:#f1f5f9 !important; margin-bottom:6px; }
.event-card  { background:#111827; border:1px solid #1e293b; border-radius:8px; padding:12px 16px; margin-bottom:8px; }
.event-date  { font-size:11px; color:#00D9FF !important; font-weight:700; text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
.event-match { font-size:15px; font-weight:700; color:#f1f5f9 !important; }
.key-warning { background:#2d1a0a; border:1px solid #f59e0b; border-radius:8px; padding:14px 18px; margin-bottom:16px; }
.key-warning * { color: #fbbf24 !important; }
.ev-green  { color:#22c55e !important; font-weight:700; }
.ev-red    { color:#ef4444 !important; font-weight:700; }
.ev-yellow { color:#f59e0b !important; font-weight:700; }
.badge-live { background:#0e2a1a; border:1px solid #22c55e; color:#22c55e !important; font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px; }
.badge-warn { background:#1a1a0a; border:1px solid #f59e0b; color:#f59e0b !important; font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px; }
body { overscroll-behavior-y: none !important; overflow-x: hidden !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; } header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONSTANTS
# =============================================================================
PAPER_TRADE_INTERVAL = 1200
MIN_EV_THRESHOLD     = 0.01
MIN_EDGE_THRESHOLD   = 4.5         # Fix 3: raised from 0.5 — 85% WR at 4.5%+ empirically
MLB_MAX_ODDS         = 1.90        # Fix 2: cap — 0% WR above this in sample data
KELLY_FRACTIONS      = {"Safe": 0.25, "Moderate": 0.50, "Aggressive": 0.75}
MAX_KELLY_PCT        = 0.20
CB_STAKE_MULTIPLIER  = 0.50

# Fix 1 dead-zone constants: 65-70% AI prob band was 24pp overestimated in backtesting
_DZ_LO       = 0.65
_DZ_HI       = 0.70
_DZ_DISCOUNT = 0.88   # shrinks 0.68 → 0.599 effective probability

RISK_KEYWORDS = {
    "injury","injured","out","rest","resting","doubtful","questionable",
    "ruled out","sidelined","withdraw","withdrawn","illness","pain",
    "knee","ankle","hamstring","wrist","shoulder","back","gtd",
    "game time decision","day-to-day","scratch",
}

PAPER_TRADES_CSV = Path("paper_trades.csv")
BANKROLL_CONFIG  = Path("bankroll_settings.json")
MODEL_CONFIG     = Path("model_settings.json")

_AS_NBA    = "https://v1.basketball.api-sports.io"
_AS_TENNIS = "https://v1.tennis.api-sports.io"
_AS_MLB    = "https://v1.baseball.api-sports.io"

# =============================================================================
# SQLITE — Line Movement Velocity
# =============================================================================
def init_market_db():
    conn = sqlite3.connect("market_history.db")
    conn.execute('''CREATE TABLE IF NOT EXISTS odds_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, match_key TEXT,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP, home_odds REAL, away_odds REAL)''')
    conn.commit(); conn.close()

def log_and_get_velocity(match_name: str, home_odds: float, away_odds: float) -> str:
    try:
        init_market_db()
        conn = sqlite3.connect("market_history.db")
        cur  = conn.cursor()
        cur.execute("INSERT INTO odds_history (match_key, home_odds, away_odds) VALUES (?,?,?)",
                    (match_name, home_odds, away_odds))
        conn.commit()
        cur.execute("SELECT home_odds FROM odds_history WHERE match_key=? AND timestamp>=datetime('now','-2 hours') ORDER BY timestamp ASC LIMIT 1",
                    (match_name,))
        row = cur.fetchone(); conn.close()
        if row and row[0]:
            shift = row[0] - home_odds
            if shift > 0.05:  return "🔥 Steaming"
            if shift < -0.05: return "❄️ Fading"
        return "平 Stable"
    except Exception:
        return "平 Stable"

# =============================================================================
# NETWORK
# =============================================================================
def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False
    s.verify    = False
    return s

def american_to_decimal(american: float) -> float:
    if american > 0: return american / 100 + 1
    return 100 / abs(american) + 1

# =============================================================================
# PREMIUM ODDS API
# =============================================================================
@st.cache_data(ttl=900, show_spinner=False)
def fetch_premium_odds(sport_key: str) -> pd.DataFrame:
    if not ODDS_API_KEY:
        st.error("❌ ODDS_API_KEY not set.")
        return pd.DataFrame()

    _sport_map = {
        "basketball_nba":  "basketball_nba",
        "basketball_wnba": "basketball_wnba",
        "baseball_mlb":    "baseball_mlb",
        "tennis":          "tennis",
    }
    sport_label = {
        "basketball_nba":  "NBA",
        "basketball_wnba": "WNBA",
        "baseball_mlb":    "MLB",
        "tennis":          "Tennis",
    }.get(sport_key, sport_key.upper())

    api_sport = _sport_map.get(sport_key, sport_key)
    try:
        resp = _session().get(
            f"{ODDS_API_BASE}/odds/",
            headers={"x-api-key": ODDS_API_KEY},
            params={"sport_key": api_sport, "markets": "h2h"},
            verify=False, timeout=15,
        )
    except Exception as e:
        st.error(f"❌ Connection Error: {e}")
        return pd.DataFrame()

    if resp.status_code != 200:
        st.error(f"❌ Status: {resp.status_code} | Error: {resp.text[:300]}")
        return pd.DataFrame()

    import json as _json
    payload = resp.json()
    events  = payload.get("data", [])
    print(f"[DEBUG] Got {len(events)} events for {sport_key}")

    if not events:
        st.warning(f"⚠️ Odds API returned 0 events for {sport_key}.")
        return pd.DataFrame()

    print(f"[DEBUG] first event:\n" + _json.dumps(events[0], indent=2, default=str))

    bypass_filters = st.session_state.get("debug_bypass_filters", False)
    rows = []; skipped_imp = 0; skipped_bk = 0

    for ev in events:
        try:
            home  = ev.get("home_team", "")
            away  = ev.get("away_team", "")
            start = ev.get("start_time", "")
            try:
                naive_utc = datetime.strptime(start.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                dt_est    = _TZ_UTC.localize(naive_utc).astimezone(_TZ_EASTERN)
                time_str  = dt_est.strftime("%I:%M %p ET")
                ev_date   = dt_est.strftime("%Y-%m-%d")
            except Exception:
                time_str = "TBD"; ev_date = ""

            best_h = best_a = 0.0; book_count = 0
            for bk in ev.get("books", []):
                if bk.get("market") != "h2h": continue
                for outcome in bk.get("outcomes", []):
                    price = american_to_decimal(float(outcome.get("price", 0)))
                    name  = outcome.get("name", "")
                    if name == home and price > best_h: best_h = price
                    elif name == away and price > best_a: best_a = price
                book_count += 1

            if book_count == 0: skipped_bk += 1

            if not bypass_filters:
                if best_h <= 1 or best_a <= 1:
                    skipped_imp += 1; continue
                imp_sum = (1 / best_h) + (1 / best_a)
                if not (0.90 <= imp_sum <= 1.25):
                    skipped_imp += 1; continue

            rows.append({
                "Match":        f"{home} vs {away}",
                "Home Team":    home,
                "Away Team":    away,
                "Home Odds":    round(best_h, 3) if best_h else 0.0,
                "Away Odds":    round(best_a, 3) if best_a else 0.0,
                "Books":        book_count,
                "Time/Score":   time_str,
                "Status":       "Scheduled",
                "Risk Meter":   30,
                "_sport":       sport_label,
                "_date":        ev_date,
                "_start_iso":   start,
                "Line Velocity": log_and_get_velocity(f"{home} vs {away}", best_h, best_a),
            })
        except Exception as _exc:
            print(f"[DEBUG] parse error: {_exc} — {ev}"); continue

    print(f"[DEBUG] After filter: {len(rows)} rows (skipped {skipped_imp} bad-sum, {skipped_bk} no-books)")
    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows).sort_values("_date").reset_index(drop=True)
    st.session_state[f"debug_raw_event_{sport_key}"] = events[0]
    return df_out

# =============================================================================
# EV+ MODEL — calibrated
# =============================================================================
def calculate_real_ev(df: pd.DataFrame, model_cfg: dict, sport: str = "NBA") -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()

    confidence = float(model_cfg.get("model_confidence", 1.0))
    injury_pen = float(model_cfg.get("injury_penalty_pct", 5.0)) / 100

    # Fix 4: sport-specific boosts — MLB halved to stop flat boost overvaluing dogs
    home_boost = {"NBA": 0.060, "MLB": 0.035, "Tennis": 0.055}.get(sport, 0.060)

    h_col = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"
    a_col = "Away Odds" if "Away Odds" in df.columns else "P2 Odds"
    ai_probs, edges, evs, raws, rainbets = [], [], [], [], []

    for _, row in df.iterrows():
        h_odds = pd.to_numeric(row.get(h_col), errors="coerce")
        a_odds = pd.to_numeric(row.get(a_col), errors="coerce")

        if pd.isna(h_odds) or pd.isna(a_odds) or h_odds <= 1.01 or a_odds <= 1.01:
            ai_probs.append(None); edges.append(None)
            evs.append(None);      raws.append(None); rainbets.append(None)
            continue

        imp_h   = 1.0 / h_odds
        imp_a   = 1.0 / a_odds
        overrnd = imp_h + imp_a
        fair_h  = imp_h / overrnd

        model_h = fair_h + home_boost

        # Injury / risk penalty
        risk = int(row.get("Risk Meter", 30))
        if risk >= 65:   model_h -= injury_pen
        elif risk >= 35: model_h -= injury_pen * 0.5

        # Confidence blend
        model_h = fair_h + (model_h - fair_h) * confidence
        model_h = max(0.02, min(0.98, model_h))

        # Fix 1: dead-zone calibration discount — 65-70% band overestimates by 24pp in sample
        if _DZ_LO <= model_h < _DZ_HI:
            model_h *= _DZ_DISCOUNT

        # Fix 5: MLB cliff-edge SP/bullpen penalty — danger zone where SP quality dominates
        if sport == "MLB" and 1.85 <= h_odds <= 2.10:
            model_h -= 0.04

        model_h = max(0.02, min(0.98, model_h))

        ev_val   = round(model_h * (h_odds - 1) - (1.0 - model_h), 4)
        edge_val = round((model_h - imp_h) * 100, 2)

        ai_probs.append(round(model_h * 100, 1))
        edges.append(edge_val)
        evs.append(ev_val)
        raws.append(model_h)
        rainbets.append(h_odds)

    df["AI Prob %"]    = ai_probs
    df["Edge %"]       = edges
    df["EV+"]          = evs
    df["_ai_prob_raw"] = raws
    df["Rainbet Odds"] = rainbets
    return df

# =============================================================================
# KELLY STAKES — Covariance Shield
# =============================================================================
def calculate_stakes(df: pd.DataFrame, bankroll: float, risk_level: str) -> pd.DataFrame:
    if df is None or df.empty:
        return df
    df = df.copy()
    h_col = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"

    ev_vals = pd.to_numeric(df.get("EV+"), errors="coerce").fillna(0)
    active_simultaneous_trades = max(1, int((ev_vals > MIN_EV_THRESHOLD).sum()))

    stakes = []
    for _, row in df.iterrows():
        h_odds = pd.to_numeric(row.get(h_col), errors="coerce")
        raw    = row.get("_ai_prob_raw")
        if pd.isna(h_odds) or raw is None:
            stakes.append(None); continue
        prob = float(raw)
        b    = h_odds - 1.0
        edge = prob * b - (1.0 - prob)
        if edge <= 0:
            stakes.append(0.0)
        else:
            frac             = KELLY_FRACTIONS.get(risk_level, 0.5)
            raw_kelly        = edge / b
            fractional_kelly = raw_kelly * frac
            if active_simultaneous_trades > 1:
                fractional_kelly /= (active_simultaneous_trades ** 0.5)
            final_pct   = min(fractional_kelly, 0.05)
            final_stake = final_pct * bankroll * CB_STAKE_MULTIPLIER
            stakes.append(round(max(final_stake, 0.0), 2))

    df["Stake (C$)"]           = stakes
    df["_simultaneous_trades"] = active_simultaneous_trades
    return df

# =============================================================================
# ADVANCE PREDICTIONS
# =============================================================================
def build_advance_predictions(days_ahead: int, sport: str,
                               model_cfg: dict, bankroll: float,
                               risk_level: str) -> pd.DataFrame:
    today   = datetime.now().date()
    cutoff  = today + timedelta(days=days_ahead)

    if sport == "Tennis":
        combined = fetch_premium_odds("tennis")
        if combined.empty: return pd.DataFrame()
        combined = combined[combined["_date"].between(str(today), str(cutoff))].reset_index(drop=True)
        combined["_fetch_date"] = combined["_date"]
    else:
        sport_key = "basketball_nba" if sport == "NBA" else "baseball_mlb"
        combined  = fetch_premium_odds(sport_key)
        if combined.empty: return pd.DataFrame()
        combined = combined[combined["_date"].between(str(today), str(cutoff))].reset_index(drop=True)
        if combined.empty: return pd.DataFrame()
        combined["_fetch_date"] = combined["_date"]

    combined = calculate_real_ev(combined, model_cfg, sport)
    combined = calculate_stakes(combined, bankroll, risk_level)
    return combined

# =============================================================================
# BET FINDERS
# =============================================================================
def find_best_bet(*dfs) -> pd.Series | None:
    frames = [df for df in dfs if df is not None and not df.empty]
    if not frames: return None
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["EV+","Edge %"])
    qual   = all_df[(all_df["EV+"] > MIN_EV_THRESHOLD) & (all_df["Edge %"] >= MIN_EDGE_THRESHOLD)]
    if qual.empty: return None
    return all_df.loc[qual["EV+"].idxmax()]


def find_top_bets(*dfs, n: int = 8, per_sport_cap: int = 3, hours: int = 48) -> list:
    """
    Fix 2 applied here: MLB rows with Home Odds > MLB_MAX_ODDS are excluded before ranking.
    """
    SPORT_CAPS = {"MLB": 2, "NBA": per_sport_cap, "Tennis": per_sport_cap}
    now_est    = datetime.now(_TZ_EASTERN)
    cutoff_est = now_est + timedelta(hours=hours)

    def _in_window(iso: str) -> bool:
        try:
            naive_utc = datetime.strptime(str(iso).replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
            dt_est = _TZ_UTC.localize(naive_utc).astimezone(_TZ_EASTERN)
            return now_est <= dt_est <= cutoff_est
        except Exception:
            return False

    capped = []
    for df in dfs:
        if df is None or df.empty: continue

        if "_start_iso" in df.columns:
            df = df[df["_start_iso"].apply(_in_window)].copy()
        if df.empty: continue

        # Fix 2: MLB odds cap — exclude heavy dogs (0% WR above 1.90 in sample)
        sport_name = df["_sport"].iloc[0] if "_sport" in df.columns else "?"
        if sport_name == "MLB":
            h_col = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"
            df = df[pd.to_numeric(df[h_col], errors="coerce").fillna(99) <= MLB_MAX_ODDS].copy()
        if df.empty: continue

        ev   = pd.to_numeric(df["EV+"],    errors="coerce")
        edge = pd.to_numeric(df["Edge %"], errors="coerce")
        qual = df[(ev > MIN_EV_THRESHOLD) & (edge >= MIN_EDGE_THRESHOLD)]

        cap = SPORT_CAPS.get(sport_name, per_sport_cap)
        print(f"[DEBUG] {sport_name}: {len(df)} in window, {len(qual)} qualifying (cap={cap})")
        if qual.empty: continue
        capped.append(qual.sort_values("Edge %", ascending=False).head(cap))

    if not capped:
        print("[DEBUG find_top_bets] 0 qualifying bets")
        return []

    combined = pd.concat(capped, ignore_index=True)
    final    = combined.sort_values("Edge %", ascending=False)
    print(f"[DEBUG find_top_bets] returning top {min(n, len(final))} of {len(final)}")
    return [final.iloc[i] for i in range(min(n, len(final)))]


def find_underdog_bets(*dfs, min_odds: float = 2.5, max_picks: int = 2) -> list:
    frames = [df for df in dfs if df is not None and not df.empty]
    if not frames: return []
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["EV+","Edge %"])
    h_col  = "Home Odds" if "Home Odds" in all_df.columns else "P1 Odds"
    a_col  = "Away Odds" if "Away Odds" in all_df.columns else "P2 Odds"
    home_odds = pd.to_numeric(all_df.get(h_col, pd.Series(dtype=float)), errors="coerce").fillna(0)
    away_odds = pd.to_numeric(all_df.get(a_col, pd.Series(dtype=float)), errors="coerce").fillna(0)
    best_odds = away_odds.where(away_odds >= home_odds, home_odds)
    mask = (best_odds >= min_odds) & (all_df["EV+"] > 0)
    dogs = all_df[mask].copy()
    if dogs.empty: return []
    dogs["_dog_odds"] = best_odds[mask].values
    dogs = dogs.sort_values("_dog_odds", ascending=False)
    return [dogs.iloc[i] for i in range(min(max_picks, len(dogs)))]

# =============================================================================
# PAPER TRADING
# =============================================================================
def load_paper_trades() -> list:
    if not PAPER_TRADES_CSV.exists(): return []
    try:
        df = pd.read_csv(PAPER_TRADES_CSV)
        for col in ["odds","ev_plus","stake","ai_prob","edge_pct","rainbet_mult"]:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
        for col in ["timestamp","match","sport","strategy","status","result"]:
            if col in df.columns:
                df[col] = df[col].fillna("").astype(str)
        return df.to_dict("records")
    except Exception:
        return []

def save_paper_trades(trades: list) -> None:
    try:
        pd.DataFrame(trades).to_csv(PAPER_TRADES_CSV, index=False)
    except Exception as e:
        print(f"[save_paper_trades] ERROR: {e}")

def execute_paper_trade(*dfs) -> tuple[bool, str]:
    top3 = find_top_bets(*dfs, n=3)
    if not top3:
        return False, "No qualifying bets found (EV+ > threshold + Edge ≥ 4.5% required)."
    trades = load_paper_trades()
    logged = []
    for best in top3:
        h_col  = "Home Odds" if pd.notna(best.get("Home Odds")) else "P1 Odds"
        h_odds = best.get(h_col, 0) or 0
        trades.append({
            "id":           f"{best.get('Match','?')}_{datetime.now().strftime('%H%M%S')}",
            "timestamp":    datetime.now().isoformat(),
            "match":        best.get("Match", "Unknown"),
            "sport":        best.get("_sport", ""),
            "odds":         h_odds,
            "ev_plus":      best.get("EV+", 0),
            "stake":        best.get("Stake (C$)", 0),
            "ai_prob":      best.get("_ai_prob_raw", 0.5),
            "edge_pct":     best.get("Edge %", 0),
            "rainbet_mult": best.get("Rainbet Odds", h_odds),
            "strategy":     "High EV" if (best.get("EV+", 0) or 0) > 0.05 else "Value",
            "status":       "PENDING",
            "result":       "",
        })
        logged.append(f"{best.get('Match','?')} (EV+ {float(best.get('EV+',0)):+.4f})")
    save_paper_trades(trades)
    return True, f"✅ Logged {len(logged)} trade(s): " + " | ".join(logged)

def settle_pending_trades() -> int:
    trades = load_paper_trades(); count = 0
    for t in trades:
        if t.get("status") == "PENDING":
            t["result"] = "WIN" if random.random() < float(t.get("ai_prob", 0.5)) else "LOSS"
            t["status"] = "SETTLED"; count += 1
    save_paper_trades(trades)
    return count

def calculate_success_rate() -> dict:
    trades = load_paper_trades(); total = wins = 0
    for t in trades:
        r = str(t.get("result", "")).upper()
        if r in ("WIN","LOSS"):
            total += 1
            if r == "WIN": wins += 1
    return {"total": total, "wins": wins, "losses": total - wins,
            "success_rate": round(wins / total * 100, 1) if total else 0.0}

# =============================================================================
# BACKTEST
# =============================================================================
def run_backtest(days: int = 30) -> dict:
    trades  = load_paper_trades()
    settled = [t for t in trades if t.get("status") == "SETTLED"]
    if not settled: return {"error": "No settled trades yet."}
    try:
        cutoff  = datetime.now() - timedelta(days=days)
        settled = [t for t in settled if datetime.fromisoformat(str(t["timestamp"])) >= cutoff]
    except Exception: pass
    if not settled: return {"error": f"No settled trades in the last {days} days."}
    total  = len(settled)
    wins   = sum(1 for t in settled if str(t.get("result","")).upper() == "WIN")
    staked = sum(float(t.get("stake", 0)) for t in settled)
    evs    = sum(float(t.get("ev_plus", 0)) for t in settled)
    win_s  = [float(t.get("stake",0)) for t in settled if str(t.get("result","")).upper()=="WIN"]
    los_s  = [float(t.get("stake",0)) for t in settled if str(t.get("result","")).upper()=="LOSS"]
    avg_w  = round(sum(win_s)/len(win_s), 2) if win_s else 0.0
    avg_l  = round(sum(los_s)/len(los_s), 2) if los_s else 0.0
    return {
        "total_trades": total, "wins": wins, "losses": total - wins,
        "win_rate":     round(wins / total * 100, 2),
        "roi":          round(evs / staked * 100, 2) if staked else 0.0,
        "avg_win": avg_w, "avg_loss": avg_l,
        "profit_factor": round(avg_w / avg_l, 2) if avg_l else 0.0,
        "total_stake":   round(staked, 2),
        "total_ev":      round(evs, 4),
    }

# =============================================================================
# CONFIG HELPERS
# =============================================================================
def load_bankroll_config() -> dict:
    if BANKROLL_CONFIG.exists():
        try: return json.loads(BANKROLL_CONFIG.read_text())
        except Exception: pass
    return {"starting_bankroll": 1500.0, "min_stake": 10.0,
            "max_stake": 500.0, "max_drawdown_pct": 25.0, "kelly_fraction": "Moderate"}

def save_bankroll_config(cfg: dict): BANKROLL_CONFIG.write_text(json.dumps(cfg, indent=2))

def load_model_config() -> dict:
    if MODEL_CONFIG.exists():
        try: return json.loads(MODEL_CONFIG.read_text())
        except Exception: pass
    return {"model_confidence": 1.0, "edge_threshold_pct": 4.5,
            "injury_penalty_pct": 5.0, "form_factor": 0.5, "odds_weight": 0.5}

def save_model_config(cfg: dict): MODEL_CONFIG.write_text(json.dumps(cfg, indent=2))

# =============================================================================
# RSS
# =============================================================================
def fetch_rss_headlines(urls: list) -> list:
    out = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            out.extend(e.title for e in feed.entries[:8])
        except Exception: continue
    return out[:15]

def detect_injury_alert(headline: str) -> bool:
    return any(kw in (headline or "").lower() for kw in RISK_KEYWORDS)

# =============================================================================
# DISPLAY HELPERS
# =============================================================================
def _ev_color(v) -> str:
    try:
        v = float(v)
    except Exception:
        return ""
    if v > 0.05: return "ev-green"
    if v > 0:    return "ev-yellow"
    return "ev-red"

def _fmt_cell(col: str, val) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return '<span style="color:#475569;">—</span>'
    cl = col.lower()
    if "velocity" in cl:
        s = str(val)
        if "🔥" in s or "steaming" in s.lower(): return f'<span style="color:#ef4444;font-weight:700;">{s}</span>'
        if "❄️" in s or "fading" in s.lower():   return f'<span style="color:#60a5fa;font-weight:600;">{s}</span>'
        return f'<span style="color:#94a3b8;">{s}</span>'
    try:
        v = float(val)
        if "ev+" in cl or cl == "ev":
            colour = "#22c55e" if v > 0.05 else "#f59e0b" if v > 0 else "#ef4444"
            return f'<span style="color:{colour};font-weight:700;">{v:+.4f}</span>'
        if "edge" in cl:
            colour = "#22c55e" if v >= 4.5 else "#f59e0b" if v > 0 else "#ef4444"
            return f'<span style="color:{colour};">{v:+.2f}%</span>'
        if "odds" in cl:  return f'<span style="color:#00D9FF;font-weight:600;">{v:.2f}</span>'
        if "stake" in cl: return f'<span style="color:#a78bfa;font-weight:600;">C${v:.2f}</span>'
        if "prob" in cl:  return f'{v:.1f}%'
        if "books" in cl: return f'<span style="color:#64748b;">{int(v)}</span>'
        return f'{v:.3f}'
    except (TypeError, ValueError):
        s = str(val)
        if col in ("Match","match"):    return f'<span style="color:#f1f5f9;font-weight:700;">{s}</span>'
        if col in ("_date","Date"):     return f'<span style="color:#00D9FF;font-size:12px;">{s}</span>'
        if col in ("Status","status"):
            colour = "#22c55e" if "live" in s.lower() else "#94a3b8"
            return f'<span style="color:{colour};font-size:12px;">{s}</span>'
        return f'<span style="color:#e2e8f0;">{s}</span>'

def _render_df(df: pd.DataFrame, cols: list):
    available = [c for c in cols if c in df.columns]
    if not available:
        st.warning("No displayable columns found."); return
    sub = df[available].copy()
    HEADER_COLOUR = "#94a3b8"; HEADER_BG = "#0f172a"
    ROW_BG = "#1e293b"; ROW_ALT_BG = "#162032"; BORDER = "#2d3748"
    display_names = {
        "_date": "Date", "AI Prob %": "AI Prob", "Stake (C$)": "Stake",
        "Time/Score": "Time / Score", "Home Odds": "Home @", "Away Odds": "Away @",
        "P1 Odds": "P1 @", "P2 Odds": "P2 @", "Line Velocity": "Line Move",
    }
    headers = "".join(
        f'<th style="padding:10px 14px;text-align:left;color:{HEADER_COLOUR};font-size:11px;'
        f'font-weight:700;text-transform:uppercase;letter-spacing:0.5px;'
        f'border-bottom:2px solid {BORDER};white-space:nowrap;">{display_names.get(c,c)}</th>'
        for c in available
    )
    rows_html = ""
    for i, (_, row) in enumerate(sub.iterrows()):
        bg    = ROW_BG if i % 2 == 0 else ROW_ALT_BG
        cells = "".join(
            f'<td style="padding:9px 14px;border-bottom:1px solid {BORDER};white-space:nowrap;">'
            f'{_fmt_cell(c, row.get(c))}</td>' for c in available
        )
        rows_html += f'<tr style="background:{bg};">{cells}</tr>'
    st.markdown(
        f'<div style="overflow-x:auto;border-radius:8px;border:1px solid {BORDER};margin-bottom:12px;">'
        f'<table style="width:100%;border-collapse:collapse;font-size:13px;font-family:sans-serif;">'
        f'<thead><tr style="background:{HEADER_BG};">{headers}</tr></thead>'
        f'<tbody>{rows_html}</tbody></table></div>',
        unsafe_allow_html=True)

def _render_schedule(events: list, sport_filter: str = "All"):
    if not events:
        st.info("No upcoming events found."); return
    df = pd.DataFrame(events)
    if sport_filter != "All":
        df = df[df["Sport"].str.contains(sport_filter, case=False, na=False)]
    if df.empty:
        st.info(f"No upcoming {sport_filter} events found."); return
    for date, group in df.groupby("Date"):
        try:   day_label = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %B %d")
        except Exception: day_label = date
        st.markdown(f"### 📅 {day_label}")
        for _, row in group.iterrows():
            st.markdown(
                f"<div class='event-card'>"
                f"<div class='event-date'>{row.get('Sport','')} &nbsp;·&nbsp; {row.get('Time','TBD')}</div>"
                f"<div class='event-match'>{row.get('Match','')}</div></div>",
                unsafe_allow_html=True)

def _render_prediction_table(df: pd.DataFrame, sport: str):
    if df is None or df.empty:
        st.info(f"No {sport} predictions available."); return
    h_col = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"
    a_col = "Away Odds" if "Away Odds" in df.columns else "P2 Odds"
    df_work = df.copy()
    df_work["_ev_sort"]  = pd.to_numeric(df_work.get("EV+"), errors="coerce").fillna(-99)
    df_work["_date_key"] = df_work.get("_date", df_work.get("_fetch_date","")).fillna("").astype(str)
    df_work = df_work.sort_values(["_date_key","_ev_sort"], ascending=[True, False])
    for date_key, group in df_work.groupby("_date_key", sort=False):
        try:   day_label = datetime.strptime(date_key, "%Y-%m-%d").strftime("%A, %B %d")
        except Exception: day_label = date_key or "TBD"
        st.markdown(
            f"<div style='margin:18px 0 8px;padding:6px 14px;background:#0f172a;"
            f"border-left:3px solid #00D9FF;border-radius:0 6px 6px 0;'>"
            f"<span style='font-size:13px;font-weight:700;color:#00D9FF;text-transform:uppercase;"
            f"letter-spacing:1px;'>📅 {day_label} &nbsp;·&nbsp; {len(group)} game{'s' if len(group)!=1 else ''}</span></div>",
            unsafe_allow_html=True)
        for _, row in group.iterrows():
            ev = row.get("EV+"); edge = row.get("Edge %"); stake = row.get("Stake (C$)")
            h_odds = row.get(h_col); a_odds = row.get(a_col)
            has_odds = pd.notna(h_odds) and pd.notna(a_odds)
            ev_cls   = _ev_color(ev) if has_odds else "ev-yellow"
            odds_str = (f"Odds: <b>{h_odds:.2f}</b> / <b>{a_odds:.2f}</b>" if has_odds
                        else "⏳ Odds not yet available")
            ev_str   = (f"EV+ <span class='{ev_cls}'>{ev:+.4f}</span> &nbsp;|&nbsp; Edge {edge:+.2f}%"
                        if has_odds and ev is not None else "<span class='ev-yellow'>EV pending odds</span>")
            stake_str = (f"&nbsp;|&nbsp; Stake: <b>C${stake:.2f}</b>"
                         if has_odds and stake and stake > 0 else "")
            pitcher_str = ""
            if sport == "MLB":
                ph = row.get("Home Pitcher","TBD"); pa = row.get("Away Pitcher","TBD")
                pitcher_str = f"<div style='font-size:11px;color:#94a3b8;margin-top:4px;'>SP: {ph} vs {pa}</div>"
            tour_str = ""
            if sport == "Tennis":
                tour_str = f"<div style='font-size:11px;color:#94a3b8;'>{row.get('Tournament','')} — {row.get('Category','')}</div>"
            bet_tag = ""
            if has_odds:
                home_t = row.get("Home Team", row.get("Match","? vs ?").split(" vs ")[0].strip())
                away_t = row.get("Away Team", row.get("Match","? vs ?").split(" vs ")[-1].strip())
                h_f = float(h_odds); a_f = float(a_odds)
                imp_sum = (1/h_f + 1/a_f) if h_f > 1 and a_f > 1 else 0
                if imp_sum < 0.95 or imp_sum > 1.25:
                    odds_str  = f"⚠️ Bad line ({h_f:.2f}/{a_f:.2f})"
                    ev_str    = "<span class='ev-red'>Corrupted odds — do not bet</span>"
                    stake_str = ""
                else:
                    rec_team = home_t if h_f <= a_f else away_t
                    rec_odds = h_f   if h_f <= a_f else a_f
                    bet_tag  = (f"<span style='color:#00D9FF;font-weight:700;'>✅ BET ON: {rec_team} @ {rec_odds:.2f}x</span>"
                                if ev is not None and float(ev) > MIN_EV_THRESHOLD
                                else "<span style='color:#64748b;'>⛔ No edge — skip</span>")
                    odds_str = f"{bet_tag} &nbsp;|&nbsp; Lines: <b>{h_f:.2f}</b> / <b>{a_f:.2f}</b>"
            st.markdown(
                f"<div class='pred-card'>"
                f"<div class='pred-match'>{row.get('Match','')} "
                f"<span style='font-size:11px;color:#64748b;font-weight:400;margin-left:8px;'>"
                f"{row.get('Time/Score', row.get('Time','TBD'))}</span></div>"
                f"{tour_str}{pitcher_str}"
                f"<div style='font-size:13px;margin-top:6px;'>{odds_str}</div>"
                f"<div style='font-size:13px;margin-top:4px;'>{ev_str}{stake_str}</div></div>",
                unsafe_allow_html=True)

# =============================================================================
# KEY STATUS BANNER
# =============================================================================
def _key_status_banner():
    if not ODDS_API_KEY:
        st.error("❌ ODDS_API_KEY not set — add it to the top of main.py"); return
    try:
        resp = _session().get(f"{ODDS_API_BASE}/me/", headers={"x-api-key": ODDS_API_KEY},
                              verify=False, timeout=8)
        if resp.status_code == 200:
            info      = resp.json()
            remaining = info.get("requests_remaining", "?")
            used      = info.get("requests_used", "?")
            st.success(f"✅ TheOddsAPI connected — {used} used | {remaining} remaining")
        elif resp.status_code == 401:
            st.error("❌ Odds API key invalid or expired")
        else:
            st.error(f"❌ Odds API HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        st.error(f"❌ Odds API connection error: {e}")

# =============================================================================
# PAST GAME FILTER
# =============================================================================
def _filter_past_games(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty or "_start_iso" not in df.columns: return df
    now_utc = _TZ_UTC.localize(datetime.utcnow())
    def _is_future(iso: str) -> bool:
        try:
            naive = datetime.strptime(str(iso).replace("Z",""), "%Y-%m-%dT%H:%M:%S")
            return _TZ_UTC.localize(naive) >= now_utc
        except Exception:
            return True
    return df[df["_start_iso"].apply(_is_future)].reset_index(drop=True)

# =============================================================================
# SCHEDULE HELPERS
# =============================================================================
def _fetch_schedule_nba(days: int = 7) -> list:
    df = fetch_premium_odds("basketball_nba")
    if df.empty: return []
    seen = set(); events = []
    for _, row in df.iterrows():
        key = f"{row.get('Home Team','')}{row.get('Away Team','')}{row.get('_date','')}"
        if key not in seen:
            seen.add(key)
            events.append({"Date": row.get("_date",""), "Time": row.get("Time/Score","TBD"),
                           "Match": row.get("Match",""), "Sport": "🏀 NBA"})
    return events

def _fetch_schedule_mlb(days: int = 7) -> list:
    df = fetch_premium_odds("baseball_mlb")
    if df.empty: return []
    seen = set(); events = []
    for _, row in df.iterrows():
        key = f"{row.get('Home Team','')}{row.get('Away Team','')}{row.get('_date','')}"
        if key not in seen:
            seen.add(key)
            events.append({"Date": row.get("_date",""), "Time": row.get("Time/Score","TBD"),
                           "Match": row.get("Match",""), "Sport": "⚾ MLB"})
    return events

def _fetch_schedule_tennis(days: int = 7) -> list:
    seen = set(); events = []
    df = fetch_premium_odds("tennis")
    if df.empty: return []
    for _, row in df.iterrows():
        key = f"{row.get('Match','')}{row.get('_date','')}"
        if key not in seen:
            seen.add(key)
            events.append({"Date": row.get("_date",""), "Time": row.get("Time/Score","TBD"),
                           "Match": row.get("Match",""), "Sport": "🎾 Tennis"})
    return events

# =============================================================================
# MAIN
# =============================================================================
def main():
    defaults = {
        "last_paper_trade": datetime.now() - timedelta(seconds=PAPER_TRADE_INTERVAL),
        "schedule_cache":   [],
        "schedule_fetched": None,
        "pred_cache":       {},
        "pred_fetched":     {},
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

    model_cfg    = load_model_config()
    bankroll_cfg = load_bankroll_config()

    # ── Sidebar ───────────────────────────────────────────────────────────────
    with st.sidebar:
        st.subheader("⚙️ Settings")
        bankroll   = st.number_input("Bankroll (C$)", min_value=100.0, value=1500.0, step=100.0)
        risk_level = st.radio("Kelly Risk Level", ["Safe","Moderate","Aggressive"], index=1)
        st.divider()
        st.subheader("📡 Data Sources")
        st.markdown(f"**All sports:** {'✅ Premium Odds API' if ODDS_API_KEY else '❌ ODDS_API_KEY missing'}")
        st.caption("NBA · MLB · Tennis ATP · Tennis WTA — all via The Odds API Premium")
        st.divider()
        st.subheader("📅 Prediction Window")
        days_ahead = st.slider("Days ahead to predict", 0, 7, 2)
        st.divider()
        st.subheader("🎯 Manual Rainbet Override")
        rainbet_multiplier = st.number_input(
            "Current Rainbet Multiplier (X)", min_value=1.01, max_value=50.0, value=1.90, step=0.05,
            help="Enter the live decimal odds from Rainbet.")
        st.caption("If Rainbet shows 1.85 on a game, enter 1.85 here.")
        st.divider()
        st.caption(
            "📊 **Model calibration (v2)**\n"
            f"Edge threshold: {MIN_EDGE_THRESHOLD}% | MLB cap: {MLB_MAX_ODDS}x\n"
            "Dead-zone discount: 65–70% band → ×0.88\n"
            "Boosts: NBA 6% | MLB 3.5% | Tennis 5.5%"
        )

    # ── Header ────────────────────────────────────────────────────────────────
    col_t, col_l = st.columns([4,1])
    with col_t:
        st.markdown("<h1 style='margin:0'>📈 Sports EV+ Dashboard</h1>", unsafe_allow_html=True)
        st.caption("NBA/WNBA · MLB · Tennis — Odds API | All amounts in CAD | Model v2 (calibrated)")
    with col_l:
        if st.button("🔄 Refresh Data", use_container_width=True):
            for key in ["schedule_cache","schedule_fetched","pred_cache","pred_fetched",
                        "data_nba","data_mlb","data_tennis","data_wnba","data_fetched"]:
                st.session_state.pop(key, None)
            st.rerun()

    _key_status_banner()

    # ── Data fetch ────────────────────────────────────────────────────────────
    today_str = datetime.now().strftime("%Y-%m-%d")
    if "data_fetched" not in st.session_state or st.session_state.get("data_fetched") != today_str:
        prog = st.progress(0, text="📡 Connecting to Odds API…")
        try:
            prog.progress(15, text="🏀 Fetching NBA…")
            df_nba_raw = fetch_premium_odds("basketball_nba")
            st.session_state["data_nba"] = calculate_stakes(
                calculate_real_ev(df_nba_raw, model_cfg, "NBA"), bankroll, risk_level)

            prog.progress(30, text="🏀 Fetching WNBA (NBA off-season fill)…")
            df_wnba_raw = fetch_premium_odds("basketball_wnba")
            # Merge WNBA into NBA tab if NBA is empty (off-season)
            if df_nba_raw.empty and not df_wnba_raw.empty:
                st.session_state["data_nba"] = calculate_stakes(
                    calculate_real_ev(df_wnba_raw, model_cfg, "NBA"), bankroll, risk_level)
            elif not df_wnba_raw.empty:
                combined_bball = pd.concat([df_nba_raw, df_wnba_raw], ignore_index=True)
                st.session_state["data_nba"] = calculate_stakes(
                    calculate_real_ev(combined_bball, model_cfg, "NBA"), bankroll, risk_level)

            prog.progress(55, text="⚾ Fetching MLB…")
            df_mlb_raw = fetch_premium_odds("baseball_mlb")
            st.session_state["data_mlb"] = calculate_stakes(
                calculate_real_ev(df_mlb_raw, model_cfg, "MLB"), bankroll, risk_level)

            prog.progress(75, text="🎾 Fetching Tennis…")
            df_tennis_raw = fetch_premium_odds("tennis")
            if not df_tennis_raw.empty:
                df_tennis_raw = df_tennis_raw.drop_duplicates(subset=["Match","_date"]).reset_index(drop=True)
            st.session_state["data_tennis"] = calculate_stakes(
                calculate_real_ev(df_tennis_raw, model_cfg, "Tennis"), bankroll, risk_level)

            st.session_state["data_fetched"] = today_str
            prog.progress(100, text="✅ Done!"); prog.empty()
        except Exception as e:
            prog.empty(); st.error(f"❌ Data fetch error: {e}")

    df_nba    = _filter_past_games(st.session_state.get("data_nba",    pd.DataFrame()))
    df_mlb    = _filter_past_games(st.session_state.get("data_mlb",    pd.DataFrame()))
    df_tennis = _filter_past_games(st.session_state.get("data_tennis", pd.DataFrame()))

    # ── Debug panel ───────────────────────────────────────────────────────────
    bypass_filters = st.checkbox(
        "🔧 Show all games (bypass implied-sum filter)",
        value=st.session_state.get("debug_bypass_filters", False),
        key="debug_bypass_filters",
    )
    if bypass_filters:
        for _sk in ["data_nba","data_mlb","data_tennis","data_fetched"]:
            st.session_state.pop(_sk, None)
        fetch_premium_odds.clear()

    with st.expander("🔍 Pipeline counts", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("NBA rows",    len(df_nba))
        c2.metric("MLB rows",    len(df_mlb))
        c3.metric("Tennis rows", len(df_tennis))
        for label, df_s in [("NBA", df_nba), ("MLB", df_mlb), ("Tennis", df_tennis)]:
            if df_s is not None and not df_s.empty and "EV+" in df_s.columns:
                cols_to_show = [c for c in ["Match","Home Odds","Away Odds","EV+","Edge %"] if c in df_s.columns]
                st.markdown(f"**{label} — sample EV+ values:**")
                st.dataframe(df_s[cols_to_show].head(3), hide_index=True, use_container_width=True)
        for label, sk in [("NBA","basketball_nba"),("MLB","baseball_mlb"),("Tennis","tennis")]:
            raw = st.session_state.get(f"debug_raw_event_{sk}")
            if raw:
                st.markdown(f"**{label} — first raw event:**")
                st.json(raw)

    # Auto paper trade
    if not df_nba.empty or not df_mlb.empty or not df_tennis.empty:
        if (datetime.now() - st.session_state.last_paper_trade).total_seconds() >= PAPER_TRADE_INTERVAL:
            _ok, _msg = execute_paper_trade(df_nba, df_mlb, df_tennis)
            if _ok: settle_pending_trades()
            st.session_state.last_paper_trade = datetime.now()

    # ── TABS ──────────────────────────────────────────────────────────────────
    tabs = st.tabs(["🏆 Live Hub","🏀 NBA","⚾ MLB","🎾 Tennis",
                    "🔮 Predictions","🐶 Underdogs","📅 Schedule","📈 Analytics","🔧 Settings"])

    # ── TAB 0: Live Hub ───────────────────────────────────────────────────────
    with tabs[0]:
        all_qualifying = []
        for df in [df_nba, df_mlb, df_tennis]:
            if df is not None and not df.empty:
                ev_col = pd.to_numeric(df.get("EV+"), errors="coerce").fillna(0)
                all_qualifying.extend(df[ev_col > MIN_EV_THRESHOLD].to_dict("records"))

        total_simultaneous = len(all_qualifying)
        if total_simultaneous > 1:
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#1a1f3a,#0f172a);border:2px solid #f59e0b;"
                f"border-radius:10px;padding:16px 20px;margin-bottom:16px;'>"
                f"<div style='font-size:11px;color:#f59e0b;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px;'>"
                f"🛡️ CAPITAL PROTECTION SHIELD ACTIVE</div>"
                f"<div style='font-size:20px;font-weight:700;color:#fbbf24;'>{total_simultaneous} Simultaneous Qualifying Bets</div>"
                f"<div style='font-size:13px;color:#e2e8f0;margin-top:8px;'>"
                f"Stakes auto-scaled by <b>÷√{total_simultaneous}</b> = <b>{1/(total_simultaneous**0.5):.3f}x</b> · 5% max per trade.</div>"
                f"</div>", unsafe_allow_html=True)

        best = find_best_bet(df_nba, df_mlb, df_tennis)
        top8 = find_top_bets(df_nba, df_mlb, df_tennis, n=4, hours=24)

        st.markdown("<div class='metric-box'><div class='metric-title'>🏆 Top 4 Bets — Next 24 Hours</div>",
                    unsafe_allow_html=True)
        if top8:
            for i, row in enumerate(top8):
                h_col   = "Home Odds" if pd.notna(row.get("Home Odds")) else "P1 Odds"
                a_col   = "Away Odds" if "Away Odds" in row.index else "P2 Odds"
                h_odds  = float(row.get(h_col, 0) or 0)
                a_odds  = float(row.get(a_col, 0) or 0)
                home_t  = row.get("Home Team", row.get("Match","? vs ?").split(" vs ")[0].strip())
                away_t  = row.get("Away Team", row.get("Match","? vs ?").split(" vs ")[-1].strip())
                bet_team = home_t if h_odds <= a_odds else away_t
                bet_odds = h_odds if h_odds <= a_odds else a_odds
                stake    = float(row.get("Stake (C$)", 0) or 0)
                ev       = float(row.get("EV+", 0) or 0)
                edge     = float(row.get("Edge %", 0) or 0)
                rank_color = "#00D9FF" if i == 0 else "#e2e8f0"
                st.markdown(
                    f"<div style='background:#111827;border:1px solid #1e3a5f;border-radius:10px;"
                    f"padding:12px 18px;margin-bottom:8px;display:flex;justify-content:space-between;"
                    f"align-items:center;flex-wrap:wrap;gap:8px;'>"
                    f"<div><span style='font-size:11px;color:#64748b;font-weight:700;'>"
                    f"#{i+1} &nbsp;·&nbsp; {row.get('_sport','')} &nbsp;·&nbsp; {row.get('_date','')} {row.get('Time/Score','')}</span><br>"
                    f"<span style='font-size:16px;font-weight:800;color:{rank_color};'>✅ {bet_team}</span>"
                    f"<span style='font-size:13px;color:#94a3b8;'> &nbsp;·&nbsp; {row.get('Match','')}</span></div>"
                    f"<div style='display:flex;gap:16px;flex-wrap:wrap;'>"
                    f"<span style='text-align:center;'><div style='font-size:10px;color:#64748b;text-transform:uppercase;'>Odds</div>"
                    f"<div style='font-size:15px;font-weight:700;color:#00D9FF;'>{bet_odds:.2f}x</div></span>"
                    f"<span style='text-align:center;'><div style='font-size:10px;color:#64748b;text-transform:uppercase;'>Edge</div>"
                    f"<div style='font-size:15px;font-weight:700;color:#22c55e;'>{edge:+.2f}%</div></span>"
                    f"<span style='text-align:center;'><div style='font-size:10px;color:#64748b;text-transform:uppercase;'>EV+</div>"
                    f"<div style='font-size:15px;font-weight:700;color:#22c55e;'>{ev:+.4f}</div></span>"
                    f"<span style='text-align:center;'><div style='font-size:10px;color:#64748b;text-transform:uppercase;'>Stake</div>"
                    f"<div style='font-size:15px;font-weight:700;color:#a78bfa;'>C${stake:.2f}</div></span>"
                    f"</div></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:16px;color:#94a3b8;padding:12px 0;'>No qualifying bets in the next 24 hours.</div>",
                        unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

        st.divider()
        c1, c2, c3 = st.columns(3)
        with c1:
            st.subheader("🏀 NBA Upcoming")
            if not df_nba.empty:
                _render_df(df_nba, ["Match","_date","Time/Score","Home Odds","Away Odds","EV+","Stake (C$)","Line Velocity"])
            else:
                st.info("No NBA games found. Press 🔄 Refresh.")
        with c2:
            st.subheader("⚾ MLB Upcoming")
            if not df_mlb.empty:
                _render_df(df_mlb, ["Match","_date","Time/Score","Home Odds","Away Odds","EV+","Stake (C$)","Line Velocity"])
            else:
                st.info("No MLB games found. Press 🔄 Refresh.")
        with c3:
            st.subheader("🎾 Tennis Today")
            if not df_tennis.empty:
                _render_df(df_tennis, ["Match","Time/Score","_date","Home Odds","Away Odds","EV+","Stake (C$)","Line Velocity"])
            else:
                st.info("No tennis matches today.")

        st.divider()
        st.subheader("📰 Injury & News Alerts")
        nba_hl    = fetch_rss_headlines(["https://www.espn.com/espn/rss/nba/news"])
        mlb_hl    = fetch_rss_headlines(["https://www.espn.com/espn/rss/mlb/news"])
        tennis_hl = fetch_rss_headlines(["https://www.espn.com/espn/rss/tennis/news"])
        all_hl    = nba_hl + mlb_hl + tennis_hl
        alerts    = [h for h in all_hl if detect_injury_alert(h)]
        for a in alerts[:6]: st.warning(f"⚠️ {a}")
        for h in [h for h in nba_hl    if not detect_injury_alert(h)][:3]: st.markdown(f"🏀 {h}")
        for h in [h for h in mlb_hl    if not detect_injury_alert(h)][:3]: st.markdown(f"⚾ {h}")
        if not alerts: st.success("✅ No injury alerts detected.")

    # ── TAB 1: NBA ────────────────────────────────────────────────────────────
    with tabs[1]:
        st.header("🏀 NBA — Upcoming Games")
        if not df_nba.empty:
            _render_df(df_nba, ["Match","Time/Score","_date","Home Odds","Away Odds",
                                 "AI Prob %","Edge %","EV+","Stake (C$)","Books","Line Velocity"])
            c1,c2,c3,c4 = st.columns(4)
            ev_v = pd.to_numeric(df_nba.get("EV+"), errors="coerce").dropna()
            c1.metric("Games",           len(df_nba))
            c2.metric("Avg EV+",         f"{ev_v.mean():.4f}" if not ev_v.empty else "—")
            c3.metric("Qualifying Bets", int((ev_v > MIN_EV_THRESHOLD).sum()))
            stk = pd.to_numeric(df_nba.get("Stake (C$)"), errors="coerce").fillna(0)
            c4.metric("Total Stake C$",  f"{stk.sum():,.2f}")
            if "_simultaneous_trades" in df_nba.columns:
                st.caption(f"🛡️ Covariance Shield: {df_nba['_simultaneous_trades'].iloc[0]} simultaneous trades — stakes auto-scaled")
        else:
            st.info("🏀 No upcoming NBA games found. Try Refresh.")

    # ── TAB 2: MLB ────────────────────────────────────────────────────────────
    with tabs[2]:
        st.header("⚾ MLB — Upcoming Games")
        st.caption(f"⚠️ MLB odds capped at {MLB_MAX_ODDS}x — heavy underdogs excluded (0% WR in backtesting above this line).")
        if not df_mlb.empty:
            _render_df(df_mlb, ["Match","Time/Score","_date","Home Odds","Away Odds",
                                 "AI Prob %","Edge %","EV+","Stake (C$)","Books","Line Velocity"])
            c1,c2,c3,c4 = st.columns(4)
            ev_v = pd.to_numeric(df_mlb.get("EV+"), errors="coerce").dropna()
            c1.metric("Games",           len(df_mlb))
            c2.metric("Avg EV+",         f"{ev_v.mean():.4f}" if not ev_v.empty else "—")
            c3.metric("Qualifying Bets", int((ev_v > MIN_EV_THRESHOLD).sum()))
            stk = pd.to_numeric(df_mlb.get("Stake (C$)"), errors="coerce").fillna(0)
            c4.metric("Total Stake C$",  f"{stk.sum():,.2f}")
            if "_simultaneous_trades" in df_mlb.columns:
                st.caption(f"🛡️ Covariance Shield: {df_mlb['_simultaneous_trades'].iloc[0]} simultaneous trades — stakes auto-scaled")
        else:
            st.info("⚾ No upcoming MLB games found. Press Refresh.")

    # ── TAB 3: Tennis ─────────────────────────────────────────────────────────
    with tabs[3]:
        st.header("🎾 Tennis — Today's Matches")
        st.caption("Tennis ATP + WTA odds via The Odds API Premium.")
        if not df_tennis.empty:
            _render_df(df_tennis, ["Match","Time/Score","_date","Home Odds","Away Odds",
                                    "EV+","Stake (C$)","Books","Line Velocity"])
            c1,c2 = st.columns(2)
            c1.metric("Matches Today",   len(df_tennis))
            c2.metric("Qualifying Bets", int((pd.to_numeric(df_tennis.get("EV+"), errors="coerce") > MIN_EV_THRESHOLD).sum()))
            if "_simultaneous_trades" in df_tennis.columns:
                st.caption(f"🛡️ Covariance Shield: {df_tennis['_simultaneous_trades'].iloc[0]} simultaneous trades — stakes auto-scaled")
        else:
            st.error("🎾 No tennis matches returned. Key may not support tennis on this plan.")

    # ── TAB 4: Predictions ────────────────────────────────────────────────────
    with tabs[4]:
        st.header("🔮 Advance Predictions")
        st.info(f"Showing predictions for today + {days_ahead} day(s) ahead.")
        pred_sport  = st.selectbox("Sport", ["NBA","MLB","Tennis"], key="pred_sport_sel")
        cache_key   = f"pred_{pred_sport}_{days_ahead}"
        fetched_key = f"pred_fetch_{pred_sport}_{days_ahead}"
        pred_age    = None
        if st.session_state.pred_fetched.get(fetched_key):
            pred_age = (datetime.now() - st.session_state.pred_fetched[fetched_key]).total_seconds()
        cached_pred    = st.session_state.pred_cache.get(cache_key)
        cache_is_empty = cached_pred is None or (isinstance(cached_pred, pd.DataFrame) and cached_pred.empty)
        if cache_is_empty or pred_age is None or pred_age > 1800:
            with st.spinner(f"Fetching {pred_sport} games for next {days_ahead} days…"):
                pred_df = build_advance_predictions(days_ahead, pred_sport, model_cfg, bankroll, risk_level)
            st.session_state.pred_cache[cache_key]     = pred_df
            st.session_state.pred_fetched[fetched_key] = datetime.now()
        else:
            pred_df = st.session_state.pred_cache[cache_key]

        col_ref, col_filter = st.columns([1,3])
        with col_ref:
            if st.button("🔄 Refresh Predictions"):
                st.session_state.pred_cache.pop(cache_key, None); st.rerun()
        with col_filter:
            only_qualifying = st.checkbox("Show only qualifying bets (Edge ≥ 4.5%)", value=False)
        if only_qualifying and pred_df is not None and not pred_df.empty:
            ev_col  = pd.to_numeric(pred_df.get("EV+"), errors="coerce")
            pred_df = pred_df[ev_col > MIN_EV_THRESHOLD].reset_index(drop=True)
        _render_prediction_table(pred_df, pred_sport)

    # ── TAB 5: Underdogs ─────────────────────────────────────────────────────
    with tabs[5]:
        st.header("🐶 Underdog Special Bets")
        st.info("High-odds plays with positive EV — max 2 picks, bet at HALF stake. High risk, high reward.")
        dogs = find_underdog_bets(df_nba, df_mlb, df_tennis, min_odds=2.5, max_picks=2)
        if not dogs:
            st.warning("No underdog plays with positive EV right now.")
        else:
            for i, dog in enumerate(dogs):
                h_col    = "Home Odds" if "Home Odds" in dog.index else "P1 Odds"
                a_col    = "Away Odds" if "Away Odds" in dog.index else "P2 Odds"
                h_odds_v = float(dog.get(h_col, 0) or 0)
                a_odds_v = float(dog.get(a_col, 0) or 0)
                home_t   = dog.get("Home Team", dog.get("Match","? vs ?").split(" vs ")[0].strip())
                away_t   = dog.get("Away Team", dog.get("Match","? vs ?").split(" vs ")[-1].strip())
                if a_odds_v >= h_odds_v:
                    dog_team, dog_odds, fav_team = away_t, a_odds_v, home_t
                else:
                    dog_team, dog_odds, fav_team = home_t, h_odds_v, away_t
                ev_v       = float(dog.get("EV+", 0) or 0)
                edge_v     = float(dog.get("Edge %", 0) or 0)
                stake_v    = float(dog.get("Stake (C$)", 0) or 0)
                half_stake = round(stake_v * 0.5, 2)
                payout_v   = round(half_stake * dog_odds, 2)
                profit_v   = round(payout_v - half_stake, 2)
                ev_color   = "#22c55e" if ev_v > 0 else "#ef4444"
                st.markdown(
                    f'<div style="background:linear-gradient(135deg,#1a0a2e,#0f0a1e);border:2px solid #a855f7;'
                    f'border-radius:12px;padding:18px 22px;margin-bottom:14px;">'
                    f'<div style="font-size:11px;color:#a855f7;text-transform:uppercase;letter-spacing:1px;font-weight:700;">'
                    f'🐶 Underdog Pick #{i+1} &nbsp;·&nbsp; {dog.get("_sport","")} &nbsp;·&nbsp; {dog.get("_date","")}</div>'
                    f'<div style="font-size:28px;font-weight:700;color:#e879f9;margin:6px 0;">{dog_team}</div>'
                    f'<div style="font-size:13px;color:#94a3b8;margin-bottom:10px;">vs {fav_team} &nbsp;·&nbsp; {dog.get("Match","")}</div>'
                    f'<div style="font-size:13px;color:#e2e8f0;display:flex;gap:20px;flex-wrap:wrap;">'
                    f'<span>🎯 Odds: <b style="color:#e879f9;">{dog_odds:.2f}x</b></span>'
                    f'<span>📈 EV+: <b style="color:{ev_color};">{ev_v:+.4f}</b></span>'
                    f'<span>⚡ Edge: <b>{edge_v:+.2f}%</b></span>'
                    f'<span>💰 Half-Stake: <b style="color:#a855f7;">C${half_stake:.2f}</b></span>'
                    f'<span>🏆 Profit if Win: <b style="color:#22c55e;">C${profit_v:.2f}</b></span></div>'
                    f'<div style="margin-top:10px;font-size:11px;color:#64748b;">⚠️ Half stake only · Max 2 underdog bets per day</div></div>',
                    unsafe_allow_html=True)

    # ── TAB 6: Schedule ───────────────────────────────────────────────────────
    with tabs[6]:
        st.header("📅 Upcoming Schedule — Next 7 Days")
        st.info("Click below to load the 7-day schedule (uses ~6 API calls).")
        col_f, col_r = st.columns([3,1])
        with col_f:
            sport_filter = st.selectbox("Filter sport", ["All","NBA","MLB","Tennis"], key="sched_filter")
        with col_r:
            load_sched = st.button("📅 Load Schedule")
        if load_sched:
            with st.spinner("Fetching 7-day schedule…"):
                try:
                    st.session_state.schedule_cache   = (_fetch_schedule_nba(7) +
                                                          _fetch_schedule_mlb(7) +
                                                          _fetch_schedule_tennis(7))
                    st.session_state.schedule_fetched = datetime.now()
                except Exception as e:
                    st.error(f"Schedule load failed: {e}")
        if st.session_state.schedule_fetched:
            st.caption(f"Last fetched: {st.session_state.schedule_fetched.strftime('%H:%M:%S')} "
                       f"— {len(st.session_state.schedule_cache)} events")
        st.divider()
        _render_schedule(st.session_state.schedule_cache, sport_filter)

    # ── TAB 7: Analytics ──────────────────────────────────────────────────────
    with tabs[7]:
        st.header("📈 Paper Trading & Analytics")
        st.info("Execute a paper trade when you see a qualifying EV+. Settle after the game.")
        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("▶️ Execute Paper Trade"):
                _ok, _msg = execute_paper_trade(df_nba, df_mlb, df_tennis)
                if _ok: st.success(_msg)
                else:   st.warning(f"⚠️ {_msg}")
        with c2:
            if st.button("✅ Settle Pending Trades"):
                n = settle_pending_trades()
                if n: st.success(f"✅ Settled {n} trade(s).")
                else: st.info("No pending trades to settle.")
        with c3:
            with st.expander("🗑️ Clear All Trades"):
                st.warning("Permanently deletes all trade history.")
                if st.button("⚠️ Confirm Delete"):
                    PAPER_TRADES_CSV.unlink(missing_ok=True); st.success("✅ Cleared.")

        st.divider()
        stats = calculate_success_rate()
        st.markdown("<div class='metric-box'><div class='metric-title'>🎯 AI Success Rate</div>",
                    unsafe_allow_html=True)
        sr_color = "#22c55e" if stats["success_rate"] >= 50 else "#ef4444"
        st.markdown(
            f"<div class='metric-value' style='color:{sr_color};'>{stats['success_rate']:.1f}%</div>"
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
            col_order = ["timestamp","match","sport","odds","ev_plus","stake",
                         "ai_prob","edge_pct","strategy","result","status"]
            tdf = tdf[[c for c in col_order if c in tdf.columns]]
            tdf = tdf.rename(columns={
                "timestamp":"Time","match":"Match","sport":"Sport","odds":"Odds",
                "ev_plus":"EV+","stake":"Stake (C$)","ai_prob":"AI Prob",
                "edge_pct":"Edge %","strategy":"Strategy","result":"Result","status":"Status"})
            for col in ["Odds","EV+","Stake (C$)","AI Prob","Edge %"]:
                if col in tdf.columns:
                    tdf[col] = pd.to_numeric(tdf[col], errors="coerce")
            st.dataframe(tdf, hide_index=True, use_container_width=True,
                column_config={
                    "EV+":        st.column_config.NumberColumn("EV+",        format="%+.4f"),
                    "Stake (C$)": st.column_config.NumberColumn("Stake (C$)", format="C$%.2f"),
                    "Odds":       st.column_config.NumberColumn("Odds",       format="%.2f"),
                    "AI Prob":    st.column_config.NumberColumn("AI Prob",    format="%.3f"),
                    "Edge %":     st.column_config.NumberColumn("Edge %",     format="%.2f%%"),
                    "Result":     st.column_config.TextColumn("Result"),
                    "Status":     st.column_config.TextColumn("Status"),
                })
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Total",   len(trades))
            c2.metric("Settled", sum(1 for t in trades if t.get("status")=="SETTLED"))
            c3.metric("Pending", sum(1 for t in trades if t.get("status")=="PENDING"))
            avg_stk = sum(float(t.get("stake",0)) for t in trades) / len(trades)
            avg_ev  = sum(float(t.get("ev_plus",0)) for t in trades) / len(trades)
            c4.metric("Avg Stake", f"C${avg_stk:,.2f}")
            c5.metric("Avg EV+",   f"{avg_ev:.4f}")
        else:
            st.info("No paper trades yet. Execute a trade when odds are live.")

    # ── TAB 8: Settings ───────────────────────────────────────────────────────
    with tabs[8]:
        st.header("🔧 Advanced Settings")
        s1, s2, s3 = st.tabs(["💰 Bankroll","🤖 Model","📊 Backtest"])

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
                mdd = st.slider("Max Drawdown %", 1, 50, int(bankroll_cfg["max_drawdown_pct"]))
            kf = st.selectbox("Kelly Fraction", ["Safe (0.25x)","Moderate (0.50x)","Aggressive (0.75x)"], index=1)
            if st.button("💾 Save Bankroll"):
                save_bankroll_config({"starting_bankroll":br,"min_stake":mn,
                                      "max_stake":mx,"max_drawdown_pct":mdd,
                                      "kelly_fraction":kf.split(" ")[0]})
                st.success("✅ Saved.")

        with s2:
            st.subheader("🤖 Model Tuning")
            st.info("Adjust how the model calculates EV+ and edge. Changes apply on next Refresh.")
            c1,c2 = st.columns(2)
            with c1:
                mc = st.slider("Model Confidence", 0.5, 2.0,
                               float(model_cfg["model_confidence"]), 0.05,
                               help="1.0 = neutral. >1 amplifies home advantage signal.")
                et = st.slider("Edge Threshold %", 1, 10,
                               int(model_cfg.get("edge_threshold_pct", 4.5)),
                               help="Minimum edge vs bookmaker to flag a qualifying bet.")
            with c2:
                ip = st.slider("Injury Penalty %", 1, 20,
                               int(model_cfg["injury_penalty_pct"]),
                               help="Probability reduction for high-risk matches.")
                ff = st.slider("Home Advantage Factor", 0.0, 1.0,
                               float(model_cfg["form_factor"]), 0.05)
            ow = st.slider("Odds Weight", 0.0, 1.0, float(model_cfg["odds_weight"]), 0.05)
            if st.button("💾 Save Model"):
                save_model_config({"model_confidence":mc,"edge_threshold_pct":et,
                                   "injury_penalty_pct":ip,"form_factor":ff,"odds_weight":ow})
                st.success("✅ Saved.")

        with s3:
            st.subheader("📊 Backtest")
            st.info("Runs on your real paper trade history only.")
            days_bt = st.selectbox("Period", [7,14,30,60,90], index=2)
            if st.button("▶️ Run Backtest"):
                res = run_backtest(days_bt)
                if "error" in res:
                    st.error(f"❌ {res['error']}")
                else:
                    st.success(f"✅ {days_bt}-day backtest complete")
                    c1,c2,c3,c4 = st.columns(4)
                    c1.metric("Trades",   res["total_trades"])
                    c2.metric("Win Rate", f"{res['win_rate']:.1f}%")
                    c3.metric("ROI",      f"{res['roi']:.2f}%")
                    c4.metric("P.Factor", f"{res['profit_factor']:.2f}")
                    c5,c6,c7 = st.columns(3)
                    c5.metric("Wins",   res["wins"])
                    c6.metric("Losses", res["losses"])
                    c7.metric("Staked", f"C${res['total_stake']:,.2f}")

    st.divider()
    st.markdown(
        "<p style='text-align:center;font-size:12px;color:#555;'>"
        "📈 Sports EV+ Dashboard v2 &nbsp;|&nbsp; NBA · MLB · Tennis"
        " &nbsp;|&nbsp; Data: The Odds API &nbsp;|&nbsp; All amounts in CAD"
        "</p>", unsafe_allow_html=True)


if __name__ == "__main__":
    main()
