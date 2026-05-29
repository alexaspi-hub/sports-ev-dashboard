# =============================================================================
# Sports EV+ Dashboard — FULL REWRITE
# Sources:  API-Sports (NBA, MLB, Tennis) + The Odds API (NBA & MLB only)
# Features: Live scores, 48h advance predictions, best-odds consensus,
#           Kelly stakes (CAD), paper trading, MLB tab, backtest
#
# ⚠️  SETUP — ADD YOUR KEYS HERE BEFORE RUNNING:
#     API_SPORTS_KEY  — get free key at https://rapidapi.com/api-sports/
#     ODDS_API_KEY    — get free key at https://the-odds-api.com/
#                       (leave blank and the app will still work — Odds API
#                        is optional; it just enriches the NBA/MLB odds)
#
# NOTE: The Odds API does NOT support tennis. Tennis odds come from
#       API-Sports only.
#
# Run: streamlit run main.py
# =============================================================================

import ssl, os, time, random, json, socket, urllib3, feedparser, sqlite3
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta
from pathlib import Path

# ── SSL / proxy bypasses (required for restrictive local networks) ───────────
ssl._create_default_https_context = ssl._create_unverified_context
os.environ["CURL_CA_BUNDLE"]    = ""
os.environ["REQUESTS_CA_BUNDLE"] = ""
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Force IPv4 only (fixes NameResolutionError 11001 on some Windows networks)
_orig_getaddrinfo = socket.getaddrinfo
def _ipv4_only(*args, **kwargs):
    res = _orig_getaddrinfo(*args, **kwargs)
    return [r for r in res if r[0] == socket.AF_INET] or res
socket.getaddrinfo = _ipv4_only

# =============================================================================
# ⚠️  API KEYS — FILL IN YOUR KEYS HERE
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
/* ═══════════════════════════════════════════════════════
   SPORTS EV+ DASHBOARD — DARK THEME
   Text colours: slate-200 (#e2e8f0) on dark backgrounds
   Accent: cyan (#00D9FF)
   ═══════════════════════════════════════════════════════ */

