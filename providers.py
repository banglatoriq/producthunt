"""
providers.py — একাধিক ফ্রি LLM প্রোভাইডার সাপোর্ট।

সবগুলোই OpenAI-কম্প্যাটিবল এন্ডপয়েন্ট দেয়, তাই একটাই `openai` ক্লায়েন্ট
দিয়ে সব চালানো যায় — শুধু base_url আর model বদলায়।

গুরুত্বপূর্ণ: ফ্রি প্রোভাইডাররা মাঝে মাঝে নোটিশ ছাড়াই মডেল মুছে দেয়।
তাই এখানে মডেলের নাম হার্ডকোড না করে রানটাইমে /models এন্ডপয়েন্ট থেকে
লাইভ লিস্ট আনা হয়। API ফেল করলে নিচের fallback লিস্ট ব্যবহার হয় —
সেগুলো শুধু ইঙ্গিত, গ্যারান্টি নয়।
"""

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Provider:
    key: str
    label: str
    base_url: str
    signup_url: str
    needs_key: bool = True
    key_prefix: str = ""
    supports_vision: bool = True
    supports_json_mode: bool = True
    # লাইভ লিস্ট আনতে না পারলে এগুলো দেখানো হবে
    fallback_models: List[str] = field(default_factory=list)
    # লাইভ লিস্টে এই টেক্সট থাকলে সেটাকে অগ্রাধিকার দেওয়া হবে
    prefer: List[str] = field(default_factory=list)
    # লাইভ লিস্ট ফিল্টার করার শর্ত (OpenRouter-এ ফ্রি মডেল বাছতে)
    only_containing: Optional[str] = None
    note: str = ""


PROVIDERS = {
    "gemini": Provider(
        key="gemini",
        label="Google Gemini  (ফ্রি টিয়ার · সুপারিশকৃত)",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
        signup_url="https://aistudio.google.com/apikey",
        key_prefix="AIza",
        supports_vision=True,
        fallback_models=[
            "gemini-2.5-flash",
            "gemini-2.5-flash-lite",
            "gemini-2.0-flash",
        ],
        prefer=["flash"],
        note=(
            "Flash ও Flash-Lite মডেলগুলো ফ্রি টিয়ারে আছে; Pro মডেল ২০২৬ সালের "
            "এপ্রিল থেকে পেইড। ক্রেডিট কার্ড লাগে না। ছবি আপলোড কাজ করে। "
            "নোট: ফ্রি টিয়ারের ডেটা Google মডেল ট্রেনিংয়ে ব্যবহার করতে পারে — "
            "গোপন তথ্য পাঠিও না।"
        ),
    ),
    "groq": Provider(
        key="groq",
        label="Groq  (ফ্রি · সবচেয়ে দ্রুত)",
        base_url="https://api.groq.com/openai/v1",
        signup_url="https://console.groq.com/keys",
        key_prefix="gsk_",
        supports_vision=False,
        fallback_models=[
            "llama-3.3-70b-versatile",
            "llama-3.1-8b-instant",
            "openai/gpt-oss-120b",
            "qwen/qwen3-32b",
        ],
        prefer=["70b", "gpt-oss-120b", "versatile"],
        note=(
            "খুব দ্রুত, কার্ড লাগে না। তবে মডেল ক্যাটালগ প্রায়ই বদলায় — "
            "নিচের 'মডেল লিস্ট রিফ্রেশ' চেপে লাইভ লিস্ট নাও। বেশিরভাগ টেক্সট "
            "মডেলে ছবি কাজ করবে না।"
        ),
    ),
    "openrouter": Provider(
        key="openrouter",
        label="OpenRouter  (:free মডেল)",
        base_url="https://openrouter.ai/api/v1",
        signup_url="https://openrouter.ai/keys",
        key_prefix="sk-or-",
        supports_vision=True,
        only_containing=":free",
        fallback_models=[],
        note=(
            "একটা key দিয়ে অনেক প্রোভাইডারের মডেল। শুধু নামের শেষে ':free' "
            "থাকা মডেলগুলো দেখানো হচ্ছে। ফ্রি মডেলে রেট লিমিট কড়া হতে পারে।"
        ),
    ),
    "ollama": Provider(
        key="ollama",
        label="Ollama  (নিজের পিসিতে · সম্পূর্ণ ফ্রি, ইন্টারনেট লাগে না)",
        base_url="http://localhost:11434/v1",
        signup_url="https://ollama.com/download",
        needs_key=False,
        supports_vision=False,
        supports_json_mode=True,
        fallback_models=["llama3.1:8b", "qwen2.5:7b", "gemma3:4b"],
        prefer=["qwen", "llama"],
        note=(
            "কোনো API key লাগে না, কোনো খরচ নেই, ডেটা তোমার পিসি ছাড়ে না। "
            "আগে Ollama ইনস্টল করে `ollama pull qwen2.5:7b` চালাও। "
            "ছোট মডেল বাংলায় দুর্বল হতে পারে — ৭B বা তার বড় নাও।"
        ),
    ),
}

