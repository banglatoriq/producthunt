"""
ai.py — প্রোডাক্ট রিসার্চ, ফ্রি LLM প্রোভাইডার দিয়ে।

কোনো পেইড API নেই। providers.py-এর মাধ্যমে Gemini, Groq, OpenRouter
বা লোকাল Ollama — যেকোনো ফ্রি প্রোভাইডারে চলে।

ছোট/ফ্রি মডেল বড় মডেলের মতো নিখুঁত JSON দেয় না। তাই এখানে:
  ১) json_object মোড চালু করা হয় (যেখানে সাপোর্ট আছে)
  ২) ব্যাকটিক/ভূমিকা কেটে JSON বের করা হয়
  ৩) ভাঙা JSON হলে মডেলকে দিয়েই মেরামত করানো হয়
  ৪) তাতেও না হলে temperature কমিয়ে রিট্রাই
"""

import json
import re
from typing import Optional

import providers

SYSTEM_PROMPT = """তুমি বাংলাদেশের ই-কমার্স ও ইম্পোর্ট বিজনেসের একজন অভিজ্ঞ প্রোডাক্ট রিসার্চ অ্যানালিস্ট।
তুমি ঢাকার মার্কেট, Daraz, ফেসবুক কমার্স, COD কালচার, কুরিয়ার বাস্তবতা এবং
চায়না (1688/Yiwu) সোর্সিং — সবই ভালো জানো।

তোমার কাজ: একটি প্রোডাক্ট সম্পর্কে বাস্তবসম্মত বিশ্লেষণ দেওয়া।

কঠোর নিয়ম:
- অতিরিক্ত আশাবাদী হবে না। ঝুঁকি ও দুর্বলতা স্পষ্ট করে বলবে।
- প্রোডাক্ট খারাপ মনে হলে সরাসরি কম স্কোর দেবে — সৌজন্য দেখাতে গিয়ে বাড়িয়ে বলবে না।
- সব টেক্সট বাংলায় লিখবে (চাইনিজ/ইংরেজি সার্চ কীওয়ার্ড ছাড়া)।
- তোমার কাছে লাইভ সেলস ডেটা নেই। সংখ্যা "অনুমান" হিসেবে দেবে এবং কীভাবে
  যাচাই করতে হবে সেটাও বলবে। বানানো পরিসংখ্যান দেবে না।
- উত্তর দেবে শুধুমাত্র একটি বৈধ JSON অবজেক্ট। কোনো ভূমিকা নয়, কোনো ব্যাখ্যা
  নয়, কোনো markdown ব্যাকটিক নয়। প্রথম অক্ষর { এবং শেষ অক্ষর }।

JSON স্কিমা (হুবহু এই কীগুলো):
{
  "product_summary": "১-২ বাক্যে প্রোডাক্টটি কী ও কী সমস্যার সমাধান করে",
  "score": 0-100 সংখ্যা,
  "score_reason": "স্কোরের যুক্তি, ২-৩ বাক্য",
  "recommendation": "যাও" | "সাবধানে যাও" | "বাদ দাও",
  "personas": [
    {
      "title": "সেগমেন্টের নাম",
      "age_range": "যেমন ২৫-৩৫",
      "gender": "পুরুষ | নারী | উভয়",
      "profession": "পেশা",
      "income_level": "মাসিক আয়ের আনুমানিক রেঞ্জ",
      "location": "ঢাকা শহর | বিভাগীয় শহর | মফস্বল",
      "why_they_buy": "কেনার আসল কারণ / আবেগ",
      "main_objection": "কেনার আগে যে আপত্তি আসবে",
      "where_to_reach": "কোন চ্যানেলে এদের পাওয়া যাবে",
      "priority": "প্রধান | দ্বিতীয়"
    }
  ],
  "positioning": {
    "hook": "এক লাইনের হুক",
    "angle": "কোন অ্যাঙ্গেলে বেচবে",
    "ad_copy": "সম্পূর্ণ ফেসবুক অ্যাড কপি, বাংলায়, ৪-৬ লাইন",
    "content_ideas": ["রিল/ভিডিও আইডিয়া"]
  },
  "pricing": {
    "suggested_range": "যেমন ১২০০-১৮০০ টাকা",
    "reasoning": "কেন এই রেঞ্জ",
    "price_sensitivity": "উচ্চ | মাঝারি | কম"
  },
  "competition": {
    "level": "কম | মাঝারি | বেশি",
    "who_sells_it": "বাংলাদেশে সাধারণত কারা বেচে",
    "differentiation": ["আলাদা হওয়ার উপায়"]
  },
  "risks": ["ঝুঁকি"],
  "logistics_flags": ["ব্যাটারি/ভঙ্গুর/ওয়ারেন্টি সংক্রান্ত সতর্কতা"],
  "sourcing_keywords": {
    "chinese": ["1688-এ সার্চের চাইনিজ কীওয়ার্ড"],
    "english": ["Alibaba-তে সার্চের ইংরেজি কীওয়ার্ড"]
  },
  "validation_steps": ["সত্যিই চলবে কিনা যাচাইয়ের কংক্রিট ধাপ"]
}"""