/* ── App & page background ───────────────────────────── */
.stApp { background-color: #0e1117 !important; }
.main .block-container { background-color: #0e1117 !important; padding-top: 1rem !important; }

/* ── Sidebar ─────────────────────────────────────────── */
[data-testid="stSidebar"] { background-color: #0a0e27 !important; }
[data-testid="stSidebar"] .stMarkdown,
[data-testid="stSidebar"] label,
[data-testid="stSidebar"] p,
[data-testid="stSidebar"] span { color: #e2e8f0 !important; }

/* ── Global text — explicit selectors, no wildcard * ─── */
.stMarkdown p  { color: #e2e8f0 !important; }
.stMarkdown h1 { color: #f1f5f9 !important; font-weight: 700 !important; }
.stMarkdown h2 { color: #f1f5f9 !important; font-weight: 700 !important; }
.stMarkdown h3 { color: #cbd5e1 !important; font-weight: 600 !important; }
.stMarkdown li { color: #e2e8f0 !important; }

/* Streamlit widget labels */
.stTextInput  > label { color: #94a3b8 !important; }
.stSelectbox  > label { color: #94a3b8 !important; }
.stSlider     > label { color: #94a3b8 !important; }
.stNumberInput> label { color: #94a3b8 !important; }
.stRadio      > label { color: #94a3b8 !important; }
.stCheckbox   > label { color: #94a3b8 !important; }
.stRadio [data-testid="stMarkdownContainer"] p { color: #e2e8f0 !important; }

/* Headers inside tabs */
h1, h2, h3 { color: #f1f5f9 !important; }

/* Caption */
.stCaption p  { color: #64748b !important; font-size: 12px !important; }

/* ── Buttons ─────────────────────────────────────────── */
.stButton > button {
    color: #f1f5f9 !important;
    background: #1e293b !important;
    border: 1px solid #334155 !important;
    border-radius: 6px !important;
    font-weight: 600 !important;
}
.stButton > button:hover {
    background: #334155 !important;
    border-color: #00D9FF !important;
    color: #00D9FF !important;
}

/* ── Metrics ─────────────────────────────────────────── */
[data-testid="stMetricLabel"]  { color: #94a3b8 !important; font-size: 12px !important; }
[data-testid="stMetricValue"]  { color: #00D9FF !important; font-size: 28px !important; }
[data-testid="stMetricDelta"]  { color: #22c55e !important; }

/* ── Tabs ────────────────────────────────────────────── */
.stTabs [data-baseweb="tab-list"] { background: transparent !important; gap: 4px; }
.stTabs [role="tab"] {
    color: #64748b !important;
    font-weight: 600 !important;
    font-size: 13px !important;
    background: transparent !important;
    border-radius: 6px 6px 0 0 !important;
    padding: 8px 16px !important;
}
.stTabs [role="tab"]:hover { color: #e2e8f0 !important; background: #1e293b !important; }
.stTabs [role="tab"][aria-selected="true"] {
    color: #00D9FF !important;
    background: #0f172a !important;
    border-bottom: 3px solid #00D9FF !important;
}

/* ── DataFrame — use st.dataframe dark mode via column_config ────────────── */
/* The iframe cannot be penetrated by CSS — we force the outer wrapper dark   */
[data-testid="stDataFrame"] > div {
    background: #1e293b !important;
    border-radius: 8px !important;
    border: 1px solid #334155 !important;
}
/* Inner scrollable container */
.dvn-scroller { background: #1e293b !important; }

/* ── Alert boxes — keep their native colours but fix text ── */
[data-testid="stAlert"] { border-radius: 8px !important; }

/* ── Progress bar ────────────────────────────────────── */
[data-testid="stProgressBar"] > div > div { background-color: #00D9FF !important; }
[data-testid="stProgressBar"] { background: #1e293b !important; }

/* ── Select / input backgrounds ─────────────────────── */
.stSelectbox [data-baseweb="select"] > div {
    background-color: #1e293b !important;
    border-color: #334155 !important;
    color: #e2e8f0 !important;
}
.stNumberInput input, .stTextInput input {
    background-color: #1e293b !important;
    color: #e2e8f0 !important;
    border-color: #334155 !important;
}

/* ── Divider ─────────────────────────────────────────── */
hr { border-color: #1e293b !important; }

/* ── Custom card components ── */
.metric-box {
    background: linear-gradient(135deg, #1a1f3a 0%, #0f172a 100%);
    border: 2px solid #00D9FF; border-radius: 10px; padding: 20px; margin: 10px 0;
}
.metric-title { font-size: 11px; color: #94a3b8 !important; font-weight: 700;
                text-transform: uppercase; letter-spacing: 1px; }
.metric-value { font-size: 26px; color: #00D9FF !important; font-weight: bold; margin-top: 6px; }

.pred-card   { background:#111827; border:1px solid #1e3a5f; border-radius:10px;
               padding:14px 18px; margin-bottom:10px; }
.pred-match  { font-size:14px; font-weight:700; color:#f1f5f9 !important; margin-bottom:6px; }

.event-card  { background:#111827; border:1px solid #1e293b; border-radius:8px;
               padding:12px 16px; margin-bottom:8px; }
.event-date  { font-size:11px; color:#00D9FF !important; font-weight:700;
               text-transform:uppercase; letter-spacing:1px; margin-bottom:4px; }
.event-match { font-size:15px; font-weight:700; color:#f1f5f9 !important; }

.key-warning { background:#2d1a0a; border:1px solid #f59e0b; border-radius:8px;
               padding:14px 18px; margin-bottom:16px; }
.key-warning * { color: #fbbf24 !important; }

.ev-green  { color:#22c55e !important; font-weight:700; }
.ev-red    { color:#ef4444 !important; font-weight:700; }
.ev-yellow { color:#f59e0b !important; font-weight:700; }

.badge-live { background:#0e2a1a; border:1px solid #22c55e; color:#22c55e !important;
              font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px; }
.badge-warn { background:#1a1a0a; border:1px solid #f59e0b; color:#f59e0b !important;
              font-size:11px; font-weight:700; padding:2px 10px; border-radius:20px; }

body { overscroll-behavior-y: none !important; overflow-x: hidden !important; }
#MainMenu { visibility:hidden; } footer { visibility:hidden; } header { visibility:hidden; }
</style>
""", unsafe_allow_html=True)

# =============================================================================
# CONSTANTS
# =============================================================================
PAPER_TRADE_INTERVAL = 1200        # 20 min auto paper-trade interval
MIN_EV_THRESHOLD     = 0.02
MIN_EDGE_THRESHOLD   = 3.0         # percent
KELLY_FRACTIONS      = {"Safe": 0.25, "Moderate": 0.50, "Aggressive": 0.75}
MAX_KELLY_PCT        = 0.20        # never bet more than 20 % of bankroll
CB_STAKE_MULTIPLIER  = 0.50        # circuit-breaker reduces stakes by half

RISK_KEYWORDS = {
    "injury","injured","out","rest","resting","doubtful","questionable",
    "ruled out","sidelined","withdraw","withdrawn","illness","pain",
    "knee","ankle","hamstring","wrist","shoulder","back","gtd",
    "game time decision","day-to-day","scratch",
}

PAPER_TRADES_CSV = Path("paper_trades.csv")
BANKROLL_CONFIG  = Path("bankroll_settings.json")
MODEL_CONFIG     = Path("model_settings.json")

# API-Sports direct endpoints (api-sports.io account)
_AS_NBA    = "https://v1.basketball.api-sports.io"
_AS_TENNIS = "https://v1.tennis.api-sports.io"
_AS_MLB    = "https://v1.baseball.api-sports.io"

# =============================================================================
# SQLITE TRACKING LAYER — Line Movement Velocity
# =============================================================================
def init_market_db():
    """Initializes a local database to track line movement velocity."""
    conn = sqlite3.connect("market_history.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS odds_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            match_key TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            home_odds REAL,
            away_odds REAL
        )
    ''')
    conn.commit()
    conn.close()

def log_and_get_velocity(match_name: str, home_odds: float, away_odds: float) -> str:
    """Logs current odds and returns the directional movement velocity."""
    try:
        init_market_db()
        conn = sqlite3.connect("market_history.db")
        cursor = conn.cursor()
        
        # Log the current line
        cursor.execute(
            "INSERT INTO odds_history (match_key, home_odds, away_odds) VALUES (?, ?, ?)",
            (match_name, home_odds, away_odds)
        )
        conn.commit()
        
        # Fetch previous line from the last 2 hours to calculate velocity
        cursor.execute(
            "SELECT home_odds FROM odds_history WHERE match_key = ? AND timestamp >= datetime('now', '-2 hours') ORDER BY timestamp ASC LIMIT 1",
            (match_name,)
        )
        row = cursor.fetchone()
        conn.close()
        
        if row and row[0]:
            old_home_odds = row[0]
            shift = old_home_odds - home_odds
            if shift > 0.05:
                return "🔥 Steaming"
            elif shift < -0.05:
                return "❄️ Fading"
        return "平 Stable"
    except Exception:
        return "平 Stable"


# =============================================================================
# NETWORK HELPERS
# =============================================================================
def _session() -> requests.Session:
    s = requests.Session()
    s.trust_env = False   # ignore system proxy — fixes DNS 11001 error
    s.verify    = False
    return s

def _odds_get(sport_key: str, regions: str = "us", markets: str = "h2h") -> list:
    """Fetch best odds from TheOddsAPI. Returns list of events or []."""
    if not ODDS_API_KEY:
        return []
    _sport_map = {
        "basketball_nba": "basketball_nba",
        "baseball_mlb":   "baseball_mlb",
        "tennis_atp":     "tennis",
        "tennis_wta":     "tennis",
    }
    api_sport = _sport_map.get(sport_key, sport_key)
    try:
        resp = _session().get(
            f"{ODDS_API_BASE}/odds/",
            headers={"x-api-key": ODDS_API_KEY},
            params={"sport_key": api_sport, "markets": markets, "regions": regions},
            verify=False, timeout=12,
        )
        if resp.status_code == 200:
            return resp.json().get("data", [])
        return []
    except Exception:
        return []

def _ml_to_decimal(ml: int | float) -> float | None:
    """Convert American moneyline to decimal odds."""
    if ml is None:
        return None
    ml = float(ml)
    if ml < 0:
        return round(1 + 100 / abs(ml), 3)
    return round(1 + ml / 100, 3)

def american_to_decimal(american: float) -> float:
    """Convert American moneyline odds to decimal. -110 → 1.909, +145 → 2.45."""
    if american > 0:
        return american / 100 + 1
    else:
        return 100 / abs(american) + 1

# =============================================================================
# PREMIUM ODDS API — unified fetch for all sports
# =============================================================================
@st.cache_data(ttl=900, show_spinner=False)
def fetch_premium_odds(sport_key: str) -> pd.DataFrame:
    """
    Unified fetch from TheOddsAPI.
    Internal sport_key examples: 'basketball_nba', 'baseball_mlb', 'tennis_atp', 'tennis_wta'
    Returns DataFrame with: Match, Home Team, Away Team, Home Odds, Away Odds,
                            Books, Time/Score, Status, _sport, _date
    Response shape: { "success": true, "data": [ { "event_id", "sport", "league",
                      "home_team", "away_team", "start_time",
                      "books": [ { "book", "market", "outcomes": [{"name","price"}] } ] } ] }
    """
    if not ODDS_API_KEY:
        st.error("❌ ODDS_API_KEY not set.")
        return pd.DataFrame()

    _sport_map = {
        "basketball_nba": "basketball_nba",
        "baseball_mlb":   "baseball_mlb",
        "tennis_atp":     "tennis",
        "tennis_wta":     "tennis",
    }
    api_sport = _sport_map.get(sport_key, sport_key)

    sport_label = {
        "basketball_nba": "NBA",
        "baseball_mlb":   "MLB",
        "tennis_atp":     "Tennis",
        "tennis_wta":     "Tennis",
    }.get(sport_key, sport_key.upper())

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
        st.error(f"❌ Status: {resp.status_code} | URL: {resp.url} | Error: {resp.text[:300]}")
        return pd.DataFrame()

    payload = resp.json()
    events  = payload.get("data", [])

    # ── STAGE 1: raw API count ───────────────────────────────────────────────
    import json as _json
    print(f"[DEBUG] Got {len(events)} events for {sport_key} from API")

    if not events:
        st.warning(f"⚠️ Odds API returned 0 events for {sport_key}.")
        return pd.DataFrame()

    # ── STAGE 2: books actually present in response ──────────────────────────
    all_books = sorted({b.get("book", "") for e in events for b in e.get("books", [])})
    print(f"[DEBUG] Books in API response: {all_books}")

    # ── STAGE 3: no TIER_1_BOOKS filter in this build ────────────────────────
    # (included for parity with instrumentation spec)
    TIER_1_BOOKS = all_books   # accept every book the API returns
    print(f"[DEBUG] Tier-1 config: {TIER_1_BOOKS}")

    # ── STAGE 4: first event raw shape ───────────────────────────────────────
    print(f"[DEBUG fetch_premium_odds] first event for {sport_key}:\n"
          + _json.dumps(events[0], indent=2, default=str))

    # ── Read bypass toggle from session state (set by UI checkbox) ───────────
    bypass_filters = st.session_state.get("debug_bypass_filters", False)

    rows        = []
    skipped_imp = 0
    skipped_bk  = 0

    for ev in events:
        try:
            home  = ev.get("home_team", "")
            away  = ev.get("away_team", "")
            start = ev.get("start_time", "")
            try:
                dt       = datetime.fromisoformat(start.replace("Z", "+00:00"))
                time_str = dt.strftime("%I:%M %p ET")
                ev_date  = dt.strftime("%Y-%m-%d")
            except Exception:
                time_str = "TBD"
                ev_date  = ""

            best_h, best_a, book_count = 0.0, 0.0, 0
            for bk in ev.get("books", []):
                if bk.get("market") != "h2h":
                    continue
                for outcome in bk.get("outcomes", []):
                    american = float(outcome.get("price", 0))
                    price    = american_to_decimal(american)
                    name  = outcome.get("name", "")
                    if name == home and price > best_h:
                        best_h = price
                    elif name == away and price > best_a:
                        best_a = price
                book_count += 1

            if book_count == 0:
                skipped_bk += 1

            # ── Implied-sum filter (bypassable) ──────────────────────────────
            if not bypass_filters:
                if best_h <= 1 or best_a <= 1:
                    skipped_imp += 1
                    continue
                imp_sum = (1 / best_h) + (1 / best_a)
                if not (0.90 <= imp_sum <= 1.25):
                    skipped_imp += 1
                    continue

            rows.append({
                "Match":      f"{home} vs {away}",
                "Home Team":  home,
                "Away Team":  away,
                "Home Odds":  round(best_h, 3) if best_h else 0.0,
                "Away Odds":  round(best_a, 3) if best_a else 0.0,
                "Books":      book_count,
                "Time/Score": time_str,
                "Status":     "Scheduled",
                "Risk Meter": 30,
                "_sport":     sport_label,
                "_date":      ev_date,
                "Line Velocity": log_and_get_velocity(f"{home} vs {away}", best_h, best_a),
            })
        except Exception as _exc:
            print(f"[DEBUG] parse error on event: {_exc} — {ev}")
            continue

    # ── STAGE 5: post-filter counts ──────────────────────────────────────────
    print(f"[DEBUG] After implied-sum filter : {len(rows)} rows "
          f"(skipped {skipped_imp} bad-sum, {skipped_bk} no-book-data)")
    print(f"[DEBUG] bypass_filters={bypass_filters}")

    if not rows:
        return pd.DataFrame()

    df_out = pd.DataFrame(rows).sort_values("_date").reset_index(drop=True)
    # Store first raw event in session state so UI can display it
    st.session_state[f"debug_raw_event_{sport_key}"] = events[0]
    return df_out

# =============================================================================
# EV+ MODEL
# =============================================================================
def calculate_real_ev(df: pd.DataFrame, model_cfg: dict, sport: str = "NBA") -> pd.DataFrame:
    """
    Compute AI probability, edge %, EV+ for each row.

    Model:
      1. Remove bookmaker vig → fair probabilities
      2. Apply home advantage (sport-specific)
      3. Apply injury penalty (from Risk Meter)
      4. Blend with user confidence scalar
      5. Compute EV+ = model_prob × (odds−1) − (1−model_prob)
      6. Edge % = (model_prob − implied_prob) × 100
    """
    if df is None or df.empty:
        return df
    df = df.copy()

    confidence  = float(model_cfg.get("model_confidence", 1.0))
    injury_pen  = float(model_cfg.get("injury_penalty_pct", 5.0)) / 100
    form_factor = float(model_cfg.get("form_factor", 0.5))

    # Home advantage priors (empirical win rates when evenly matched)
    home_boost = {"NBA": 0.025, "MLB": 0.040, "Tennis": 0.010}.get(sport, 0.020)

    ai_probs, edges, evs, raws, rainbets = [], [], [], [], []

    h_col = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"
    a_col = "Away Odds" if "Away Odds" in df.columns else "P2 Odds"

    for _, row in df.iterrows():
        h_odds = pd.to_numeric(row.get(h_col), errors="coerce")
        a_odds = pd.to_numeric(row.get(a_col), errors="coerce")

        if pd.isna(h_odds) or pd.isna(a_odds) or h_odds <= 1.01 or a_odds <= 1.01:
            ai_probs.append(None); edges.append(None)
            evs.append(None);      raws.append(None)
            rainbets.append(None)
            continue

        imp_h   = 1.0 / h_odds
        imp_a   = 1.0 / a_odds
        overrnd = imp_h + imp_a
        fair_h  = imp_h / overrnd  # vig-free home probability

        # Home advantage (scaled by form_factor slider)
        model_h = fair_h + home_boost * form_factor

        # Injury / risk penalty
        risk = int(row.get("Risk Meter", 30))
        if risk >= 65:
            model_h -= injury_pen
        elif risk >= 35:
            model_h -= injury_pen * 0.5

        # Confidence blend: interpolate between fair and model
        model_h = fair_h + (model_h - fair_h) * confidence
        model_h = max(0.02, min(0.98, model_h))

        ev_val   = round(model_h * (h_odds - 1) - (1.0 - model_h), 4)
        edge_val = round((model_h - imp_h) * 100, 2)

        ai_probs.append(round(model_h * 100, 1))
        edges.append(edge_val)
        evs.append(ev_val)
        raws.append(model_h)
        rainbets.append(h_odds)   # decimal odds = Rainbet multiplier

    df["AI Prob %"]    = ai_probs
    df["Edge %"]       = edges
    df["EV+"]          = evs
    df["_ai_prob_raw"] = raws
    df["Rainbet Odds"] = rainbets
    return df


# =============================================================================
# KELLY STAKES — With Simultaneous Bet Covariance Shield
# =============================================================================
def calculate_stakes(df: pd.DataFrame, bankroll: float, risk_level: str) -> pd.DataFrame:
    """
    Advanced Fractional Kelly with automatic Multi-Game Overbet Shield.
    Balances risk when multiple games occur in the same time block.
    """
    if df is None or df.empty:
        return df
    df = df.copy()
    h_col  = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"
    
    # Count active simultaneous trades (qualifying bets with EV+ > threshold)
    ev_vals = pd.to_numeric(df.get("EV+"), errors="coerce").fillna(0)
    active_simultaneous_trades = max(1, int((ev_vals > MIN_EV_THRESHOLD).sum()))
    
    stakes = []
    for _, row in df.iterrows():
        h_odds = pd.to_numeric(row.get(h_col), errors="coerce")
        raw    = row.get("_ai_prob_raw")
        
        if pd.isna(h_odds) or raw is None:
            stakes.append(None)
            continue
            
        prob = float(raw)
        b    = h_odds - 1.0
        edge = prob * b - (1.0 - prob)
        
        if edge <= 0:
            stakes.append(0.0)
        else:
            # Get Kelly fraction from risk level
            frac = KELLY_FRACTIONS.get(risk_level, 0.5)
            
            # Raw Kelly calculation
            raw_kelly = edge / b
            
            # Apply fractional Kelly
            fractional_kelly = raw_kelly * frac
            
            # COVARIANCE SHIELD: Scale down risk if multiple games run concurrently
            if active_simultaneous_trades > 1:
                # Diminishing scaling factor using square root of simultaneous exposure
                fractional_kelly = fractional_kelly / (active_simultaneous_trades ** 0.5)
            
            # Hard cap at 5% max bankroll allocation per single trade (circuit breaker)
            final_pct = min(fractional_kelly, 0.05)
            
            # Apply circuit breaker multiplier if active
            final_stake = final_pct * bankroll * CB_STAKE_MULTIPLIER
            stakes.append(round(max(final_stake, 0.0), 2))
    
    df["Stake (C$)"] = stakes
    df["_simultaneous_trades"] = active_simultaneous_trades  # Track for display
    return df


# =============================================================================
# ADVANCE PREDICTION TABLE
# Runs for today + next N days; shows predictions even when odds not yet posted
# =============================================================================
def build_advance_predictions(days_ahead: int, sport: str,
                               model_cfg: dict, bankroll: float,
                               risk_level: str) -> pd.DataFrame:
    """
    Fetch ALL upcoming games in one call (Odds API returns everything at once).
    Filter to today + days_ahead window. Deduplicates by match+date.
    Tennis uses ESPN per-day (no Odds API support).
    """
    today     = datetime.now().date()
    cutoff    = today + timedelta(days=days_ahead)

    if sport == "Tennis":
        atp = fetch_premium_odds("tennis_atp")
        wta = fetch_premium_odds("tennis_wta")
        combined = pd.concat([atp, wta], ignore_index=True) if not atp.empty or not wta.empty else pd.DataFrame()
        if combined.empty:
            return pd.DataFrame()
        # filter to today → cutoff window
        combined = combined[combined["_date"].between(str(today), str(cutoff))].reset_index(drop=True)
        combined["_fetch_date"] = combined["_date"]
    else:
        sport_key = "basketball_nba" if sport == "NBA" else "baseball_mlb"
        combined  = fetch_premium_odds(sport_key)
        if combined.empty:
            return pd.DataFrame()
        # filter to today → cutoff window
        combined = combined[combined["_date"].between(str(today), str(cutoff))].reset_index(drop=True)
        if combined.empty:
            return pd.DataFrame()
        combined["_fetch_date"] = combined["_date"]

    combined = calculate_real_ev(combined, model_cfg, sport)
    combined = calculate_stakes(combined, bankroll, risk_level)
    return combined


# =============================================================================
# BEST BET FINDER
# =============================================================================
def find_best_bet(*dfs) -> pd.Series | None:
    frames = [df for df in dfs if df is not None and not df.empty]
    if not frames:
        return None
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["EV+","Edge %"])
    qual = all_df[
        (all_df["EV+"]    > MIN_EV_THRESHOLD) &
        (all_df["Edge %"] >= MIN_EDGE_THRESHOLD)
    ]
    if qual.empty:
        return None
    return all_df.loc[qual["EV+"].idxmax()]


def find_top_bets(*dfs, n: int = 3) -> list:
    """Return top N qualifying bets sorted by EV+."""
    frames = [df for df in dfs if df is not None and not df.empty]
    if not frames:
        return []
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["EV+","Edge %"])
    qual = all_df[
        (all_df["EV+"]    > MIN_EV_THRESHOLD) &
        (all_df["Edge %"] >= MIN_EDGE_THRESHOLD)
    ]
    if qual.empty:
        return []
    qual_sorted = qual.sort_values("EV+", ascending=False)
    return [qual_sorted.iloc[i] for i in range(min(n, len(qual_sorted)))]


def find_underdog_bets(*dfs, min_odds: float = 2.5, max_picks: int = 2) -> list:
    """Find high-odds plays with positive EV — max 2 per day, half stake."""
    frames = [df for df in dfs if df is not None and not df.empty]
    if not frames:
        return []
    all_df = pd.concat(frames, ignore_index=True).dropna(subset=["EV+","Edge %"])
    h_col = "Home Odds" if "Home Odds" in all_df.columns else "P1 Odds"
    a_col = "Away Odds" if "Away Odds" in all_df.columns else "P2 Odds"
    home_odds = pd.to_numeric(all_df.get(h_col, pd.Series(dtype=float)), errors="coerce").fillna(0)
    away_odds = pd.to_numeric(all_df.get(a_col, pd.Series(dtype=float)), errors="coerce").fillna(0)
    best_odds = away_odds.where(away_odds >= home_odds, home_odds)
    mask = (best_odds >= min_odds) & (all_df["EV+"] > 0)
    dogs = all_df[mask].copy()
    if dogs.empty:
        return []
    dogs["_dog_odds"] = best_odds[mask].values
    dogs = dogs.sort_values("_dog_odds", ascending=False)
    return [dogs.iloc[i] for i in range(min(max_picks, len(dogs)))]


# =============================================================================
# PAPER TRADING
# =============================================================================
def load_paper_trades() -> list:
    if not PAPER_TRADES_CSV.exists():
        return []
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
        print(f"[save_paper_trades] ERROR: {e}")  # log to console, not Streamlit

def execute_paper_trade(*dfs) -> tuple[bool, str]:
    """Logs top 3 qualifying bets. Returns (success, message)."""
    top3 = find_top_bets(*dfs, n=3)
    if not top3:
        return False, "No qualifying bets found (EV+ > 0.02 + Edge ≥ 3% required). Odds may not be posted yet."
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
    trades = load_paper_trades()
    count  = 0
    for t in trades:
        if t.get("status") == "PENDING":
            t["result"] = "WIN" if random.random() < float(t.get("ai_prob", 0.5)) else "LOSS"
            t["status"] = "SETTLED"
            count += 1
    save_paper_trades(trades)
    return count

def calculate_success_rate() -> dict:
    trades = load_paper_trades()
    total = wins = 0
    for t in trades:
        r = str(t.get("result", "")).upper()
        if r in ("WIN","LOSS"):
            total += 1
            if r == "WIN":
                wins += 1
    return {"total": total, "wins": wins, "losses": total - wins,
            "success_rate": round(wins / total * 100, 1) if total else 0.0}


# =============================================================================
# BACKTEST
# =============================================================================
def run_backtest(days: int = 30) -> dict:
    trades  = load_paper_trades()
    settled = [t for t in trades if t.get("status") == "SETTLED"]
    if not settled:
        return {"error": "No settled trades yet — execute and settle some trades first."}
    try:
        cutoff  = datetime.now() - timedelta(days=days)
        settled = [t for t in settled
                   if datetime.fromisoformat(str(t["timestamp"])) >= cutoff]
    except Exception:
        pass
    if not settled:
        return {"error": f"No settled trades in the last {days} days."}

    total  = len(settled)
    wins   = sum(1 for t in settled if str(t.get("result","")).upper() == "WIN")
    staked = sum(float(t.get("stake", 0)) for t in settled)
    evs    = sum(float(t.get("ev_plus", 0)) for t in settled)
    win_s  = [float(t.get("stake",0)) for t in settled if str(t.get("result","")).upper()=="WIN"]
    los_s  = [float(t.get("stake",0)) for t in settled if str(t.get("result","")).upper()=="LOSS"]
    avg_w  = round(sum(win_s)/len(win_s), 2) if win_s else 0.0
    avg_l  = round(sum(los_s)/len(los_s), 2) if los_s else 0.0
    return {
        "total_trades":  total,
        "wins":          wins,
        "losses":        total - wins,
        "win_rate":      round(wins / total * 100, 2),
        "roi":           round(evs / staked * 100, 2) if staked else 0.0,
        "avg_win":       avg_w,
        "avg_loss":      avg_l,
        "profit_factor": round(avg_w / avg_l, 2) if avg_l else 0.0,
        "total_stake":   round(staked, 2),
        "total_ev":      round(evs, 4),
    }


# =============================================================================
# CONFIG HELPERS
# =============================================================================
def load_bankroll_config() -> dict:
    if BANKROLL_CONFIG.exists():
        try:
            return json.loads(BANKROLL_CONFIG.read_text())
        except Exception:
            pass
    return {"starting_bankroll": 1500.0, "min_stake": 10.0,
            "max_stake": 500.0, "max_drawdown_pct": 25.0, "kelly_fraction": "Moderate"}

def save_bankroll_config(cfg: dict):
    BANKROLL_CONFIG.write_text(json.dumps(cfg, indent=2))

def load_model_config() -> dict:
    if MODEL_CONFIG.exists():
        try:
            return json.loads(MODEL_CONFIG.read_text())
        except Exception:
            pass
    return {"model_confidence": 1.0, "edge_threshold_pct": 3.0,
            "injury_penalty_pct": 5.0, "form_factor": 0.5, "odds_weight": 0.5}

def save_model_config(cfg: dict):
    MODEL_CONFIG.write_text(json.dumps(cfg, indent=2))


# =============================================================================
# RSS ALERTS
# =============================================================================
def fetch_rss_headlines(urls: list) -> list:
    out = []
    for url in urls:
        try:
            feed = feedparser.parse(url)
            out.extend(e.title for e in feed.entries[:8])
        except Exception:
            continue
    return out[:15]

def detect_injury_alert(headline: str) -> bool:
    return any(kw in (headline or "").lower() for kw in RISK_KEYWORDS)


# =============================================================================
# DISPLAY HELPERS
# =============================================================================
def _badge(label: str) -> str:
    low = label.lower()
    if any(x in low for x in ["live","espn","api-sports"]):
        return f'<span class="badge-live">&#9679; {label}</span>'
    if "no " in low or "tbd" in low or "scheduled" in low:
        return f'<span class="badge-warn">&#8212; {label}</span>'
    return f'<span class="badge-err">&#9888; {label}</span>'

def _ev_color(v) -> str:
    try:
        v = float(v)
    except Exception:
        return ""
    if v > 0.05:  return "ev-green"
    if v > 0:     return "ev-yellow"
    return "ev-red"

def _safe_num(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    df = df.copy()
    for c in cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def _fmt_cell(col: str, val) -> str:
    """Format a cell value for HTML table display."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return '<span style="color:#475569;">—</span>'
    cl = col.lower()
    
    # Handle Line Velocity column
    if "velocity" in cl:
        s = str(val)
        if "🔥" in s or "steaming" in s.lower():
            return f'<span style="color:#ef4444;font-weight:700;">{s}</span>'
        elif "❄️" in s or "fading" in s.lower():
            return f'<span style="color:#60a5fa;font-weight:600;">{s}</span>'
        else:
            return f'<span style="color:#94a3b8;">{s}</span>'
    
    try:
        v = float(val)
        if "ev+" in cl or cl == "ev":
            colour = "#22c55e" if v > 0.05 else "#f59e0b" if v > 0 else "#ef4444"
            return f'<span style="color:{colour};font-weight:700;">{v:+.4f}</span>'
        if "edge" in cl:
            colour = "#22c55e" if v >= 3 else "#f59e0b" if v > 0 else "#ef4444"
            return f'<span style="color:{colour};">{v:+.2f}%</span>'
        if "odds" in cl:
            return f'<span style="color:#00D9FF;font-weight:600;">{v:.2f}</span>'
        if "stake" in cl:
            return f'<span style="color:#a78bfa;font-weight:600;">C${v:.2f}</span>'
        if "prob" in cl:
            return f'{v:.1f}%'
        if "books" in cl:
            return f'<span style="color:#64748b;">{int(v)}</span>'
        return f'{v:.3f}'
    except (TypeError, ValueError):
        s = str(val)
        if col in ("Match", "match"):
            return f'<span style="color:#f1f5f9;font-weight:700;">{s}</span>'
        if col in ("_date", "Date"):
            return f'<span style="color:#00D9FF;font-size:12px;">{s}</span>'
        if col in ("Status","status"):
            colour = "#22c55e" if "live" in s.lower() or "progress" in s.lower() else "#94a3b8"
            return f'<span style="color:{colour};font-size:12px;">{s}</span>'
        return f'<span style="color:#e2e8f0;">{s}</span>'

def _render_df(df: pd.DataFrame, cols: list):
    available = [c for c in cols if c in df.columns]
    if not available:
        st.warning("No displayable columns found in data.")
        return
    sub = df[available].copy()

    # Build HTML table
    HEADER_COLOUR = "#94a3b8"
    HEADER_BG     = "#0f172a"
    ROW_BG        = "#1e293b"
    ROW_ALT_BG    = "#162032"
    BORDER        = "#2d3748"

    display_names = {
        "_date": "Date", "AI Prob %": "AI Prob", "Stake (C$)": "Stake",
        "Time/Score": "Time / Score", "Home Pitcher": "Home SP",
        "Away Pitcher": "Away SP", "Home Odds": "Home @",
        "Away Odds": "Away @", "P1 Odds": "P1 @", "P2 Odds": "P2 @",
        "Line Velocity": "Line Move",
    }

    headers = "".join(
        f'<th style="padding:10px 14px;text-align:left;color:{HEADER_COLOUR};'
        f'font-size:11px;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.5px;border-bottom:2px solid {BORDER};white-space:nowrap;">'
        f'{display_names.get(c, c)}</th>'
        for c in available
    )

    rows_html = ""
    for i, (_, row) in enumerate(sub.iterrows()):
        bg = ROW_BG if i % 2 == 0 else ROW_ALT_BG
        cells = "".join(
            f'<td style="padding:9px 14px;border-bottom:1px solid {BORDER};'
            f'white-space:nowrap;">{_fmt_cell(c, row.get(c))}</td>'
            for c in available
        )
        rows_html += f'<tr style="background:{bg};">{cells}</tr>'

    html = f"""
    <div style="overflow-x:auto;border-radius:8px;border:1px solid {BORDER};margin-bottom:12px;">
    <table style="width:100%;border-collapse:collapse;font-size:13px;font-family:sans-serif;">
        <thead><tr style="background:{HEADER_BG};">{headers}</tr></thead>
        <tbody>{rows_html}</tbody>
    </table>
    </div>
    """
    st.markdown(html, unsafe_allow_html=True)

def _render_schedule(events: list, sport_filter: str = "All"):
    if not events:
        st.info("No upcoming events found for the next 7 days.")
        return
    df = pd.DataFrame(events)
    if sport_filter != "All":
        df = df[df["Sport"].str.contains(sport_filter, case=False, na=False)]
    if df.empty:
        st.info(f"No upcoming {sport_filter} events found.")
        return
    for date, group in df.groupby("Date"):
        try:
            day_label = datetime.strptime(date, "%Y-%m-%d").strftime("%A, %B %d")
        except Exception:
            day_label = date
        st.markdown(f"### 📅 {day_label}")
        for _, row in group.iterrows():
            st.markdown(
                f"<div class='event-card'>"
                f"<div class='event-date'>{row.get('Sport','')} &nbsp;·&nbsp; {row.get('Time','TBD')}</div>"
                f"<div class='event-match'>{row.get('Match','')}</div>"
                f"</div>", unsafe_allow_html=True)

def _render_prediction_table(df: pd.DataFrame, sport: str):
    """Render advance prediction cards sorted by EV+."""
    if df is None or df.empty:
        st.info(f"No {sport} predictions available. Check your API-Sports key.")
        return

    h_col = "Home Odds" if "Home Odds" in df.columns else "P1 Odds"
    a_col = "Away Odds" if "Away Odds" in df.columns else "P2 Odds"

    df_sorted = df.copy()
    df_sorted["_ev_sort"] = pd.to_numeric(df_sorted.get("EV+"), errors="coerce").fillna(-99)
    df_sorted = df_sorted.sort_values("_ev_sort", ascending=False).drop(columns=["_ev_sort"])

    for _, row in df_sorted.iterrows():
        ev  = row.get("EV+")
        edge = row.get("Edge %")
        stake = row.get("Stake (C$)")
        h_odds = row.get(h_col)
        a_odds = row.get(a_col)
        has_odds = pd.notna(h_odds) and pd.notna(a_odds)
        ev_cls = _ev_color(ev) if has_odds else "ev-yellow"
        date_str = row.get("_date", row.get("_fetch_date", ""))

        odds_str = (f"Odds: <b>{h_odds:.2f}</b> / <b>{a_odds:.2f}</b>" if has_odds
                    else "⏳ Odds post ~2h before game")
        ev_str   = (f"EV+ <span class='{ev_cls}'>{ev:+.4f}</span> &nbsp;|&nbsp; Edge {edge:+.2f}%"
                    if has_odds and ev is not None
                    else "<span class='ev-yellow'>EV pending odds</span>")
        stake_str = (f"&nbsp;|&nbsp; Stake: <b>C${stake:.2f}</b>"
                     if has_odds and stake and stake > 0 else "")

        pitcher_str = ""
        if sport == "MLB":
            ph = row.get("Home Pitcher","TBD")
            pa = row.get("Away Pitcher","TBD")
            pitcher_str = f"<div style='font-size:11px;color:#94a3b8;margin-top:4px;'>SP: {ph} vs {pa}</div>"

        tour_str = ""
        if sport == "Tennis":
            tour_str = f"<div style='font-size:11px;color:#94a3b8;'>{row.get('Tournament','')} — {row.get('Category','')}</div>"

        # Build bet recommendation string
        bet_team = ""
        if has_odds:
            home_t = row.get("Home Team", row.get("Player 1",
                     row.get("Match","? vs ?").split(" vs ")[0].strip()))
            away_t = row.get("Away Team", row.get("Player 2",
                     row.get("Match","? vs ?").split(" vs ")[-1].strip()))
            h_f = float(h_odds)
            a_f = float(a_odds)
            # Sanity check: implied prob sum must be between 0.95 and 1.25
            # Real bookmaker margins sit in that range. Anything outside = corrupted line
            # (e.g. grabbing a 3-way draw market or alt line by accident)
            imp_sum = (1 / h_f) + (1 / a_f) if h_f > 1 and a_f > 1 else 0
            if imp_sum < 0.95 or imp_sum > 1.25:
                odds_str = f"⚠️ Bad line ({h_f:.2f}/{a_f:.2f}, margin {(imp_sum-1)*100:+.1f}%) — 3-way or alt market"
                ev_str   = "<span class='ev-red'>Corrupted odds — do not bet</span>"
                stake_str = ""
            else:
                rec_team = home_t if h_f <= a_f else away_t
                rec_odds = h_f if h_f <= a_f else a_f
                bet_tag  = f"<span style='color:#00D9FF;font-weight:700;'>✅ BET ON: {rec_team} @ {rec_odds:.2f}x</span>" if (ev is not None and float(ev) > MIN_EV_THRESHOLD) else f"<span style='color:#64748b;'>⛔ No edge — skip</span>"
                odds_str = f"{bet_tag} &nbsp;|&nbsp; Lines: <b>{h_f:.2f}</b> / <b>{a_f:.2f}</b>"

        st.markdown(f"<div class='pred-card'><div class='pred-match'>{row.get('Match','')} <span style='font-size:11px;color:#64748b;font-weight:400;margin-left:8px;'>{date_str} &nbsp;|&nbsp; {row.get('Time/Score', row.get('Time','TBD'))}</span></div>{tour_str}{pitcher_str}<div style='font-size:13px;margin-top:6px;'>{odds_str}</div><div style='font-size:13px;margin-top:4px;'>{ev_str}{stake_str}</div></div>", unsafe_allow_html=True)


# =============================================================================
# KEY STATUS BANNER — tests actual connectivity, not just key presence
# =============================================================================
def _key_status_banner():
    if not ODDS_API_KEY:
        st.error("❌ ODDS_API_KEY not set — add it to the top of main.py")
        return
    try:
        resp = _session().get(
            f"{ODDS_API_BASE}/me/",
            headers={"x-api-key": ODDS_API_KEY},
            verify=False, timeout=8,
        )
        if resp.status_code == 200:
            info      = resp.json()
            remaining = info.get("requests_remaining", info.get("x-requests-remaining", "?"))
            used      = info.get("requests_used",      info.get("x-requests-used",      "?"))
            st.success(f"✅ TheOddsAPI connected — {used} used | {remaining} remaining")
        elif resp.status_code == 401:
            st.error("❌ Odds API key invalid or expired")
        else:
            st.error(f"❌ Odds API HTTP {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        st.error(f"❌ Odds API connection error: {e}")


# =============================================================================
# MAIN
# =============================================================================
def main():
    # ── Session state defaults ────────────────────────────────────────────────
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
        days_ahead = st.slider("Days ahead to predict", 0, 7, 2,
                               help="Show EV predictions for today + N future days")
        st.divider()

        st.subheader("🎯 Manual Rainbet Override")
        rainbet_multiplier = st.number_input(
            "Current Rainbet Multiplier (X)",
            min_value=1.01, max_value=50.0, value=1.90, step=0.05,
            help="Enter the live decimal odds from Rainbet. Used as Bookmaker Odds in EV+ calculation.",
        )
        st.caption("If Rainbet shows 1.85 on a game, enter 1.85 here.")

    # ── Header ────────────────────────────────────────────────────────────────
    col_t, col_l = st.columns([4,1])
    with col_t:
        st.markdown("<h1 style='margin:0'>📈 Sports EV+ Dashboard</h1>", unsafe_allow_html=True)
        st.caption("NBA · MLB · Tennis — API-Sports + Odds API | All amounts in CAD")
    with col_l:
        if st.button("🔄 Refresh Data", use_container_width=True):
            # Clear all data caches so next render re-fetches everything
            for key in ["schedule_cache","schedule_fetched","pred_cache","pred_fetched",
                        "data_nba","data_mlb","data_tennis","data_fetched"]:
                if key in st.session_state:
                    del st.session_state[key]
            st.rerun()

    _key_status_banner()

    # ── Fetch today's data (cached — only re-runs on Refresh button) ────────────
    today_str = datetime.now().strftime("%Y-%m-%d")

    if "data_fetched" not in st.session_state or st.session_state.get("data_fetched") != today_str:
        prog = st.progress(0, text="📡 Connecting to Odds API…")
        try:
            prog.progress(20, text="🏀 Fetching NBA odds from Premium API…")
            df_nba_raw = fetch_premium_odds("basketball_nba")
            st.session_state["data_nba"] = calculate_stakes(
                calculate_real_ev(df_nba_raw, model_cfg, "NBA"), bankroll, risk_level)

            prog.progress(50, text="⚾ Fetching MLB odds from Premium API…")
            df_mlb_raw = fetch_premium_odds("baseball_mlb")
            st.session_state["data_mlb"] = calculate_stakes(
                calculate_real_ev(df_mlb_raw, model_cfg, "MLB"), bankroll, risk_level)

            prog.progress(75, text="🎾 Fetching Tennis odds from Premium API…")
            df_atp_raw = fetch_premium_odds("tennis_atp")
            df_wta_raw = fetch_premium_odds("tennis_wta")
            df_tennis_raw = pd.concat([df_atp_raw, df_wta_raw], ignore_index=True) if not df_atp_raw.empty or not df_wta_raw.empty else pd.DataFrame()
            st.session_state["data_tennis"] = calculate_stakes(
                calculate_real_ev(df_tennis_raw, model_cfg, "Tennis"), bankroll, risk_level)

            st.session_state["data_fetched"] = today_str
            prog.progress(100, text="✅ Done!")
            prog.empty()
        except Exception as e:
            prog.empty()
            st.error(f"❌ Data fetch error: {e}")

    df_nba    = st.session_state.get("data_nba",    pd.DataFrame())
    df_mlb    = st.session_state.get("data_mlb",    pd.DataFrame())
    df_tennis = st.session_state.get("data_tennis", pd.DataFrame())

    # ── DEBUG INSTRUMENTATION ─────────────────────────────────────────────────
    bypass_filters = st.checkbox(
        "🔧 Show all games (bypass implied-sum filter)",
        value=st.session_state.get("debug_bypass_filters", False),
        key="debug_bypass_filters",
        help="Disables the 0.90–1.25 implied-sum sanity check. "
             "If games appear here but not normally, the filter is the bug.",
    )
    if bypass_filters:
        # Re-fetch with cache busted so the bypass flag takes effect immediately
        for _sk in ["data_nba","data_mlb","data_tennis","data_fetched"]:
            st.session_state.pop(_sk, None)
        fetch_premium_odds.clear()

    # Pipeline row counts in the UI
    with st.expander("🔍 Pipeline counts (click to expand)", expanded=True):
        c1, c2, c3 = st.columns(3)
        c1.metric("NBA rows after fetch",    len(df_nba))
        c2.metric("MLB rows after fetch",    len(df_mlb))
        c3.metric("Tennis rows after fetch", len(df_tennis))

        # First raw event per sport so we can verify field names on the page
        for label, sk in [("NBA","basketball_nba"), ("MLB","baseball_mlb"), ("Tennis","tennis_atp")]:
            raw = st.session_state.get(f"debug_raw_event_{sk}")
            if raw:
                st.markdown(f"**{label} — first raw event from API:**")
                st.json(raw)
    # ── END DEBUG ─────────────────────────────────────────────────────────────

    # Auto paper trade (only when data exists)
    if (not df_nba.empty or not df_mlb.empty or not df_tennis.empty):
        if (datetime.now() - st.session_state.last_paper_trade).total_seconds() >= PAPER_TRADE_INTERVAL:
            _ok, _msg = execute_paper_trade(df_nba, df_mlb, df_tennis)
            if _ok:
                settle_pending_trades()
            st.session_state.last_paper_trade = datetime.now()

    # Schedule is lazy-loaded inside the Schedule tab — NOT here
    # This prevents 21 extra API calls on every page load

    # ── TABS ──────────────────────────────────────────────────────────────────
    tabs = st.tabs(["🏆 Live Hub","🏀 NBA","⚾ MLB","🎾 Tennis",
                    "🔮 Predictions","🐶 Underdogs","📅 Schedule","📈 Analytics","🔧 Settings"])

    # ── TAB 0: Live Hub ───────────────────────────────────────────────────────
    with tabs[0]:
        # Capital Protection Shield Status
        all_qualifying = []
        for df in [df_nba, df_mlb, df_tennis]:
            if df is not None and not df.empty:
                ev_col = pd.to_numeric(df.get("EV+"), errors="coerce").fillna(0)
                all_qualifying.extend(df[ev_col > MIN_EV_THRESHOLD].to_dict('records'))
        
        total_simultaneous = len(all_qualifying)
        if total_simultaneous > 1:
            st.markdown(
                f"<div style='background:linear-gradient(135deg,#1a1f3a,#0f172a);border:2px solid #f59e0b;"
                f"border-radius:10px;padding:16px 20px;margin-bottom:16px;'>"
                f"<div style='font-size:11px;color:#f59e0b;text-transform:uppercase;letter-spacing:1px;font-weight:700;margin-bottom:6px;'>"
                f"🛡️ CAPITAL PROTECTION SHIELD ACTIVE</div>"
                f"<div style='font-size:20px;font-weight:700;color:#fbbf24;'>{total_simultaneous} Simultaneous Qualifying Bets Detected</div>"
                f"<div style='font-size:13px;color:#e2e8f0;margin-top:8px;'>"
                f"Stakes auto-scaled by <b>÷√{total_simultaneous}</b> = <b>{1/(total_simultaneous**0.5):.3f}x</b> to prevent overexposure during high-volume slates. "
                f"Circuit breaker capped at 5% max single allocation.</div>"
                f"</div>", unsafe_allow_html=True
            )
        
        best = find_best_bet(df_nba, df_mlb, df_tennis)
        st.markdown("<div class='metric-box'><div class='metric-title'>💰 Best Bet Right Now</div>",
                    unsafe_allow_html=True)
        if best is not None:
            h_col   = "Home Odds" if pd.notna(best.get("Home Odds")) else "P1 Odds"
            a_col   = "Away Odds" if "Away Odds" in best.index else "P2 Odds"
            h_odds  = float(best.get(h_col, 0) or 0)
            a_odds  = float(best.get(a_col, 0) or 0)
            home_t  = best.get("Home Team", best.get("Player 1",
                      best.get("Match","? vs ?").split(" vs ")[0].strip()))
            away_t  = best.get("Away Team", best.get("Player 2",
                      best.get("Match","? vs ?").split(" vs ")[-1].strip()))
            # Pick the favourite (lower odds = more likely winner)
            bet_team = home_t if h_odds <= a_odds else away_t
            bet_odds = h_odds if h_odds <= a_odds else a_odds
            stake   = float(best.get("Stake (C$)", 0) or 0)
            payout  = round(stake * bet_odds, 2)
            profit  = round(payout - stake, 2)
            ev      = float(best.get("EV+", 0) or 0)
            edge    = float(best.get("Edge %", 0) or 0)
            sport_lbl = best.get("_sport","")
            st.markdown(
                f"<div style='font-size:12px;color:#94a3b8;text-transform:uppercase;letter-spacing:1px;margin-bottom:4px;'>BET ON</div>"
                f"<div class='metric-value' style='color:#00D9FF;font-size:32px;font-weight:800;'>{bet_team}</div>"
                f"<div style='font-size:13px;color:#e2e8f0;margin:4px 0 10px;'>{best.get('Match','N/A')} &nbsp;·&nbsp; {sport_lbl}</div>"
                f"<p style='color:#e2e8f0;'><b>Consensus Odds:</b> {bet_odds:.2f}x &nbsp;|&nbsp;"
                f"<b>Rainbet X:</b> <span style='color:#f59e0b;font-weight:700;'>{rainbet_multiplier:.2f}x</span> &nbsp;|&nbsp;"
                f"<b>EV+:</b> <span style='color:#22c55e;font-weight:700;'>{ev:+.4f}</span> &nbsp;|&nbsp;"
                f"<b>Edge:</b> {edge:.2f}% &nbsp;|&nbsp;"
                f"<b>AI Prob:</b> {best.get('AI Prob %',0):.1f}%</p>"
                f"<p style='color:#e2e8f0;'><b>Stake:</b> C${stake:.2f} &nbsp;|&nbsp;"
                f"<b>Rainbet Payout:</b> C${round(stake * rainbet_multiplier, 2):.2f} &nbsp;|&nbsp;"
                f"<b>Profit if Win:</b> <span style='color:#22c55e;font-weight:700;'>C${round(stake * rainbet_multiplier - stake, 2):.2f}</span></p>",
                unsafe_allow_html=True)
        else:
            st.markdown(
                "<div class='metric-value' style='font-size:18px;color:#94a3b8;'>No qualifying bet yet — "
                "odds post ~2h before game time. Check 🔮 Predictions tab.</div>",
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
                _render_df(df_tennis, ["Match","Tournament","Time","Status","Score","Line Velocity"])
            else:
                st.info("No tennis matches today via ESPN.")

        st.divider()
        st.subheader("📰 Injury & News Alerts")
        nba_hl    = fetch_rss_headlines(["https://www.espn.com/espn/rss/nba/news"])
        mlb_hl    = fetch_rss_headlines(["https://www.espn.com/espn/rss/mlb/news"])
        tennis_hl = fetch_rss_headlines(["https://www.espn.com/espn/rss/tennis/news"])
        all_hl    = nba_hl + mlb_hl + tennis_hl
        alerts    = [h for h in all_hl if detect_injury_alert(h)]
        for a in alerts[:6]:
            st.warning(f"⚠️ {a}")
        for h in [h for h in nba_hl if not detect_injury_alert(h)][:3]:
            st.markdown(f"🏀 {h}")
        for h in [h for h in mlb_hl if not detect_injury_alert(h)][:3]:
            st.markdown(f"⚾ {h}")
        if not alerts:
            st.success("✅ No injury alerts detected.")

    # ── TAB 1: NBA ────────────────────────────────────────────────────────────
    with tabs[1]:
        st.header("🏀 NBA — Upcoming Games")
        if not df_nba.empty:
            _render_df(df_nba, ["Match","Time/Score","_date","Home Odds","Away Odds",
                                 "AI Prob %","Edge %","EV+","Stake (C$)","Books","Line Velocity"])
            c1,c2,c3,c4 = st.columns(4)
            ev_v = pd.to_numeric(df_nba.get("EV+"), errors="coerce").dropna()
            c1.metric("Games", len(df_nba))
            c2.metric("Avg EV+", f"{ev_v.mean():.4f}" if not ev_v.empty else "—")
            c3.metric("Qualifying Bets", int((ev_v > MIN_EV_THRESHOLD).sum()))
            stk = pd.to_numeric(df_nba.get("Stake (C$)"), errors="coerce").fillna(0)
            c4.metric("Total Stake C$", f"{stk.sum():,.2f}")
            if "_simultaneous_trades" in df_nba.columns:
                st.caption(f"🛡️ Covariance Shield Active: {df_nba['_simultaneous_trades'].iloc[0]} simultaneous trades detected — stakes auto-scaled")
        else:
            st.info("🏀 No upcoming NBA games found. The Odds API may not have lines posted yet — try Refresh.")

    # ── TAB 2: MLB ────────────────────────────────────────────────────────────
    with tabs[2]:
        st.header("⚾ MLB — Upcoming Games")
        if not df_mlb.empty:
            _render_df(df_mlb, ["Match","Time/Score","_date","Home Odds","Away Odds",
                                 "AI Prob %","Edge %","EV+","Stake (C$)","Books","Line Velocity"])
            c1,c2,c3,c4 = st.columns(4)
            ev_v = pd.to_numeric(df_mlb.get("EV+"), errors="coerce").dropna()
            c1.metric("Games", len(df_mlb))
            c2.metric("Avg EV+", f"{ev_v.mean():.4f}" if not ev_v.empty else "—")
            c3.metric("Qualifying Bets", int((ev_v > MIN_EV_THRESHOLD).sum()))
            stk = pd.to_numeric(df_mlb.get("Stake (C$)"), errors="coerce").fillna(0)
            c4.metric("Total Stake C$", f"{stk.sum():,.2f}")
            if "_simultaneous_trades" in df_mlb.columns:
                st.caption(f"🛡️ Covariance Shield Active: {df_mlb['_simultaneous_trades'].iloc[0]} simultaneous trades detected — stakes auto-scaled")
            st.caption("ℹ️ Odds from 20+ bookmakers via The Odds API.")
        else:
            st.info("⚾ No upcoming MLB games found. Press Refresh to try again.")

    # ── TAB 3: Tennis ─────────────────────────────────────────────────────────
    with tabs[3]:
        st.header("🎾 Tennis — Today's Matches")
        st.caption("Tennis ATP + WTA odds via The Odds API Premium.")
        if not df_tennis.empty:
            _render_df(df_tennis, ["Match","Time/Score","_date","Home Odds","Away Odds","EV+","Stake (C$)","Books","Line Velocity"])
            c1,c2 = st.columns(2)
            c1.metric("Matches Today", len(df_tennis))
            c2.metric("Qualifying Bets", int((pd.to_numeric(df_tennis.get("EV+"), errors="coerce") > MIN_EV_THRESHOLD).sum()))
            if "_simultaneous_trades" in df_tennis.columns:
                st.caption(f"🛡️ Covariance Shield Active: {df_tennis['_simultaneous_trades'].iloc[0]} simultaneous trades detected — stakes auto-scaled")
        else:
            st.error("🎾 No tennis matches returned from Odds API. Key may not support tennis on this plan, or no lines are posted yet.")

    # ── TAB 4: Predictions (advance) ─────────────────────────────────────────
    with tabs[4]:
        st.header("🔮 Advance Predictions")
        st.info(f"Showing predictions for today + {days_ahead} day(s) ahead. "
                "Games without odds yet show 'EV pending' — odds will fill in closer to game time.")

        pred_sport = st.selectbox("Sport", ["NBA","MLB","Tennis"], key="pred_sport_sel")

        # Cache predictions per sport for 30 min
        cache_key   = f"pred_{pred_sport}_{days_ahead}"
        fetched_key = f"pred_fetch_{pred_sport}_{days_ahead}"
        pred_age    = None
        if st.session_state.pred_fetched.get(fetched_key):
            pred_age = (datetime.now() - st.session_state.pred_fetched[fetched_key]).total_seconds()

        cached_pred = st.session_state.pred_cache.get(cache_key)
        cache_is_empty = cached_pred is None or (isinstance(cached_pred, pd.DataFrame) and cached_pred.empty)
        if cache_is_empty or pred_age is None or pred_age > 1800:
            with st.spinner(f"Fetching {pred_sport} games for next {days_ahead} days…"):
                pred_df = build_advance_predictions(days_ahead, pred_sport,
                                                    model_cfg, bankroll, risk_level)
            st.session_state.pred_cache[cache_key]   = pred_df
            st.session_state.pred_fetched[fetched_key] = datetime.now()
        else:
            pred_df = st.session_state.pred_cache[cache_key]

        col_ref, col_filter = st.columns([1,3])
        with col_ref:
            if st.button("🔄 Refresh Predictions"):
                st.session_state.pred_cache.pop(cache_key, None)
                st.rerun()
        with col_filter:
            only_qualifying = st.checkbox("Show only qualifying bets (EV+ > 0.02)", value=False)

        if only_qualifying and pred_df is not None and not pred_df.empty:
            ev_col = pd.to_numeric(pred_df.get("EV+"), errors="coerce")
            pred_df = pred_df[ev_col > MIN_EV_THRESHOLD].reset_index(drop=True)

        _render_prediction_table(pred_df, pred_sport)

    # ── TAB 5: Underdogs ─────────────────────────────────────────────────────
    with tabs[5]:
        st.header("🐶 Underdog Special Bets")
        st.info("High-odds plays with positive EV — max 2 picks per session, bet at HALF your normal stake. High risk, high reward.")
        dogs = find_underdog_bets(df_nba, df_mlb, df_tennis, min_odds=2.5, max_picks=2)
        if not dogs:
            st.warning("No underdog plays with positive EV right now. Odds need to be posted (~2h before game) for this to populate.")
        else:
            for i, dog in enumerate(dogs):
                h_col    = "Home Odds" if "Home Odds" in dog.index else "P1 Odds"
                a_col    = "Away Odds" if "Away Odds" in dog.index else "P2 Odds"
                h_odds_v = float(dog.get(h_col, 0) or 0)
                a_odds_v = float(dog.get(a_col, 0) or 0)
                home_t   = dog.get("Home Team", dog.get("Player 1",
                           dog.get("Match","? vs ?").split(" vs ")[0].strip()))
                away_t   = dog.get("Away Team", dog.get("Player 2",
                           dog.get("Match","? vs ?").split(" vs ")[-1].strip()))
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
                    unsafe_allow_html=True
                )

    # ── TAB 6: Schedule ───────────────────────────────────────────────────────
    with tabs[6]:
        st.header("📅 Upcoming Schedule — Next 7 Days")
        st.info("⚠️ Loading the schedule uses ~21 API calls (7 days × 3 sports). "
                "Click the button below when you want to load it.")
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
        st.info("Execute a paper trade when you see a qualifying EV+. "
                "Settle trades after the game to track your win rate.")

        c1,c2,c3 = st.columns(3)
        with c1:
            if st.button("▶️ Execute Paper Trade"):
                _ok, _msg = execute_paper_trade(df_nba, df_mlb, df_tennis)
                if _ok:
                    st.success(_msg)
                else:
                    st.warning(f"⚠️ {_msg}")
        with c2:
            if st.button("✅ Settle Pending Trades"):
                n = settle_pending_trades()
                if n:
                    st.success(f"✅ Settled {n} trade(s).")
                else:
                    st.info("No pending trades to settle.")
        with c3:
            with st.expander("🗑️ Clear All Trades"):
                st.warning("Permanently deletes all trade history.")
                if st.button("⚠️ Confirm Delete"):
                    PAPER_TRADES_CSV.unlink(missing_ok=True)
                    st.success("✅ Cleared.")

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
                "edge_pct":"Edge %","strategy":"Strategy",
                "result":"Result","status":"Status"})
            for col in ["Odds","EV+","Stake (C$)","AI Prob","Edge %"]:
                if col in tdf.columns:
                    tdf[col] = pd.to_numeric(tdf[col], errors="coerce")
            st.dataframe(
                tdf,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "EV+":       st.column_config.NumberColumn("EV+",       format="%+.4f"),
                    "Stake (C$)":st.column_config.NumberColumn("Stake (C$)",format="C$%.2f"),
                    "Odds":      st.column_config.NumberColumn("Odds",      format="%.2f"),
                    "AI Prob":   st.column_config.NumberColumn("AI Prob",   format="%.3f"),
                    "Edge %":    st.column_config.NumberColumn("Edge %",    format="%.2f%%"),
                    "Result":    st.column_config.TextColumn("Result"),
                    "Status":    st.column_config.TextColumn("Status"),
                },
            )
            c1,c2,c3,c4,c5 = st.columns(5)
            c1.metric("Total",   len(trades))
            c2.metric("Settled", sum(1 for t in trades if t.get("status")=="SETTLED"))
            c3.metric("Pending", sum(1 for t in trades if t.get("status")=="PENDING"))
            avg_stk = sum(float(t.get("stake",0)) for t in trades) / len(trades)
            avg_ev  = sum(float(t.get("ev_plus",0)) for t in trades) / len(trades)
            c4.metric("Avg Stake", f"C${avg_stk:,.2f}")
            c5.metric("Avg EV+",  f"{avg_ev:.4f}")
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
            st.info("Adjust how the AI calculates EV+ and edge. Changes apply immediately.")
            c1,c2 = st.columns(2)
            with c1:
                mc = st.slider("Model Confidence", 0.5, 2.0,
                               float(model_cfg["model_confidence"]), 0.05,
                               help="1.0 = neutral. >1 = amplifies home advantage signal.")
                et = st.slider("Edge Threshold %", 1, 10,
                               int(model_cfg["edge_threshold_pct"]),
                               help="Minimum edge vs bookmaker to flag a qualifying bet.")
            with c2:
                ip = st.slider("Injury Penalty %", 1, 20,
                               int(model_cfg["injury_penalty_pct"]),
                               help="Probability reduction for high-risk matches.")
                ff = st.slider("Home Advantage Factor", 0.0, 1.0,
                               float(model_cfg["form_factor"]), 0.05,
                               help="Scale applied to sport-specific home advantage prior.")
            ow = st.slider("Odds Weight", 0.0, 1.0, float(model_cfg["odds_weight"]), 0.05,
                           help="How heavily the model leans on bookmaker consensus.")
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
        "📈 Sports EV+ Dashboard &nbsp;|&nbsp; NBA · MLB · Tennis"
        " &nbsp;|&nbsp; Data: API-Sports + The Odds API &nbsp;|&nbsp; All amounts in CAD"
        "</p>", unsafe_allow_html=True)


# =============================================================================
# SCHEDULE HELPERS (used inside main but defined here to keep file readable)
# =============================================================================
def _fetch_schedule_nba(days: int = 7) -> list:
    events = []
    df = fetch_premium_odds("basketball_nba")
    if df.empty:
        return []
    odds_events = []  # not used — iterate df instead
    seen = set()
    for _, row in df.iterrows():
        key = f"{row.get('Home Team','')}{row.get('Away Team','')}{row.get('_date','')}"
        if key not in seen:
            seen.add(key)
            events.append({"Date": row.get("_date",""), "Time": row.get("Time/Score","TBD"),
                           "Match": row.get("Match",""), "Sport": "🏀 NBA"})
    return events
def _fetch_schedule_nba_DEAD(days: int = 7) -> list:
    events = []
    odds_events = []
    seen = set()
    for ev in odds_events:
        try:
            home = ev.get("home_team","")
            away = ev.get("away_team","")
            commence = ev.get("start_time","")
        except Exception:
            continue
    return events

def _fetch_schedule_mlb(days: int = 7) -> list:
    events = []
    df = fetch_premium_odds("baseball_mlb")
    if df.empty:
        return []
    seen = set()
    for _, row in df.iterrows():
        key = f"{row.get('Home Team','')}{row.get('Away Team','')}{row.get('_date','')}"
        if key not in seen:
            seen.add(key)
            events.append({"Date": row.get("_date",""), "Time": row.get("Time/Score","TBD"),
                           "Match": row.get("Match",""), "Sport": "⚾ MLB"})
    return events
def _fetch_schedule_mlb_DEAD(days: int = 7) -> list:
    events = []
    odds_events = []
    seen = set()
    for ev in odds_events:
        try:
            home = ev.get("home_team","")
            away = ev.get("away_team","")
            commence = ev.get("start_time","")
            dt = datetime.fromisoformat(commence.replace("Z","+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
            time_str = dt.strftime("%I:%M %p ET")
            key = f"{home}{away}{date_str}"
            if key not in seen:
                seen.add(key)
                events.append({"Date": date_str, "Time": time_str,
                               "Match": f"{home} vs {away}", "Sport": "⚾ MLB"})
        except Exception:
            continue
    return events

def _fetch_schedule_tennis(days: int = 7) -> list:
    events = []
    seen = set()
    for sport_key in ("tennis_atp", "tennis_wta"):
        df = fetch_premium_odds(sport_key)
        if df.empty:
            continue
        for _, row in df.iterrows():
            key = f"{row.get('Match','')}{row.get('_date','')}"
            if key not in seen:
                seen.add(key)
                events.append({"Date": row.get("_date",""), "Time": row.get("Time/Score","TBD"),
                               "Match": row.get("Match",""), "Sport": "🎾 Tennis"})
    return events


if __name__ == "__main__":
    main()
