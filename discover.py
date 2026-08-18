"""
discover.py — প্রোডাক্ট আইডিয়া বের করা + যাচাই করার লিঙ্ক বানানো।

গুরুত্বপূর্ণ সীমাবদ্ধতা, শুরুতেই পরিষ্কার করে বলা দরকার:

    AI-এর কাছে বাংলাদেশের কোনো লাইভ সেলস ডেটা নেই। এই মডিউল যা দেয়
    তা হলো **হাইপোথিসিস** — "এটা হয়তো চলতে পারে"। প্রমাণ নয়।

তাই প্রতিটা আইডিয়ার সাথে সরাসরি যাচাইয়ের লিঙ্ক তৈরি হয় (Daraz, Facebook
Ad Library, 1688, Google Trends)। আসল সিদ্ধান্ত ওই লিঙ্কগুলোতে ক্লিক করে
নিজের চোখে দেখে নিতে হবে — AI-এর কথায় নয়।
"""

import json
from urllib.parse import quote_plus, quote

import providers
from ai import extract_json


IDEA_SYSTEM = """তুমি বাংলাদেশের ই-কমার্স ও চায়না-ইম্পোর্ট বিজনেসের অভিজ্ঞ প্রোডাক্ট স্কাউট।
ঢাকার মার্কেট, Daraz, ফেসবুক কমার্স, COD কালচার এবং 1688/Yiwu সোর্সিং ভালো জানো।

তোমার কাজ: দেওয়া শর্ত অনুযায়ী বাংলাদেশে অনলাইনে বেচার মতো প্রোডাক্ট আইডিয়া বের করা।

কঠোর নিয়ম:
- এগুলো **হাইপোথিসিস**, প্রমাণ নয়। তোমার কাছে লাইভ সেলস ডেটা নেই — এটা মনে রেখে
  লিখবে। "X হাজার পিস বিক্রি হয়েছে" জাতীয় বানানো পরিসংখ্যান কখনো দেবে না।
- আইডিয়াগুলো বৈচিত্র্যময় হবে — একই জিনিসের ভিন্ন ভিন্ন রূপ নয়।
- খুব সাধারণ, সবাই বেচে এমন জিনিস (সাধারণ মগ, সাধারণ পাওয়ার ব্যাংক) এড়িয়ে যাবে,
  যদি না ব্যবহারকারী স্পষ্টভাবে চায়।
- বাংলাদেশের আবহাওয়া, বিদ্যুৎ, ব্যবহারের অভ্যাস আর ক্রয়ক্ষমতা মাথায় রাখবে।
  শীতের ভারী গিয়ার বা -১০°C এর জিনিস দেবে না।
- ভঙ্গুর, ব্যাটারিওয়ালা, লিকুইড বা ওয়ারেন্টি লাগে এমন জিনিসে ঝুঁকি আছে —
  দিলে risk ফিল্ডে স্পষ্ট লিখবে।
- দাম ও ওজন **আনুমানিক রেঞ্জ** হিসেবে দেবে, নির্দিষ্ট সংখ্যা নয়।
- সব বাংলায়, শুধু search_en আর search_cn ছাড়া।
- উত্তর দেবে শুধুমাত্র একটি বৈধ JSON অবজেক্ট। কোনো ভূমিকা নয়, ব্যাকটিক নয়।
  প্রথম অক্ষর { এবং শেষ অক্ষর }।

JSON স্কিমা:
{
  "ideas": [
    {
      "name_bn": "প্রোডাক্টের নাম বাংলায়",
      "name_en": "English product name",
      "category": "ক্যাটাগরি",
      "why_bd": "কেন বাংলাদেশে চলতে পারে — ২ বাক্য, বাস্তব কারণ",
      "who_buys": "কে কিনবে — এক লাইনে",
      "est_cny_min": সংখ্যা,
      "est_cny_max": সংখ্যা,
      "est_weight_g": সংখ্যা,
      "competition_guess": "কম | মাঝারি | বেশি",
      "risk": "প্রধান ঝুঁকি — এক লাইনে, সৎভাবে",
      "search_bn": "Daraz/ফেসবুকে যে বাংলা বা ইংরেজি শব্দে খুঁজলে পাওয়া যাবে",
      "search_en": "English search term for Alibaba/AliExpress",
      "search_cn": "1688-এ সার্চের চাইনিজ কীওয়ার্ড"
    }
  ],
  "notes": "পুরো লিস্ট সম্পর্কে সতর্কতা বা পরামর্শ, ২-৩ বাক্য"
}"""