REQUIRED_KEYS = ["product_summary", "score", "recommendation", "personas"]


# --------------------------------------------------------------------------
# JSON পার্সিং — ছোট মডেলের এলোমেলো আউটপুট সামলানোর জন্য
# --------------------------------------------------------------------------

def _strip_fences(text: str) -> str:
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*", "", t)
    t = re.sub(r"\s*```$", "", t)
    return t.strip()


def _balanced_slice(text: str):
    """স্ট্রিং বাদ দিয়ে ব্রেস গুনে সম্পূর্ণ JSON অবজেক্টটা কেটে আনে।"""
    start = text.find("{")
    if start == -1:
        return None
    depth, in_str, esc = 0, False, False
    for i in range(start, len(text)):
        ch = text[i]
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def extract_json(text: str) -> dict:
    """কয়েক ধাপে JSON বের করার চেষ্টা।"""
    t = _strip_fences(text)
    try:
        return json.loads(t)
    except json.JSONDecodeError:
        pass

    sliced = _balanced_slice(t)
    if sliced:
        try:
            return json.loads(sliced)
        except json.JSONDecodeError:
            cleaned = re.sub(r",\s*([}\]])", r"\1", sliced)   # trailing comma
            return json.loads(cleaned)

    raise json.JSONDecodeError("JSON পাওয়া যায়নি", text[:200] or " ", 0)


def _repair_with_model(provider_key, api_key, model, broken: str) -> dict:
    """মডেলকে দিয়েই ভাঙা JSON ঠিক করানো।"""
    fixed, _ = providers.chat(
        provider_key,
        api_key,
        model,
        system=(
            "তুমি একটি JSON মেরামতকারী। ইনপুটে ভাঙা বা অসম্পূর্ণ JSON আছে। "
            "শুধু ঠিক করা বৈধ JSON অবজেক্ট আউটপুট দাও — আর কিছু নয়। "
            "কনটেন্ট বদলাবে না, শুধু সিনট্যাক্স ঠিক করবে।"
        ),
        user_content=broken[:12000],
        max_tokens=4000,
        json_mode=True,
        temperature=0.0,
    )
    return extract_json(fixed)


# --------------------------------------------------------------------------
# প্রম্পট
# --------------------------------------------------------------------------

def build_user_prompt(
    name: str,
    description: str = "",
    cny_price: Optional[float] = None,
    landed_cost: Optional[float] = None,
    target_price: Optional[float] = None,
    notes: str = "",
) -> str:
    parts = [f"প্রোডাক্ট: {name}"]
    if description:
        parts.append(f"বিবরণ: {description}")
    if cny_price:
        parts.append(f"চায়নায় দাম: ¥{cny_price}")
    if landed_cost:
        parts.append(f"ল্যান্ডেড কস্ট (বাংলাদেশে পৌঁছে): ৳{landed_cost:.0f}")
    if target_price:
        parts.append(f"পরিকল্পিত সেল প্রাইস: ৳{target_price:.0f}")
    if notes:
        parts.append(f"অতিরিক্ত তথ্য: {notes}")
    parts.append(
        "\nবাজার: বাংলাদেশ, অনলাইন (ফেসবুক + Daraz), COD ডেলিভারি। "
        "বিক্রেতা নতুন — বড় ক্যাপিটাল নেই, প্রথম লট ২০-৫০ পিস।\n"
        "উপরের স্কিমা অনুযায়ী শুধু JSON দাও।"
    )
    return "\n".join(parts)


