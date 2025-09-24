
import streamlit as st
import pandas as pd
import math
from datetime import date, datetime, timedelta, time
from calendar import monthrange
from dateutil.relativedelta import relativedelta
# =========================
# 🧭 사이드바
# =========================
with st.sidebar:
    st.title("메뉴")
    page = st.radio("기능 선택",  ["시급 역산", "월급 계산", "월휴무 월급 계산", "연차 시간 환산"], index=0)

# 상수
# ---------------------------
WEEKS_PER_MONTH = 4.345
MAX_WEEKLY_HOURS = 40
MAX_MONTHLY_HOLIDAY = 35  # 월 주휴시간 상한
# ---------------------------
# 유틸
# ---------------------------
def hours_between(start: time, end: time) -> float:
    """출근~퇴근 구간 길이를 시간(float)로 반환. 자정 넘기면 +24h."""
    s = start.hour + start.minute / 60
    e = end.hour + end.minute / 60
    if e <= s:  # 자정 넘김
        e += 24
    return max(0.0, e - s)

def night_hours_simple(start: time, end: time) -> float:
    """야간(22~06=22~30h)과 근무구간의 단순 겹침(시간)."""
    s = start.hour + start.minute / 60
    e = end.hour + end.minute / 60
    if e <= s:
        e += 24.0
    return max(0.0, min(e, 30.0) - max(s, 22.0))

def ceil_if(x: float, flag: bool) -> float:
    """올림 옵션 적용(월 시간 단위)."""
    return math.ceil(x) if flag else x

def won_ceil(x: float) -> int:
    """원단위 올림."""
    return int(math.ceil(x - 1e-12))

def ceil_ones(n: int) -> int:
    """10원 단위 올림."""
    return int(math.ceil(n / 10.0) * 10)



