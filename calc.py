"""
calc.py — ল্যান্ডেড কস্ট ও প্রফিট ক্যালকুলেশন ইঞ্জিন।

সব হিসাব বাংলাদেশি টাকায় (BDT)। কোনো Streamlit ইম্পোর্ট নেই — তাই এই
ফাইলটা আলাদাভাবে টেস্ট বা অন্য স্ক্রিপ্টে রিইউজ করা যায়।
"""

from dataclasses import dataclass, asdict, field
from typing import Optional


# --------------------------------------------------------------------------
# ইনপুট মডেল
# --------------------------------------------------------------------------

@dataclass
class CostInput:
    """একটি প্রোডাক্টের সব খরচের ইনপুট।"""

    # --- সোর্সিং ---
    cny_price: float = 30.0          # 1688/Taobao-তে প্রতি পিসের দাম (¥)
    cny_to_bdt: float = 17.0         # ¥1 = কত টাকা
    unit_weight_g: float = 300.0     # প্রতি পিসের ওজন (গ্রাম), প্যাকিং সহ
    freight_per_kg: float = 900.0    # এজেন্ট/ফরওয়ার্ডারের রেট (টাকা/কেজি)
    duty_pct: float = 30.0           # কাস্টমস ডিউটি + ক্লিয়ারেন্স (%)
    agent_fee_pct: float = 5.0       # বাইং এজেন্ট কমিশন (%)
    local_packaging: float = 25.0    # দেশে রিপ্যাক/বক্স/স্টিকার (টাকা/পিস)

    # --- বিক্রয় ---
    sell_price: float = 2500.0       # কাস্টমারের কাছে দাম (টাকা)
    order_qty: int = 50              # এই লটে কত পিস আনছ

    # --- অর্ডারপ্রতি চলতি খরচ ---
    cac: float = 350.0               # ফেসবুক অ্যাড খরচ / অর্ডার
    delivery_fwd: float = 100.0      # কুরিয়ার ফরোয়ার্ড চার্জ
    delivery_return: float = 60.0    # রিটার্ন হলে ফেরত আনার চার্জ
    gateway_pct: float = 1.0         # COD/গেটওয়ে সার্ভিস চার্জ (%)

    # --- ঝুঁকি ---
    return_rate_pct: float = 25.0    # COD রিটার্ন হার (%)
    damage_pct: float = 5.0          # রিটার্ন আসা মালের যত অংশ নষ্ট হয় (%)


# --------------------------------------------------------------------------
# আউটপুট মডেল
# --------------------------------------------------------------------------

@dataclass
class CostResult:
    # ল্যান্ডেড কস্ট ব্রেকডাউন (প্রতি পিস)
    product_bdt: float = 0.0
    freight_bdt: float = 0.0
    duty_bdt: float = 0.0
    agent_bdt: float = 0.0
    packaging_bdt: float = 0.0
    landed_unit: float = 0.0

    # লট লেভেল
    total_investment: float = 0.0

    # ১০০ অর্ডারের সিমুলেশন
    delivered: float = 0.0
    returned: float = 0.0
    revenue_100: float = 0.0
    ad_cost_100: float = 0.0
    courier_cost_100: float = 0.0
    gateway_cost_100: float = 0.0
    cogs_100: float = 0.0
    damage_cost_100: float = 0.0
    net_100: float = 0.0

    # সূচক
    net_per_delivered: float = 0.0
    net_margin_pct: float = 0.0
    markup_x: float = 0.0
    roi_pct: float = 0.0
    breakeven_price: float = 0.0
    lot_profit: float = 0.0
    verdict: str = ""
    verdict_level: str = "bad"       # good | ok | bad
    warnings: list = field(default_factory=list)


# --------------------------------------------------------------------------
# ইঞ্জিন
# --------------------------------------------------------------------------

def landed_cost(ci: CostInput) -> dict:
    """প্রতি পিসের ল্যান্ডেড কস্ট ও তার ব্রেকডাউন।"""
    product_bdt = ci.cny_price * ci.cny_to_bdt
    freight_bdt = (ci.unit_weight_g / 1000.0) * ci.freight_per_kg
    # ডিউটি সাধারণত পণ্যমূল্য + ফ্রেইটের উপর বসে (CIF ভিত্তিক)
    duty_bdt = (product_bdt + freight_bdt) * (ci.duty_pct / 100.0)
    agent_bdt = product_bdt * (ci.agent_fee_pct / 100.0)
    packaging = ci.local_packaging

    total = product_bdt + freight_bdt + duty_bdt + agent_bdt + packaging
    return {
        "product_bdt": product_bdt,
        "freight_bdt": freight_bdt,
        "duty_bdt": duty_bdt,
        "agent_bdt": agent_bdt,
        "packaging_bdt": packaging,
        "landed_unit": total,
    }