def _build_content(prompt: str, image_bytes, media_type: str, vision_ok: bool):
    """ছবি থাকলে OpenAI-ফরম্যাটে multimodal content বানায়।"""
    if not image_bytes or not vision_ok:
        return prompt
    import base64

    b64 = base64.b64encode(image_bytes).decode("utf-8")
    return [
        {"type": "text", "text": prompt},
        {"type": "image_url", "image_url": {"url": f"data:{media_type};base64,{b64}"}},
    ]


# --------------------------------------------------------------------------
# মূল ফাংশন
# --------------------------------------------------------------------------

def research_product(
    provider_key: str,
    api_key: str,
    model: str,
    name: str,
    description: str = "",
    cny_price: Optional[float] = None,
    landed_cost: Optional[float] = None,
    target_price: Optional[float] = None,
    notes: str = "",
    image_bytes: Optional[bytes] = None,
    image_media_type: str = "image/jpeg",
    max_attempts: int = 3,
) -> dict:
    """
    প্রোডাক্ট অ্যানালাইসিস চালায় এবং ভ্যালিডেটেড dict রিটার্ন করে।
    ছোট মডেল ভুল করলে নিজে থেকেই মেরামত ও রিট্রাই করে।
    """
    p = providers.PROVIDERS[provider_key]
    prompt = build_user_prompt(name, description, cny_price, landed_cost, target_price, notes)
    content = _build_content(prompt, image_bytes, image_media_type, p.supports_vision)

    last_err = None
    for attempt in range(max_attempts):
        try:
            raw, usage = providers.chat(
                provider_key,
                api_key,
                model,
                system=SYSTEM_PROMPT,
                user_content=content,
                max_tokens=4000,
                json_mode=True,
                temperature=0.4 if attempt == 0 else 0.1,
            )
            try:
                data = extract_json(raw)
            except json.JSONDecodeError:
                data = _repair_with_model(provider_key, api_key, model, raw)

            missing = [k for k in REQUIRED_KEYS if k not in data]
            if missing:
                raise ValueError(f"স্কিমায় কী অনুপস্থিত: {', '.join(missing)}")

            data = _normalize(data)
            data["_provider"] = p.label
            data["_model"] = model
            data["_usage"] = usage
            data["_attempts"] = attempt + 1
            if image_bytes and not p.supports_vision:
                data["_warning"] = (
                    "এই প্রোভাইডারে ছবি পাঠানো যায়নি — শুধু টেক্সট দেখে বিশ্লেষণ হয়েছে।"
                )
            return data
        except Exception as e:
            last_err = e
            continue

    raise RuntimeError(
        f"{max_attempts} বার চেষ্টার পরেও ঠিক উত্তর পাওয়া যায়নি। শেষ সমস্যা: {last_err}\n\n"
        "টিপস: বড় মডেল বেছে নাও (Gemini Flash বা Llama 70B), অথবা বিবরণ ছোট করো।"
    )


def _normalize(d: dict) -> dict:
    """ছোট মডেল কখনো ভুল টাইপ দেয় — ঠিক করে নেওয়া।"""
    try:
        d["score"] = max(0, min(100, int(float(d.get("score", 0)))))
    except (TypeError, ValueError):
        d["score"] = 0

    if isinstance(d.get("personas"), dict):
        d["personas"] = [d["personas"]]
    if not isinstance(d.get("personas"), list):
        d["personas"] = []
    d["personas"] = [p for p in d["personas"] if isinstance(p, dict)]

    for k in ("risks", "logistics_flags", "validation_steps"):
        v = d.get(k)
        if isinstance(v, str):
            d[k] = [v]
        elif not isinstance(v, list):
            d[k] = []

    for k in ("positioning", "pricing", "competition", "sourcing_keywords"):
        if not isinstance(d.get(k), dict):
            d[k] = {}

    kw = d["sourcing_keywords"]
    for k in ("chinese", "english"):
        if isinstance(kw.get(k), str):
            kw[k] = [kw[k]]
        elif not isinstance(kw.get(k), list):
            kw[k] = []

    ideas = d["positioning"].get("content_ideas")
    if isinstance(ideas, str):
        d["positioning"]["content_ideas"] = [ideas]
    elif not isinstance(ideas, list):
        d["positioning"]["content_ideas"] = []

    diff = d["competition"].get("differentiation")
    if isinstance(diff, str):
        d["competition"]["differentiation"] = [diff]
    elif not isinstance(diff, list):
        d["competition"]["differentiation"] = []

    return d