if page == "시급 역산":
    st.title("💰 시급 역산 계산기")
    # ---------------------------
    # 입력
    # ---------------------------
    c1, c2 = st.columns(2)

    # 출근시간 입력 (시, 분)
    start_hour = c1.number_input("출근 시(hour)", min_value=0, max_value=23, value=10, step=1)
    start_min  = c1.number_input("출근 분(minute)", min_value=0, max_value=59, value=0, step=1)

    # 퇴근시간 입력 (시, 분)
    end_hour = c2.number_input("퇴근 시(hour)", min_value=0, max_value=23, value=23, step=1)
    end_min  = c2.number_input("퇴근 분(minute)", min_value=0, max_value=59, value=0, step=1)

    # datetime.time 객체로 변환
    from datetime import time
    start_t = time(int(start_hour), int(start_min))
    end_t   = time(int(end_hour), int(end_min))

    break_min = st.number_input("휴게시간 (분)", min_value=0, max_value=600, step=5, value=60)
    break_h = break_min / 60
    meal    = st.number_input("식대 (고정수당)", min_value=0, step=1000, value=0)
    car     = st.number_input("차량유지비 (고정수당)", min_value=0, step=1000, value=0)
    days_wk = st.number_input("주 근로일수", min_value=1, max_value=7, value=5)
    salary  = st.number_input("월 급여", min_value=0, step=1000, value=5_000_000)

    c3, c4 = st.columns(2)
    is_5p   = c3.checkbox("5인 이상 사업장 (연장 1.5배, 야간 0.5배)", value=True)
    ceil_on = c4.checkbox("월 시간 올림 적용 (근로/주휴/연장/야간)", value=True)

    # 🔧 항목별 10원 올림 옵션 (라디오)
    st.markdown("### 항목별 1의 자리 올림 설정")
    with st.expander("항목별 올림 설정 (선택 사항)", expanded=False):
        st.markdown("항목별 수당을 10원 단위로 올림할지 선택하세요.")

        opt_basic   = st.radio("기본급",   ["그대로", "올림"], horizontal=True, index=0, key="basic")
        opt_holiday = st.radio("주휴수당", ["그대로", "올림"], horizontal=True, index=0, key="holiday")
        opt_ot      = st.radio("연장수당", ["그대로", "올림"], horizontal=True, index=0, key="ot")
        opt_night   = st.radio("야간수당", ["그대로", "올림"], horizontal=True, index=0, key="night")
    # ---------------------------
    # 🔍 계산
    # ---------------------------
    if st.button("계산하기"):
        # 고정수당만으로 월급 초과 시 계산 불가
        if meal + car > salary:
            st.error("고정수당(식대+차량)이 월급여보다 큽니다. 입력값을 확인해주세요.")
            st.stop()

        # 1) 시간 산출
        daily_span = hours_between(start_t, end_t)             # 체류시간
        daily_work = max(0.0, daily_span - break_h)            # 휴게 차감 실근로
        weekly_raw  = daily_work * days_wk
        weekly_base = min(weekly_raw, MAX_WEEKLY_HOURS)        # 주 40h 제한

        monthly_base    = weekly_base * WEEKS_PER_MONTH
        # ✅ 주휴시간: 무조건 (주근로시간 ÷ 5) → 월 환산, 상한 35h
        monthly_holiday = min((weekly_base / 5.0) * WEEKS_PER_MONTH, MAX_MONTHLY_HOLIDAY)
        monthly_ot      = max(0.0, weekly_raw - MAX_WEEKLY_HOURS) * WEEKS_PER_MONTH
        monthly_night   = night_hours_simple(start_t, end_t) * days_wk * WEEKS_PER_MONTH

        # 2) 월 시간 올림
        monthly_base    = ceil_if(monthly_base,    ceil_on)
        monthly_holiday = ceil_if(monthly_holiday, ceil_on)
        monthly_ot      = ceil_if(monthly_ot,      ceil_on)
        monthly_night   = ceil_if(monthly_night,   ceil_on)

        denom_hours = monthly_base + monthly_holiday
        if denom_hours <= 0:
            st.error("분모 시간(기본근로+주휴)이 0입니다. 입력값을 확인하세요.")
            st.stop()

        # 3) 가산계수
        ot_factor    = 1.5 if is_5p else 1.0
        night_factor = 0.5 if is_5p else 0.0

        # 4) 초기 기준시급 추정 (올림)
        base_only = salary - meal - car
        init_base_wage = won_ceil(base_only / denom_hours)

        # 5) 총액 시뮬레이터
        def simulate_total(gwage: int):
            # 기본급/주휴수당
            base_pay = won_ceil(gwage * monthly_base)
            holi_pay = won_ceil(gwage * monthly_holiday)
            if opt_basic   == "올림": base_pay = ceil_ones(base_pay)
            if opt_holiday == "올림": holi_pay = ceil_ones(holi_pay)

            # ✅ 통상시급 (원단위 올림, 주휴 포함)
            normal_wage = won_ceil((base_pay + holi_pay + meal + car) / denom_hours)

            # 연장/야간
            overtime_pay = won_ceil(normal_wage * monthly_ot * ot_factor)
            night_pay    = won_ceil(normal_wage * monthly_night * night_factor)
            if opt_ot    == "올림": overtime_pay = ceil_ones(overtime_pay)
            if opt_night == "올림": night_pay    = ceil_ones(night_pay)

            total = base_pay + holi_pay + overtime_pay + night_pay + meal + car
            return normal_wage, total, base_pay, holi_pay, overtime_pay, night_pay

        # 6) 기준시급 탐색: 월급 이하 중 가장 근접
        bw = max(0, init_base_wage)
        nw, tot, bpay, hpay, otpay, npay = simulate_total(bw)

        if tot > salary:
            while bw > 0:
                bw -= 1
                nw, tot, bpay, hpay, otpay, npay = simulate_total(bw)
                if tot <= salary:
                    break
        else:
            while True:
                cand = bw + 1
                nw2, tot2, *_ = simulate_total(cand)
                if tot2 <= salary:
                    bw = cand
                    nw = nw2
                    tot = tot2
                    _, _, bpay, hpay, otpay, npay = simulate_total(bw)
                else:
                    break

        if tot > salary:
            bw = 0
            nw, tot, bpay, hpay, otpay, npay = simulate_total(bw)

        # ---------------------------
        # 📤 결과 출력
        # ---------------------------
        st.subheader("📊 계산 결과 (월급 이하·가장 근접 | 최저시급 : 10,030원)")
        st.write(f"✅ 기준시급(올림): **{bw:,}원**")
        st.write(f"✅ 통상시급(올림): **{nw:,}원**")

        st.write("---")
        st.write(f"📌 월 기본근로시간: {monthly_base:,.2f} h")
        st.write(f"📌 월 주휴시간(주근로/5, 최대 35h): {monthly_holiday:,.2f} h")
        st.write(f"📌 월 연장근로시간: {monthly_ot:,.2f} h")
        st.write(f"📌 월 야간근로시간(22~06): {monthly_night:,.2f} h")

        st.write("---")
        st.write(f"📌 기본급: {bpay:,}원")
        st.write(f"📌 주휴수당: {hpay:,}원")
        st.write(f"📌 연장근로수당: {otpay:,}원")
        st.write(f"📌 야간근로수당: {npay:,}원")
        st.write(f"📌 고정수당(식대+차량): {(meal+car):,}원")

        gap = salary - tot
        gap_pct = (gap / salary * 100) if salary else 0.0
        st.success(f"💵 총 계산액: **{tot:,}원** / 입력 월급여: **{salary:,}원**")
        if gap > 0:
            st.info(f"차이: **{gap:,}원** (입력 대비 **{gap_pct:.3f}%** 미달) — "
                    f"일치하려면 **{gap:,}원** 더 더해야 합니다.")
        elif gap == 0:
            st.info("입력 월급여와 정확히 일치합니다.")
        else:
            st.warning(f"총액이 월급여를 **{(-gap):,}원** 초과했습니다. (보정 필요)")