def compute(ci: CostInput) -> CostResult:
    """
    ১০০টি অর্ডারের ভিত্তিতে পুরো হিসাব।

    যুক্তি: অ্যাড খরচ ও ফরোয়ার্ড কুরিয়ার সব অর্ডারেই লাগে — ডেলিভারি হোক
    বা রিটার্ন হোক। রিটার্ন মাল ফেরত আসে, তাই তার COGS ধরা হয় না, শুধু
    যেটুকু নষ্ট হয় সেটুকু লস।
    """
    r = CostResult()
    lc = landed_cost(ci)
    for k, v in lc.items():
        setattr(r, k, v)

    r.total_investment = r.landed_unit * ci.order_qty

    n = 100.0
    ret_rate = ci.return_rate_pct / 100.0
    r.delivered = n * (1 - ret_rate)
    r.returned = n * ret_rate

    r.revenue_100 = r.delivered * ci.sell_price
    r.ad_cost_100 = n * ci.cac
    r.courier_cost_100 = (n * ci.delivery_fwd) + (r.returned * ci.delivery_return)
    r.gateway_cost_100 = r.revenue_100 * (ci.gateway_pct / 100.0)
    r.cogs_100 = r.delivered * r.landed_unit
    r.damage_cost_100 = r.returned * (ci.damage_pct / 100.0) * r.landed_unit

    r.net_100 = (
        r.revenue_100
        - r.ad_cost_100
        - r.courier_cost_100
        - r.gateway_cost_100
        - r.cogs_100
        - r.damage_cost_100
    )

    r.net_per_delivered = r.net_100 / r.delivered if r.delivered else 0.0
    r.net_margin_pct = (r.net_100 / r.revenue_100 * 100.0) if r.revenue_100 else 0.0
    r.markup_x = (ci.sell_price / r.landed_unit) if r.landed_unit else 0.0
    r.roi_pct = (r.net_100 / r.cogs_100 * 100.0) if r.cogs_100 else 0.0
    r.breakeven_price = min_viable_price(ci, target_margin_pct=0.0)
    r.lot_profit = r.net_per_delivered * ci.order_qty * (1 - ret_rate) if ci.order_qty else 0.0

    r.verdict, r.verdict_level = _verdict(r)
    r.warnings = _warnings(ci, r)
    return r


def min_viable_price(ci: CostInput, target_margin_pct: float = 20.0) -> float:
    """
    টার্গেট নেট মার্জিন পেতে হলে সর্বনিম্ন সেল প্রাইস কত হতে হবে।

    প্রতি ১০০ অর্ডারে:
      revenue = delivered * P
      net = revenue*(1 - g) - ad - courier - cogs - damage
      net = revenue * m   (m = টার্গেট মার্জিন)
    => delivered*P*(1 - g - m) = ad + courier + cogs + damage
    """
    lc = landed_cost(ci)["landed_unit"]
    n = 100.0
    ret = ci.return_rate_pct / 100.0
    delivered = n * (1 - ret)
    returned = n * ret

    fixed = (
        n * ci.cac
        + (n * ci.delivery_fwd + returned * ci.delivery_return)
        + delivered * lc
        + returned * (ci.damage_pct / 100.0) * lc
    )
    g = ci.gateway_pct / 100.0
    m = target_margin_pct / 100.0
    denom = delivered * (1 - g - m)
    if denom <= 0:
        return float("inf")
    return fixed / denom


def _verdict(r: CostResult):
    if r.net_margin_pct >= 25 and r.markup_x >= 3:
        return "চমৎকার — এই প্রোডাক্টে স্কেল করা যায়", "good"
    if r.net_margin_pct >= 15:
        return "চলার মতো — কিন্তু CAC একটু বাড়লেই চাপে পড়বে", "ok"
    if r.net_margin_pct > 0:
        return "ঝুঁকিপূর্ণ — মার্জিন খুব পাতলা, একটা খারাপ সপ্তাহেই লস", "bad"
    return "লস — এই দামে বেচলে টাকা হারাবে", "bad"


def _warnings(ci: CostInput, r: CostResult) -> list:
    w = []
    if r.markup_x < 2.5:
        w.append(
            f"মার্কআপ মাত্র {r.markup_x:.1f}x — অনলাইন B2C-তে কমপক্ষে ৩x দরকার, "
            "কারণ অ্যাড খরচ সময়ের সাথে বাড়ে।"
        )
    if ci.unit_weight_g > 500:
        w.append(
            f"ওজন {ci.unit_weight_g:.0f} গ্রাম — এয়ার ফ্রেইটে ভারী পণ্য মার্জিন খেয়ে ফেলে। "
            "৫০০ গ্রামের নিচে খোঁজো।"
        )
    if r.freight_bdt > r.product_bdt:
        w.append("ফ্রেইট খরচ পণ্যের দামের চেয়ে বেশি — এই প্রোডাক্ট এয়ারে আনার উপযুক্ত নয়।")
    if ci.return_rate_pct < 15:
        w.append(
            "রিটার্ন রেট ১৫%-এর নিচে ধরেছ — বাংলাদেশে COD-তে বাস্তব হার সাধারণত "
            "২০–৩০%। বেশি ধরে হিসাব করাই নিরাপদ।"
        )
    if ci.cac < 200:
        w.append("CAC ২০০ টাকার নিচে ধরেছ — প্রথম দিকে বাস্তবে ৩০০–৬০০ হয়। কনজারভেটিভ থাকো।")
    if ci.order_qty > 100:
        w.append(
            f"প্রথম লটে {ci.order_qty} পিস — প্রোডাক্ট প্রুভ হওয়ার আগে "
            "২০–৫০ পিসের বেশি নয়।"
        )
    if r.total_investment > 100000:
        w.append(
            f"এক লটে বিনিয়োগ ৳{r.total_investment:,.0f} — টেস্ট ফেজে এত টাকা আটকানো ঝুঁকিপূর্ণ।"
        )
    return w


def to_dict(ci: CostInput, r: CostResult) -> dict:
    d = {}
    d.update({f"in_{k}": v for k, v in asdict(ci).items()})
    d.update({f"out_{k}": v for k, v in asdict(r).items() if k != "warnings"})
    return d
