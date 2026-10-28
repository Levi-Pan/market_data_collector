from datetime import datetime, timedelta, timezone

import pandas_market_calendars as mcal

from standard_module.config import (
    CALENDAR_LOOKBACK_DAYS,
    MARKET_CALENDAR_NAME,
    MARKET_CLOSE_DELAY_MINUTES,
)


def get_completed_trading_dates(count, decision_time=None):
    """
    获取最近已收盘且经过等待时间的交易日期。

    :param count: 需要的交易日数量
    :param decision_time: 带时区的判断时间，默认当前UTC时间
    :return: 按日期升序排列的YYYY-MM-DD字符串列表
    """
    if count <= 0:
        raise ValueError("交易日数量必须大于0")
    if decision_time is None:
        decision_time = datetime.now(timezone.utc)
    if decision_time.tzinfo is None or decision_time.utcoffset() is None:
        raise ValueError("判断时间必须带时区")

    decision_time = decision_time.astimezone(timezone.utc)
    calendar = mcal.get_calendar(MARKET_CALENDAR_NAME)
    schedule = calendar.schedule(
        start_date=(
            decision_time - timedelta(days=CALENDAR_LOOKBACK_DAYS)
        ).date(),
        end_date=decision_time.date(),
    )
    cutoff = decision_time - timedelta(minutes=MARKET_CLOSE_DELAY_MINUTES)
    completed = schedule.loc[schedule["market_close"] <= cutoff]
    if len(completed) < count:
        raise ValueError("交易日历覆盖范围不足")

    return [
        value.strftime("%Y-%m-%d")
        for value in completed.index[-count:]
    ]