if page == "월급 계산":
    st.header("💵 월급 계산")

    # ---------------------------
    # 입력
    # ---------------------------
    c1, c2 = st.columns(2)

    # 출근시간 입력 (시, 분)
    start_hour = c1.number_input("출근 시(hour)", min_value=0, max_value=23, value=10, step=1)
    start_min  = c1.number_input("출근 분(minute)", min_value=0, max_value=59, value=0, step=1)

    # 퇴근시간 입력 (시, 분)
    end_hour = c2.number_input("퇴근 시(hour)", min_value=0, max_value=23, value=23, step=1)
    end_min  = c2.number_input("퇴근 분(minute)", min_value=0, max_value=59, value=0, step=1)

    # datetime.time 객체로 변환
    from datetime import time
    start_t = time(int(start_hour), int(start_min))
    end_t   = time(int(end_hour), int(end_min))

    break_min = st.number_input("휴게시간 (분)", min_value=0, max_value=600, step=5, value=60)
    break_h = break_min / 60
    meal    = st.number_input("식대 (고정수당)", min_value=0, step=1000, value=100_000)
    car     = st.number_input("차량유지비 (고정수당)", min_value=0, step=1000, value=200_000)
    days_wk = st.number_input("주 근로일수", min_value=1, max_value=7, value=5)

    gwage   = st.number_input("기준시급", min_value=0, step=10, value=10_030)

    c3, c4 = st.columns(2)
    is_5p   = c3.checkbox("5인 이상 사업장 (연장 1.5배, 야간 0.5배)", value=True)
    ceil_on = c4.checkbox("월 시간 올림 적용 (근로/주휴/연장/야간)", value=True)

    with st.expander("항목별 10원 단위 올림 설정"):
        opt_basic   = st.checkbox("기본급 10원 단위 올림")
        opt_holiday = st.checkbox("주휴수당 10원 단위 올림")
        opt_ot      = st.checkbox("연장수당 10원 단위 올림")
        opt_night   = st.checkbox("야간수당 10원 단위 올림")

    if st.button("계산하기"):
        # (시간 계산 로직은 '시급 역산'과 동일)
        daily_span = hours_between(start_t, end_t)
        daily_work = max(0.0, daily_span - break_h)
        weekly_raw  = daily_work * days_wk
        weekly_base = min(weekly_raw, MAX_WEEKLY_HOURS)

        monthly_base    = weekly_base * WEEKS_PER_MONTH
        monthly_holiday = min((weekly_base / 5.0) * WEEKS_PER_MONTH, MAX_MONTHLY_HOLIDAY)
        monthly_ot      = max(0.0, weekly_raw - MAX_WEEKLY_HOURS) * WEEKS_PER_MONTH
        monthly_night   = night_hours_simple(start_t, end_t) * days_wk * WEEKS_PER_MONTH

        # 올림
        monthly_base    = ceil_if(monthly_base,    ceil_on)
        monthly_holiday = ceil_if(monthly_holiday, ceil_on)
        monthly_ot      = ceil_if(monthly_ot,      ceil_on)
        monthly_night   = ceil_if(monthly_night,   ceil_on)

        denom_hours = monthly_base + monthly_holiday

        # 가산계수
        ot_factor    = 1.5 if is_5p else 1.0
        night_factor = 0.5 if is_5p else 0.0

        # 시뮬레이션
        base_pay = won_ceil(gwage * monthly_base)
        holi_pay = won_ceil(gwage * monthly_holiday)
        if opt_basic:   base_pay = ceil_ones(base_pay)
        if opt_holiday: holi_pay = ceil_ones(holi_pay)

        normal_wage = won_ceil((base_pay + holi_pay + meal + car) / denom_hours)

        overtime_pay = won_ceil(normal_wage * monthly_ot * ot_factor)
        night_pay    = won_ceil(normal_wage * monthly_night * night_factor)
        if opt_ot:    overtime_pay = ceil_ones(overtime_pay)
        if opt_night: night_pay    = ceil_ones(night_pay)

        total = base_pay + holi_pay + overtime_pay + night_pay + meal + car

        # 결과 출력
        st.subheader("📊 계산 결과 (월급 계산) | 최저시급 : 10,030원")
        st.write(f"✅ 기준시급: **{gwage:,}원**")
        st.write(f"✅ 통상시급(올림): **{normal_wage:,}원**")

        st.write("---")
        st.write(f"⏱ 월 기본근로시간: {monthly_base:,.2f} h")
        st.write(f"⏱ 월 주휴시간(주근로/5, 최대 35h): {monthly_holiday:,.2f} h")
        st.write(f"⏱ 월 연장근로시간: {monthly_ot:,.2f} h")
        st.write(f"⏱ 월 야간근로시간(22~06): {monthly_night:,.2f} h")

        st.write("---")
        st.write(f"📌 기본급: {base_pay:,}원")
        st.write(f"📌 주휴수당: {holi_pay:,}원")
        st.write(f"📌 연장근로수당: {overtime_pay:,}원")
        st.write(f"📌 야간근로수당: {night_pay:,}원")
        st.write(f"📌 고정수당(식대+차량): {(meal+car):,}원")

        st.success(f"💵 총 월 급여: **{total:,}원**")