CATEGORIES = [
    "ঘরের গ্যাজেট ও ইউটিলিটি",
    "রান্নাঘর ও কিচেন টুল",
    "মোবাইল ও কম্পিউটার একসেসরিজ",
    "স্বাস্থ্য, ফিটনেস ও পার্সোনাল কেয়ার",
    "বাচ্চাদের জিনিস ও শিক্ষামূলক খেলনা",
    "গাড়ি ও বাইক একসেসরিজ",
    "অফিস ডেস্ক ও স্টেশনারি",
    "কর্পোরেট গিফট (বাল্ক)",
    "ফ্যাশন একসেসরিজ ও ব্যাগ",
    "পোষা প্রাণীর জিনিস",
    "বিয়ে ও উৎসবের আইটেম",
    "ছোট ব্যবসার টুল (দোকান, সেলুন, রেস্টুরেন্ট)",
]

SEASONS = [
    "সারা বছর",
    "গরমকাল",
    "বর্ষাকাল",
    "শীতকাল (হালকা)",
    "রমজান ও ঈদ",
    "নববর্ষ ও কর্পোরেট গিফট সিজন",
    "স্কুল-কলেজ ভর্তি মৌসুম",
    "বিয়ের মৌসুম",
]


def build_idea_prompt(
    categories,
    price_min: float,
    price_max: float,
    count: int = 10,
    season: str = "সারা বছর",
    audience: str = "",
    extra: str = "",
    exclude=None,
    avoid_battery: bool = True,
    max_weight_g: int = 500,
) -> str:
    lines = [
        f"আমাকে {count}টি প্রোডাক্ট আইডিয়া দাও।",
        "",
        f"ক্যাটাগরি: {', '.join(categories) if categories else 'যেকোনো'}",
        f"বাংলাদেশে সেল প্রাইস হতে হবে: ৳{price_min:.0f} – ৳{price_max:.0f}",
        f"মৌসুম/উপলক্ষ: {season}",
    ]
    if audience:
        lines.append(f"টার্গেট ক্রেতা: {audience}")

    lines += [
        "",
        "বাধ্যতামূলক শর্ত:",
        f"- প্রতি পিসের ওজন {max_weight_g} গ্রামের নিচে (এয়ার ফ্রেইটে আনা হবে)",
        "- চায়নায় দাম এমন হতে হবে যেন উপরের সেল প্রাইসে অন্তত ৩x মার্কআপ পাওয়া যায়",
        "- ভঙ্গুর নয়, লিকুইড নয়",
    ]
    if avoid_battery:
        lines.append("- ব্যাটারি বা রিচার্জেবল নয় (কাস্টমস ও ওয়ারেন্টি ঝামেলা)")

    lines += [
        "- বিক্রেতা নতুন, প্রথম লট মাত্র ২০-৫০ পিস — তাই কম ঝুঁকির জিনিস",
        "- ফেসবুক অ্যাড আর Daraz-এ বেচা হবে, COD ডেলিভারি",
    ]

    if exclude:
        lines += ["", f"এগুলো আগেই দেখা হয়েছে, বাদ দাও: {', '.join(exclude[:30])}"]
    if extra:
        lines += ["", f"অতিরিক্ত নির্দেশনা: {extra}"]

    lines += ["", "উপরের স্কিমা অনুযায়ী শুধু JSON দাও।"]
    return "\n".join(lines)


