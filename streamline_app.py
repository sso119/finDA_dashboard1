import datetime as dt

import plotly.graph_objects as go
import streamlit as st

# ---------------------------------------------------------------------------
# Page config & dark theme styling
# ---------------------------------------------------------------------------
st.set_page_config(page_title="급등 후 과열위험 조기진단", layout="wide")

C = {
    "bg": "#0A0E13",
    "panel": "#12171F",
    "panelAlt": "#161C25",
    "border": "#232B36",
    "borderSoft": "#1B222B",
    "text": "#E7ECF2",
    "textDim": "#8E99A8",
    "textFaint": "#5D6673",
    "teal": "#33C6A6",
    "tealDim": "#1E5347",
    "amber": "#E3A23D",
    "amberDim": "#4A3A1D",
    "violet": "#7C86E8",
    "violetDim": "#2B2E52",
    "grid": "#1A2029",
}

st.markdown(
    f"""
    <style>
    .stApp {{ background-color: {C['bg']}; color: {C['text']}; }}
    div[data-testid="stMetricValue"] {{ font-family: monospace; }}
    .panel {{
        background: {C['panel']};
        border: 1px solid {C['border']};
        border-radius: 12px;
        padding: 18px;
    }}
    .chip {{
        display: inline-block;
        padding: 3px 10px;
        border-radius: 999px;
        font-size: 12px;
        font-weight: 600;
    }}
    .small-dim {{ color: {C['textFaint']}; font-size: 11px; }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Model reliability table (RF + P, 2026 Stress Test)
# ---------------------------------------------------------------------------
TIERS = {
    "T": dict(auc=0.617, precision=37.2, recall=95.8, ba=55.1, tier="low",
              tier_label="아직 이른 진단",
              note="급등 당일이라 정보가 적어요. 참고만 하고 다음 갱신을 기다리세요."),
    "T+3": dict(auc=0.769, precision=47.2, recall=88.5, ba=68.0, tier="medium",
                tier_label="참고 신호",
                note="정확도가 올라가는 중이지만, 아직 단독으로 판단하기엔 이릅니다."),
    "T+5": dict(auc=0.778, precision=52.1, recall=76.0, ba=69.5, tier="high",
                tier_label="믿을 수 있는 조기경보",
                note="가장 빠르면서도 안정적으로 맞는 시점이에요. 이후 시점과 정확도 차이도 크지 않아요."),
    "T+7": dict(auc=0.803, precision=56.8, recall=82.3, ba=74.6, tier="high",
                tier_label="조기경보",
                note="T+5보다 조금 더 정확하지만, 그 차이는 크지 않아요."),
    "T+10": dict(auc=0.827, precision=56.3, recall=79.2, ba=73.3, tier="reference",
                 tier_label="확인용 (많이 진행됨)",
                 note="이미 20일 관찰기간의 절반이 지나 결과가 어느 정도 드러난 시점이에요."),
}
TIMINGS = ["T", "T+3", "T+5", "T+7", "T+10"]
TIMING_OFFSET = {"T": 0, "T+3": 3, "T+5": 5, "T+7": 7, "T+10": 10}
TIMING_LABEL = {"T": "급등일", "T+3": "+3일", "T+5": "+5일", "T+7": "+7일", "T+10": "+10일"}

TIER_COLOR = {
    "low": C["textDim"],
    "medium": C["amber"],
    "high": C["teal"],
    "reference": C["violet"],
}

RISK_BINS = [
    ("Q1", 0.139, 7.1),
    ("Q2", 0.312, 14.5),
    ("Q3", 0.500, 34.5),
    ("Q4", 0.700, 52.7),
    ("Q5", 0.805, 64.3),
]


def calibrated_risk(score: float) -> float:
    pts = RISK_BINS
    if score <= pts[0][1]:
        return pts[0][2]
    if score >= pts[-1][1]:
        return pts[-1][2]
    for (q1, s1, a1), (q2, s2, a2) in zip(pts, pts[1:]):
        if s1 <= score <= s2:
            t = (score - s1) / (s2 - s1)
            return a1 + t * (a2 - a1)
    return pts[-1][2]


def bin_of(score: float) -> str:
    for q, s, _ in reversed(RISK_BINS):
        if score >= s - 0.1:
            return q
    return "Q1"


def date_for(event_date: str, timing: str) -> str:
    d = dt.date.fromisoformat(event_date) + dt.timedelta(days=TIMING_OFFSET[timing])
    return f"{d.month}.{d.day}"


# ---------------------------------------------------------------------------
# Mock events — 화면 예시용 가상 데이터 (실 서비스에는 모델 산출 스코어 연결)
# ---------------------------------------------------------------------------
def build_series(seed: float, drawdown_from: int):
    stock, kospi = [100.0], [100.0]
    s = k = 100.0
    for i in range(1, 21):
        import math
        noise = math.sin(i * seed) * 0.6
        drift = 1.1 if i < drawdown_from else -0.35
        s += drift + noise
        k += 0.15 + noise * 0.2
        stock.append(round(s, 1))
        kospi.append(round(k, 1))
    return stock, kospi


EVENTS = {
    "mirae": dict(name="미래소재", date="2026-07-08", return20d=22.1, vol_mult=1.8,
                  scores={"T": 0.24, "T+3": 0.29, "T+5": 0.28, "T+7": 0.27, "T+10": 0.25},
                  series=build_series(0.45, 14)),
    "hanbit": dict(name="한빛전자", date="2026-07-01", return20d=26.8, vol_mult=2.4,
                   scores={"T": 0.52, "T+3": 0.61, "T+5": 0.70, "T+7": 0.78, "T+10": 0.81},
                   series=build_series(0.30, 8)),
    "saeron": dict(name="새론바이오", date="2026-07-11", return20d=31.4, vol_mult=3.1,
                   scores={"T": 0.44, "T+3": 0.55, "T+5": 0.63, "T+7": None, "T+10": None},
                   series=build_series(0.60, 10)),
}

# ---------------------------------------------------------------------------
# Header
# ---------------------------------------------------------------------------
st.markdown(
    f"<div class='small-dim'>SURGE RISK MONITOR · 화면 예시 · 가상 종목·점수 사용</div>",
    unsafe_allow_html=True,
)
st.markdown("### 급등 이후 과열위험 조기진단")
st.markdown(
    "<div class='small-dim'>시점을 바꾸면 급등일/+3일/+5일/+7일/+10일 모델이 적용되고, "
    "신뢰도가 낮은 시점의 진단은 자동으로 톤을 낮춰 표시합니다.</div>",
    unsafe_allow_html=True,
)
st.write("")

# ---------------------------------------------------------------------------
# Selectors
# ---------------------------------------------------------------------------
col_a, col_b = st.columns([1, 2])
with col_a:
    event_id = st.selectbox(
        "급등 사건",
        options=list(EVENTS.keys()),
        format_func=lambda k: f"{EVENTS[k]['name']} · {EVENTS[k]['date']}",
    )
event = EVENTS[event_id]

with col_b:
    st.write("조회 시점")
    tab_cols = st.columns(len(TIMINGS))
    if "timing" not in st.session_state:
        st.session_state.timing = "T+5"
    for i, t in enumerate(TIMINGS):
        available = event["scores"][t] is not None
        label = f"{TIMING_LABEL[t]}\n{date_for(event['date'], t)}"
        with tab_cols[i]:
            if st.button(label, key=f"{event_id}-{t}", disabled=not available,
                         use_container_width=True):
                st.session_state.timing = t

timing = st.session_state.timing
if event["scores"][timing] is None:
    timing = next(t for t in TIMINGS if event["scores"][t] is not None)
    st.session_state.timing = timing

score = event["scores"][timing]
meta = TIERS[timing]
tier_color = TIER_COLOR[meta["tier"]]

st.write("")

# ---------------------------------------------------------------------------
# Main row: gauge + reliability panel
# ---------------------------------------------------------------------------
col1, col2 = st.columns(2)

with col1:
    risk_pct = calibrated_risk(score)
    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=risk_pct,
            number={"suffix": "%", "font": {"color": C["text"], "size": 34}},
            gauge={
                "axis": {"range": [0, 100], "visible": False},
                "bar": {"color": tier_color},
                "bgcolor": C["borderSoft"],
                "borderwidth": 0,
            },
        )
    )
    fig.update_layout(
        paper_bgcolor=C["panel"],
        height=180,
        margin=dict(t=10, b=10, l=10, r=10),
    )
    with st.container(border=True):
        gc1, gc2 = st.columns([1, 1.4])
        with gc1:
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})
        with gc2:
            st.markdown(
                f"<span class='chip' style='color:{tier_color};"
                f"background:{C['panelAlt']};border:1px solid {tier_color}55'>"
                f"{meta['tier_label']}</span>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div class='small-dim' style='margin-top:8px'>예측점수 {score:.2f} · "
                f"{TIMING_LABEL[timing]}({date_for(event['date'], timing)}) 기준</div>",
                unsafe_allow_html=True,
            )
            st.markdown(
                f"<div style='margin-top:8px;font-size:13px;color:{C['textDim']}'>"
                f"{meta['note']}</div>",
                unsafe_allow_html=True,
            )

with col2:
    with st.container(border=True):
        st.markdown(
            f"<div style='font-size:12px;color:{C['textDim']};font-weight:600;"
            f"margin-bottom:10px'>시점별 모델 신뢰도 (2026 Stress Test)</div>",
            unsafe_allow_html=True,
        )
        for t in TIMINGS:
            d = TIERS[t]
            active = t == timing
            bar_color = TIER_COLOR[d["tier"]] if active else f"{TIER_COLOR[d['tier']]}55"
            pct = d["auc"] / 0.9 * 100
            st.markdown(
                f"""
                <div style='display:flex;align-items:center;gap:8px;margin-bottom:6px'>
                    <div style='width:34px;font-family:monospace;font-size:11px;
                        color:{C['text'] if active else C['textFaint']};
                        font-weight:{700 if active else 400}'>{t}</div>
                    <div style='flex:1;height:6px;background:{C['borderSoft']};
                        border-radius:4px;overflow:hidden'>
                        <div style='width:{pct}%;height:100%;background:{bar_color};
                            border-radius:4px'></div>
                    </div>
                    <div style='width:40px;text-align:right;font-family:monospace;
                        font-size:11px;color:{C['text'] if active else C['textFaint']}'>
                        {d['auc']:.3f}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        st.markdown(
            f"<div class='small-dim'>막대 길이 = 2026 Stress Test ROC-AUC</div>",
            unsafe_allow_html=True,
        )
        m1, m2, m3 = st.columns(3)
        m1.metric("Precision", f"{meta['precision']}%")
        m2.metric("Recall", f"{meta['recall']}%")
        m3.metric("Balanced Acc.", f"{meta['ba']}%")

st.write("")

# ---------------------------------------------------------------------------
# Metrics row
# ---------------------------------------------------------------------------
mcol1, mcol2, mcol3 = st.columns(3)
next_timing = TIMINGS[min(TIMINGS.index(timing) + 1, len(TIMINGS) - 1)]
mcol1.metric("20일 수익률", f"+{event['return20d']}%", help="급등 탐지 시점")
mcol2.metric("거래량 배수", f"{event['vol_mult']}배", help="직전 20일 평균 대비")
mcol3.metric(
    "다음 갱신",
    f"{TIMING_LABEL[next_timing]} ({date_for(event['date'], next_timing)})",
    help=f"{TIMING_OFFSET[next_timing] - TIMING_OFFSET[timing]}거래일 후",
)

st.write("")

# ---------------------------------------------------------------------------
# Risk bin context
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown(
        f"<div style='font-size:12px;color:{C['textDim']};font-weight:600'>"
        f"과거 유사 예측점수 구간의 실제 위험률</div>",
        unsafe_allow_html=True,
    )
    active_q = bin_of(score)
    bin_cols = st.columns(len(RISK_BINS))
    for i, (q, s, a) in enumerate(RISK_BINS):
        active = q == active_q
        bg = C["tealDim"] if active else C["panelAlt"]
        border = C["teal"] if active else C["borderSoft"]
        fg = C["text"] if active else C["textDim"]
        with bin_cols[i]:
            st.markdown(
                f"""
                <div style='background:{bg};border:1px solid {border};border-radius:8px;
                    padding:8px 6px;text-align:center'>
                    <div style='font-family:monospace;font-size:10px;
                        color:{C['teal'] if active else C['textFaint']}'>{q}</div>
                    <div style='font-family:monospace;font-size:14px;font-weight:700;
                        color:{fg}'>{a}%</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
    st.markdown(
        f"<div class='small-dim' style='margin-top:8px'>예측점수 자체는 실제 위험률보다 "
        f"높게 나오는 경향이 있어, 게이지의 %는 원점수가 아니라 이 구간별 실측 위험률로 "
        f"환산한 값입니다.</div>",
        unsafe_allow_html=True,
    )

st.write("")

# ---------------------------------------------------------------------------
# Relative performance chart
# ---------------------------------------------------------------------------
with st.container(border=True):
    st.markdown(
        f"<div style='font-size:12px;color:{C['textDim']};font-weight:600'>"
        f"사건일 이후 상대성과</div>",
        unsafe_allow_html=True,
    )
    stock_series, kospi_series = event["series"]
    days = list(range(21))
    day_labels = ["급등일" if d == 0 else f"+{d}일" for d in days]

    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(x=days, y=stock_series, mode="lines", name="종목",
                               line=dict(color=C["teal"], width=2.2)))
    fig2.add_trace(go.Scatter(x=days, y=kospi_series, mode="lines", name="KOSPI200",
                               line=dict(color=C["textFaint"], width=1.5, dash="dot")))
    fig2.add_vline(x=TIMING_OFFSET[timing], line_dash="dash", line_color=tier_color,
                    annotation_text=f"조회 {TIMING_LABEL[timing]}",
                    annotation_font_color=tier_color)
    fig2.update_layout(
        paper_bgcolor=C["panel"],
        plot_bgcolor=C["panel"],
        height=280,
        margin=dict(t=30, b=10, l=10, r=10),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
                    font=dict(color=C["textDim"])),
        xaxis=dict(tickmode="array", tickvals=days, ticktext=day_labels,
                   gridcolor=C["grid"], color=C["textFaint"]),
        yaxis=dict(gridcolor=C["grid"], color=C["textFaint"]),
    )
    st.plotly_chart(fig2, use_container_width=True, config={"displayModeBar": False})

st.markdown(
    f"<div class='small-dim' style='margin-top:12px'>모델: RandomForest + 가격·거래량(P) · "
    f"검증: 시간순 워크포워드 + 2025년 검증 + 2026년 스트레스 테스트 · "
    f"+10일은 20일 관찰기간의 절반을 이미 지난 시점으로 확인용입니다.</div>",
    unsafe_allow_html=True,
)