if page == "월휴무 월급 계산":
    st.header("🗓️ 월휴무 기반 월급 계산")

    # ── 출퇴근 시간: 숫자 직접 입력 (시/분)
    c1, c2 = st.columns(2)
    start_hour = c1.number_input("출근 시(hour)", min_value=0, max_value=23, value=10, step=1)
    start_min  = c1.number_input("출근 분(minute)", min_value=0, max_value=59, value=0, step=1)
    end_hour   = c2.number_input("퇴근 시(hour)",   min_value=0, max_value=23, value=23, step=1)
    end_min    = c2.number_input("퇴근 분(minute)", min_value=0, max_value=59, value=0, step=1)

    from datetime import time as _time
    start_t = _time(int(start_hour), int(start_min))
    end_t   = _time(int(end_hour), int(end_min))

    # ── 휴게시간: 분 단위 입력 → 시간(float)로 변환
    break_min = st.number_input("휴게시간 (분)", min_value=0, max_value=600, value=60, step=5)
    break_h   = break_min / 60.0

    # ── 시급/고정수당
    gwage = st.number_input("기준시급(원)", min_value=0, step=10, value=10_030)
    meal  = st.number_input("식대 (고정수당)", min_value=0, step=1000, value=100_000)
    car   = st.number_input("차량유지비 (고정수당)", min_value=0, step=1000, value=200_000)

    # ── 월 휴무일 입력 → 주 휴일/주 근로일 환산
    WEEKS_PER_MONTH = 4.345
    monthly_off = st.number_input("월 휴무일(일)", min_value=0.0, step=0.5, value=6.0)
    weekly_holidays = monthly_off / WEEKS_PER_MONTH          # 주 휴일(일/주)
    days_wk_raw     = 7.0 - weekly_holidays                  # 주 근로일(일/주)
    days_wk         = max(0.0, min(7.0, days_wk_raw))        # 안전 클램프

    c3, c4 = st.columns(2)
    is_5p   = c3.checkbox("5인 이상 사업장 (연장 1.5배, 야간 0.5배)", value=True)
    ceil_on = c4.checkbox("월 시간 올림 적용 (근로/주휴/연장/야간)", value=True)

    with st.expander("항목별 10원 단위 올림 설정 (선택)"):
        opt_basic   = st.checkbox("기본급 10원 단위 올림", value=False)
        opt_holiday = st.checkbox("주휴수당 10원 단위 올림", value=False)
        opt_ot      = st.checkbox("연장수당 10원 단위 올림", value=False)
        opt_night   = st.checkbox("야간수당 10원 단위 올림", value=False)

    if st.button("월급 계산하기", type="primary"):
        # ── 시간 계산 (월급 계산 로직 동일)
        MAX_WEEKLY_HOURS   = 40
        MAX_MONTHLY_HOLIDAY = 35

        daily_span = hours_between(start_t, end_t)
        daily_work = max(0.0, daily_span - break_h)

        weekly_raw  = daily_work * days_wk
        weekly_base = min(weekly_raw, MAX_WEEKLY_HOURS)

        monthly_base    = weekly_base * WEEKS_PER_MONTH
        # 주휴시간: 무조건 (주근로시간 ÷ 5) → 월 환산, 상한 35h
        monthly_holiday = min((weekly_base / 5.0) * WEEKS_PER_MONTH, MAX_MONTHLY_HOLIDAY)
        monthly_ot      = max(0.0, weekly_raw - MAX_WEEKLY_HOURS) * WEEKS_PER_MONTH
        monthly_night   = night_hours_simple(start_t, end_t) * days_wk * WEEKS_PER_MONTH

        # 월 시간 올림 옵션
        monthly_base    = ceil_if(monthly_base,    ceil_on)
        monthly_holiday = ceil_if(monthly_holiday, ceil_on)
        monthly_ot      = ceil_if(monthly_ot,      ceil_on)
        monthly_night   = ceil_if(monthly_night,   ceil_on)

        denom_hours = monthly_base + monthly_holiday
        if denom_hours <= 0:
            st.error("분모 시간(기본근로+주휴)이 0입니다. 입력값을 확인하세요.")
            st.stop()

        # 가산계수
        ot_factor    = 1.5 if is_5p else 1.0
        night_factor = 0.5 if is_5p else 0.0

        # ── 금액 계산 (모든 금액: 원단위 올림, 통상시급은 주휴 포함)
        base_pay = won_ceil(gwage * monthly_base)
        holi_pay = won_ceil(gwage * monthly_holiday)
        if opt_basic:   base_pay = ceil_ones(base_pay)     # 10원 단위 올림
        if opt_holiday: holi_pay = ceil_ones(holi_pay)

        normal_wage = won_ceil((base_pay + holi_pay + meal + car) / denom_hours)

        overtime_pay = won_ceil(normal_wage * monthly_ot * ot_factor)
        night_pay    = won_ceil(normal_wage * monthly_night * night_factor)
        if opt_ot:    overtime_pay = ceil_ones(overtime_pay)
        if opt_night: night_pay    = ceil_ones(night_pay)

        total = base_pay + holi_pay + overtime_pay + night_pay + meal + car

        # ── 결과 출력
        st.subheader("📊 계산 결과 | 최저시급 : 10,030원")
        st.write(f"✅ 기준시급(입력): **{gwage:,}원**")
        st.write(f"✅ 통상시급(올림): **{normal_wage:,}원**")

        st.write("---")
        st.write(f"⏱ 월 기본근로시간: {monthly_base:,.2f} h")
        st.write(f"⏱ 월 주휴시간(주근로/5, 최대 35h): {monthly_holiday:,.2f} h")
        st.write(f"⏱ 월 연장근로시간: {monthly_ot:,.2f} h")
        st.write(f"⏱ 월 야간근로시간(22~06): {monthly_night:,.2f} h")

        st.write("---")
        st.write(f"📌 기본급: {base_pay:,}원")
        st.write(f"📌 주휴수당: {holi_pay:,}원")
        st.write(f"📌 연장근로수당: {overtime_pay:,}원")
        st.write(f"📌 야간근로수당: {night_pay:,}원")
        st.write(f"📌 고정수당(식대+차량): {(meal+car):,}원")

        st.write("---")
        st.info(f"🧮 입력한 월 휴무일: **{monthly_off:.2f}일** → "
                f"주 휴일: **{weekly_holidays:.3f}일/주** → "
                f"주 근로일: **{days_wk:.3f}일/주**")

        st.success(f"💵 총 월 급여: **{total:,}원**")