DEFAULT_PROVIDER = "gemini"


def get_client(provider_key: str, api_key: str = ""):
    """OpenAI-কম্প্যাটিবল ক্লায়েন্ট বানায়।"""
    from openai import OpenAI

    p = PROVIDERS[provider_key]
    return OpenAI(
        api_key=api_key or "not-needed",
        base_url=p.base_url,
        timeout=120.0,
        max_retries=2,
    )


def list_models(provider_key: str, api_key: str = "") -> tuple:
    """
    প্রোভাইডার থেকে লাইভ মডেল লিস্ট আনে।
    রিটার্ন: (মডেল লিস্ট, সোর্স) — সোর্স = "live" অথবা "fallback"
    """
    p = PROVIDERS[provider_key]
    try:
        client = get_client(provider_key, api_key)
        raw = [m.id for m in client.models.list().data]

        if p.only_containing:
            raw = [m for m in raw if p.only_containing in m]

        # কাজে লাগে না এমনগুলো বাদ
        skip = ("whisper", "embed", "guard", "tts", "rerank", "moderation", "image")
        raw = [m for m in raw if not any(s in m.lower() for s in skip)]

        if not raw:
            return (p.fallback_models, "fallback")

        # পছন্দের মডেল আগে
        def rank(name: str) -> int:
            low = name.lower()
            for i, pref in enumerate(p.prefer):
                if pref in low:
                    return i
            return len(p.prefer) + 1

        raw.sort(key=lambda m: (rank(m), m))
        return (raw, "live")
    except Exception:
        return (p.fallback_models, "fallback")


def chat(
    provider_key: str,
    api_key: str,
    model: str,
    system: str,
    user_content,
    max_tokens: int = 4000,
    json_mode: bool = True,
    temperature: float = 0.4,
) -> tuple:
    """
    একটা কল করে টেক্সট রিটার্ন করে।
    রিটার্ন: (টেক্সট, usage dict)
    """
    p = PROVIDERS[provider_key]
    client = get_client(provider_key, api_key)

    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user_content},
        ],
    }
    if json_mode and p.supports_json_mode:
        kwargs["response_format"] = {"type": "json_object"}

    try:
        resp = client.chat.completions.create(**kwargs)
    except Exception as e:
        msg = str(e)
        # কিছু মডেল json_object বা max_tokens সাপোর্ট করে না — ছাড়া আবার চেষ্টা
        retry = False
        if "response_format" in msg or "json_object" in msg:
            kwargs.pop("response_format", None)
            retry = True
        if "max_tokens" in msg and "max_completion_tokens" in msg:
            kwargs["max_completion_tokens"] = kwargs.pop("max_tokens")
            retry = True
        if not retry:
            raise
        resp = client.chat.completions.create(**kwargs)

    text = resp.choices[0].message.content or ""
    usage = {}
    if getattr(resp, "usage", None):
        usage = {
            "input_tokens": getattr(resp.usage, "prompt_tokens", 0),
            "output_tokens": getattr(resp.usage, "completion_tokens", 0),
        }
    return text, usage


def test_connection(provider_key: str, api_key: str, model: str) -> tuple:
    """কানেকশন ও key ঠিক আছে কিনা দ্রুত চেক।"""
    try:
        text, _ = chat(
            provider_key,
            api_key,
            model,
            system="Reply with the single word: ok",
            user_content="ping",
            max_tokens=20,
            json_mode=False,
        )
        return True, (text or "").strip()[:40] or "ঠিক আছে"
    except Exception as e:
        return False, str(e)[:300]
