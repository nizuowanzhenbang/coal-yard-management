"""入煤综合评分。

100 分制。基础分由化验数据计算（热值占大头，灰分硫分水分扣分），
然后按库龄衰减（自燃风险 + 热值下降）。

公式：
  base = calorific_score - ash_penalty - sulfur_penalty - moisture_penalty
  aging_decay = aging_days 折扣（线性，到 60 天扣 20 分封顶）
  current = clamp(base - aging_decay, 0, 100)
"""
from typing import Optional, Tuple

from app.config import settings


def _calorific_score(cv: Optional[float]) -> float:
    """热值 4000~6000 kcal/kg → 60~95 分线性映射；缺失返回 70"""
    if cv is None:
        return 70.0
    if cv <= 4000:
        return 60.0
    if cv >= 6000:
        return 95.0
    return round(60 + (cv - 4000) / 2000 * 35, 1)


def _ash_penalty(ash: Optional[float]) -> float:
    """灰分 >20% 开始扣，>30% 封顶 -10 分"""
    if ash is None or ash <= 20:
        return 0.0
    return round(min((ash - 20) * 1.0, 10.0), 1)


def _sulfur_penalty(s: Optional[float]) -> float:
    """硫分 >0.6% 开始扣，>1.5% 封顶 -8 分"""
    if s is None or s <= 0.6:
        return 0.0
    return round(min((s - 0.6) * 9, 8.0), 1)


def _moisture_penalty(m: Optional[float]) -> float:
    """水分 >12% 开始扣，>20% 封顶 -5 分"""
    if m is None or m <= 12:
        return 0.0
    return round(min((m - 12) * 0.7, 5.0), 1)


def _aging_decay(aging_days: int) -> float:
    """库龄 ≤15 天不扣；15~30 线性扣 0~5；30~60 线性扣 5~20；>60 封顶 20"""
    if aging_days <= settings.AGING_WARN_DAYS:
        return 0.0
    if aging_days <= settings.AGING_DANGER_DAYS:
        ratio = (aging_days - settings.AGING_WARN_DAYS) / (settings.AGING_DANGER_DAYS - settings.AGING_WARN_DAYS)
        return round(ratio * 5, 1)
    if aging_days <= 60:
        ratio = (aging_days - settings.AGING_DANGER_DAYS) / (60 - settings.AGING_DANGER_DAYS)
        return round(5 + ratio * 15, 1)
    return 20.0


def calc_score(
    calorific_value: Optional[float],
    ash: Optional[float],
    sulfur: Optional[float],
    moisture: Optional[float],
    aging_days: int,
) -> Tuple[float, dict]:
    """返回 (current_score, breakdown)"""
    base_calorific = _calorific_score(calorific_value)
    ash_p = _ash_penalty(ash)
    s_p = _sulfur_penalty(sulfur)
    m_p = _moisture_penalty(moisture)
    base = round(base_calorific - ash_p - s_p - m_p, 1)
    decay = _aging_decay(aging_days)
    current = max(0.0, min(100.0, round(base - decay, 1)))
    return current, {
        "calorific_score": base_calorific,
        "ash_penalty": -ash_p,
        "sulfur_penalty": -s_p,
        "moisture_penalty": -m_p,
        "base_score": base,
        "aging_decay": -decay,
        "current_score": current,
    }


def blending_priority(current_score: float, aging_days: int) -> float:
    """配煤优先级：综合评分 + 库龄权重。
    高分优先，但同分时长龄优先（避免囤积老批次自燃 + 热值衰减）。
    返回 priority，越大越优先用。
    """
    aging_weight = min(aging_days * 0.4, 30)  # 库龄越长权重越大，封顶 30
    return round(current_score + aging_weight, 1)