# =========================================================
# 사이드바 네비게이션
# =========================================================


# =========================
# 🔧 유틸 함수 (목적/주석 명확히)
# =========================
def eom(d: date) -> date:
    """주어진 날짜 d가 속한 달의 '말일'을 반환."""
    return date(d.year, d.month, monthrange(d.year, d.month)[1])

def days_between_inclusive(a: date, b: date) -> int:
    """양 끝 포함 일수. (a==b면 1일)"""
    return (b - a).days + 1

def normalize_changes(anchor: date, changes: list[tuple[date, float]], default_wsh: float):
    """
    [WSH 타임라인 정규화]
    - changes: [(효력일, WSH)]  → '효력일 당일부터' 해당 WSH 적용
    - anchor 이전 구간의 WSH가 비어 있으면 (anchor, default_wsh) 삽입
    - 효력일 오름차순 정렬
    """
    arr = []
    for d, w in changes:
        if isinstance(d, datetime):
            d = d.date()
        arr.append((d, float(w)))
    arr.sort(key=lambda x: x[0])
    if not arr or arr[0][0] > anchor:
        arr = [(anchor, default_wsh)] + arr
    return arr

def split_by_changes(start: date, end: date, changes: list[tuple[date, float]]):
    """
    [WSH 구간 분할]
    - 입력 구간 [start, end]을 WSH 변경점(효력일)을 경계로 쪼개,
      WSH가 일정한 세그먼트들의 리스트를 반환.
    - 반환: [(seg_start, seg_end, wsh), ...]
    """
    if start > end:
        return []

    # 시작 시점의 WSH 찾기
    cur_wsh = None
    for eff, w in changes:
        if eff <= start:
            cur_wsh = w
        else:
            break
    if cur_wsh is None:
        raise ValueError("시작 시점의 WSH가 정의되지 않았습니다. 입력을 확인하세요.")

    segs = []
    cur_start = start
    for eff, w in changes:
        if eff <= start:
            continue
        if eff > end:
            break
        seg_end = eff - timedelta(days=1)
        if cur_start <= seg_end:
            segs.append((cur_start, seg_end, cur_wsh))
        cur_start = eff
        cur_wsh = w
    if cur_start <= end:
        segs.append((cur_start, end, cur_wsh))
    return segs

