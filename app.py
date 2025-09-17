import streamlit as st
import math
from datetime import time

# =========================
# 🧭 사이드바
# =========================
with st.sidebar:
    st.title("메뉴")
    page = st.radio("기능 선택", ["월급 계산", "시급 역산"], index=0)

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
    start_t = c1.time_input("출근시간", value=time(10, 0))
    end_t   = c2.time_input("퇴근시간", value=time(23, 0))

    break_h = st.number_input("휴게시간 (시간)", min_value=0.0, step=0.25, value=1.0)
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
        st.subheader("📊 계산 결과 (월급 이하·가장 근접)")
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
    start_t = c1.time_input("출근시간", value=time(10, 0))
    end_t   = c2.time_input("퇴근시간", value=time(23, 0))

    break_h = st.number_input("휴게시간 (시간)", min_value=0.0, step=0.25, value=1.0)
    meal    = st.number_input("식대 (고정수당)", min_value=0, step=1000, value=100_000)
    car     = st.number_input("차량유지비 (고정수당)", min_value=0, step=1000, value=200_000)
    days_wk = st.number_input("주 근로일수", min_value=1, max_value=7, value=5)

    gwage   = st.number_input("기준시급", min_value=0, step=10, value=10_000)

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
        st.subheader("📊 계산 결과 (월급 계산)")
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