def generate_ideas(
    provider_key: str,
    api_key: str,
    model: str,
    categories,
    price_min: float,
    price_max: float,
    count: int = 10,
    season: str = "সারা বছর",
    audience: str = "",
    extra: str = "",
    exclude=None,
    avoid_battery: bool = True,
    max_weight_g: int = 500,
    max_attempts: int = 3,
) -> dict:
    prompt = build_idea_prompt(
        categories, price_min, price_max, count, season,
        audience, extra, exclude, avoid_battery, max_weight_g,
    )

    last_err = None
    for attempt in range(max_attempts):
        try:
            raw, usage = providers.chat(
                provider_key,
                api_key,
                model,
                system=IDEA_SYSTEM,
                user_content=prompt,
                max_tokens=4000,
                json_mode=True,
                # প্রথমবার একটু বেশি সৃজনশীল, রিট্রাইয়ে বেশি অনুগত
                temperature=0.8 if attempt == 0 else 0.3,
            )
            data = extract_json(raw)
            ideas = data.get("ideas")
            if isinstance(ideas, dict):
                ideas = [ideas]
            if not isinstance(ideas, list) or not ideas:
                raise ValueError("কোনো আইডিয়া পাওয়া যায়নি")

            data["ideas"] = [_clean_idea(i) for i in ideas if isinstance(i, dict)]
            data["_usage"] = usage
            data["_model"] = model
            data["_attempts"] = attempt + 1
            return data
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(
        f"{max_attempts} বার চেষ্টার পরেও আইডিয়া পাওয়া যায়নি। শেষ সমস্যা: {last_err}\n\n"
        "টিপস: বড় মডেল বাছো, বা আইডিয়ার সংখ্যা কমাও।"
    )


def _num(v, default=0.0):
    try:
        return float(str(v).replace(",", "").strip())
    except (TypeError, ValueError):
        return default


def _clean_idea(d: dict) -> dict:
    """ছোট মডেলের এলোমেলো টাইপ ঠিক করা।"""
    out = {k: (v if isinstance(v, str) else v) for k, v in d.items()}
    out["name_bn"] = str(d.get("name_bn") or d.get("name_en") or "নামহীন")
    out["name_en"] = str(d.get("name_en") or "")
    out["est_cny_min"] = _num(d.get("est_cny_min"))
    out["est_cny_max"] = _num(d.get("est_cny_max"), out["est_cny_min"])
    out["est_weight_g"] = _num(d.get("est_weight_g"), 300)
    for k in ("category", "why_bd", "who_buys", "competition_guess", "risk",
              "search_bn", "search_en", "search_cn"):
        v = d.get(k)
        out[k] = v if isinstance(v, str) else ("" if v is None else str(v))
    if not out["search_bn"]:
        out["search_bn"] = out["name_en"] or out["name_bn"]
    if not out["search_en"]:
        out["search_en"] = out["name_en"] or out["name_bn"]
    return out


# --------------------------------------------------------------------------
# যাচাইয়ের লিঙ্ক — এখানেই আসল প্রমাণ পাওয়া যাবে
# --------------------------------------------------------------------------

def verify_links(idea: dict) -> dict:
    """
    প্রতিটা আইডিয়ার জন্য সরাসরি সার্চ লিঙ্ক।
    AI যা বলেছে তা সত্যি কিনা — এই লিঙ্কগুলোই বলে দেবে।
    """
    bn = idea.get("search_bn") or idea.get("name_en") or idea.get("name_bn", "")
    en = idea.get("search_en") or bn
    cn = idea.get("search_cn") or en

    return {
        # বাংলাদেশে কেউ বেচছে কিনা, কত দামে, কত রিভিউ
        "Daraz BD": f"https://www.daraz.com.bd/catalog/?q={quote_plus(bn)}",
        # কোন অ্যাড কতদিন ধরে চলছে — সবচেয়ে শক্তিশালী সিগন্যাল
        "FB Ad Library": (
            "https://www.facebook.com/ads/library/?active_status=all&ad_type=all"
            f"&country=BD&q={quote_plus(bn)}&search_type=keyword_unordered"
        ),
        # চায়নায় আসল হোলসেল দাম
        "1688": f"https://s.1688.com/selloffer/offer_search.htm?keywords={quote(cn)}",
        # ইংরেজিতে সাপ্লায়ার ও MOQ
        "Alibaba": f"https://www.alibaba.com/trade/search?SearchText={quote_plus(en)}",
        # ১ পিস স্যাম্পল আনার জন্য
        "AliExpress": f"https://www.aliexpress.com/wholesale?SearchText={quote_plus(en)}",
        # বাংলাদেশে সার্চ ট্রেন্ড বাড়ছে না কমছে
        "Google Trends": f"https://trends.google.com/trends/explore?geo=BD&q={quote_plus(en)}",
        # পাশের বাজারে চলছে কিনা
        "Meesho (IN)": f"https://www.meesho.com/search?q={quote_plus(en)}",
    }