def human_readable(segs: list[tuple[date, date, float]]) -> str:
    """세그먼트 리스트를 사람이 보기 좋은 문자열로."""
    return " | ".join([f"{s}~{e} (WSH={w})" for s, e, w in segs])

def statutory_days(service_years: int) -> int:
    """
    [1년 이상 연차일수 매핑(간단화)]
    - 1년차: 15일
    - 이후 2년에 1일씩 가산, 최대 25일
    (1→15, 2→15, 3→16, 4→16, …, 21→25, 22→25)
    """
    if service_years <= 0:
        return 0
    inc = (service_years - 1) // 2
    return min(15 + inc, 25)

# =========================
# 🧮 1) 1년 미만 — “입사일 기준 매월 같은 날” 방식
# =========================
def accrual_under_1y_monthly(join_dt: date, end_limit: date,
                             changes: list[tuple[date, float]], default_wsh: float):
    """
    [1년 미만 · 월 단위 발생]
    - 입사일 기준으로 매월 같은 '일(day)'에 1일 발생 (최대 11회)
      예) 7/15 입사 → 8/15, 9/15, 10/15 … (최대 11번)
    - 각 부여일 award_date 의 '직전 한 달'을 참조:
        ref_start = award_date - 1개월
        ref_end   = award_date - 1일
      이 기간에 WSH가 바뀌면 일수비율 가중 평균.
    - 연차시간 = 1일 × 평균 WSH
    """
    changes = normalize_changes(join_dt, changes, default_wsh)

    # 1년 종료일(입사 1년 전날)까지만 계산
    one_year_end = join_dt + relativedelta(years=1) - timedelta(days=1)
    period_end = min(end_limit, one_year_end)

    rows = []
    for n in range(1, 12):  # 최대 11회
        award_date = join_dt + relativedelta(months=n)
        if award_date > period_end:
            break

        ref_start = join_dt + relativedelta(months=n-1)
        ref_end = award_date - timedelta(days=1)

        segs = split_by_changes(ref_start, ref_end, changes)
        month_days = days_between_inclusive(ref_start, ref_end)

        # 가중 평균 WSH
        weighted_wsh = 0.0
        for s, e, w in segs:
            frac = days_between_inclusive(s, e) / month_days
            weighted_wsh += frac * w

        rows.append({
            "award_date": award_date,
            "ref_start": ref_start,
            "ref_end": ref_end,
            "ref_window": f"{ref_start} ~ {ref_end}",
            "month_days": month_days,
            "avg_wsh": weighted_wsh,
            "accrual_days": 1.0,
            "accrual_hours": weighted_wsh,
            "splits": human_readable(segs)
        })

    df = pd.DataFrame(rows)
    totals = {
        "days_total": df["accrual_days"].sum() if not df.empty else 0.0,
        "hours_total": df["accrual_hours"].sum() if not df.empty else 0.0
    }
    return df, totals

# =========================
# 🧮 2) 1년 이상 — 연차년도 정액(표) × WSH 비율 배분
# =========================
def accrual_over_1y(join_dt: date, target_anniv: date,
                    changes: list[tuple[date, float]], default_wsh: float):
    """
    [1년 이상]
    - 연차년도: [작년 기념일, 이번 기념일 - 1일]
    - 표상 연차일수 N을 1년 구간에서 WSH 변화 비율로 배분하여 시수 환산.
    """
    prev_anniv = target_anniv - relativedelta(years=1)
    service_years = relativedelta(target_anniv, join_dt).years
    N = statutory_days(service_years)

    changes = normalize_changes(prev_anniv, changes, default_wsh)
    segs = split_by_changes(prev_anniv, target_anniv - timedelta(days=1), changes)

    total_days_in_year = days_between_inclusive(prev_anniv, target_anniv - timedelta(days=1))
    rows, total_hours = [], 0.0
    for s, e, w in segs:
        seg_days = days_between_inclusive(s, e)
        ratio = seg_days / total_days_in_year
        alloc_days = N * ratio
        hours = alloc_days * w
        rows.append({
            "start": s, "end": e,
            "seg_days": seg_days,
            "seg_ratio": ratio,
            "alloc_days": alloc_days,
            "wsh": w,
            "alloc_hours": hours
        })
        total_hours += hours

    df = pd.DataFrame(rows)
    totals = {"days_total": float(N), "hours_total": total_hours}
    return service_years, N, df, totals, prev_anniv, target_anniv

# =========================
# 🖥️ 메인 UI
# =========================
if page == "연차 시간 환산":

    st.markdown("#### 입력 설정")
    c1, c2 = st.columns(2)
    join_dt: date = c1.date_input("입사일", value=date(2024, 7, 15))
    default_wsh = c2.number_input("입사 시 WSH(연차시간(단위:주))", min_value=0.0, step=0.1, value=3.0, 
                                  help="연차시간 = 주당 근로시간 / 5")
    st.caption("※ WSH = 주당 연차시간. '효력일 당일'부터 적용됩니다.")

    # 변경표 입력
    st.markdown("##### WSH 변경표 (효력일, WSH)")
    sample_df = pd.DataFrame({"효력일": [join_dt], "WSH": [default_wsh]})
    changes_df = st.data_editor(
        sample_df, num_rows="dynamic", use_container_width=True,
        column_config={
            "효력일": st.column_config.DateColumn("효력일"),
            "WSH": st.column_config.NumberColumn("WSH", step=0.1, help="연차시간(단위:주)")
        },
        key="changes_editor"
    )
    changes_list = [(pd.to_datetime(r["효력일"]).date(), float(r["WSH"]))
                    for _, r in changes_df.dropna().iterrows()]

    st.divider()
    tab1, tab2 = st.tabs(["🍼 1년 미만 (매월 같은 날)", "🏅 1년 이상 (연차년도 정액)"])

    # ------- 1년 미만 (매월 같은 날) -------
    with tab1:
        st.markdown("##### 규칙: 입사일과 같은 '날짜'에 매월 1일 발생 (최대 11회)")
        end_limit = st.date_input(
            "계산 종료일 (기본: 입사 후 1년 전날까지)",
            value=join_dt + relativedelta(years=1) - timedelta(days=1),
            help="예) 7/15 입사 → 8/15, 9/15, 10/15 …"
        )
        if st.button("계산하기 (1년 미만 · 월 단위)", type="primary"):
            df, totals = accrual_under_1y_monthly(join_dt, end_limit, changes_list, default_wsh)
            if df.empty:
                st.warning("부여 스케줄이 없습니다. 입력값을 확인하세요.")
            else:
                st.subheader("📊 부여 스케줄 (직전 한 달 참조)")
                st.dataframe(
                    df[["award_date", "ref_window", "month_days", "avg_wsh",
                        "accrual_days", "accrual_hours", "splits"]],
                    use_container_width=True
                )
                st.success(f"합계: 발생일수 **{totals['days_total']:.0f}일** / 연차시간 **{totals['hours_total']:.2f}시간**")

    # ------- 1년 이상 (정액) -------
    with tab2:
        st.markdown("##### 규칙: 연차년도(작년 기념일 ~ 이번 기념일-1일) 정액을 WSH 비율로 시수 환산")
        target_anniv = st.date_input(
            "이번 기념일(정산 기준일)", value=date(2025, 9, 12),
            help="예: 2025-09-12 → [2024-09-12 ~ 2025-09-11]이 대상 연차년도입니다."
        )
        if st.button("계산하기 (1년 이상)", type="primary"):
            svc_years, N, df2, totals2, prev_anniv, this_anniv = accrual_over_1y(
                join_dt, target_anniv, changes_list, default_wsh
            )
            st.info(f"근속연수 **{svc_years}년**, 표상 연차 **{N}일**, 대상연차년도 **{prev_anniv} ~ {this_anniv - timedelta(days=1)}**")
            if df2.empty:
                st.warning("결과가 비어 있습니다.")
            else:
                df2_show = df2.copy()
                df2_show["seg_ratio(%)"] = (df2_show["seg_ratio"] * 100).round(3)
                st.dataframe(
                    df2_show[["start","end","seg_days","seg_ratio(%)","alloc_days","wsh","alloc_hours"]],
                    use_container_width=True
                )
                st.success(f"합계: 발생일수 **{totals2['days_total']:.2f}일** / 연차시간 **{totals2['hours_total']:.2f}시간**")


