#!/usr/bin/env python3
"""Prepare non-overlapping themed seed manifests for the 22 Phase 2B chat batches."""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
LEXICON_PATH = BASE_DIR / "data" / "processed" / "lexicon.jsonl"
TEXTS_PATH = BASE_DIR / "data" / "processed" / "dialect_texts.jsonl"
REVIEW_30_PATH = BASE_DIR / "data" / "chat" / "batches" / "sample_review_30.jsonl"
DEFAULT_OUT = BASE_DIR / "data" / "chat_v4" / "batch_seeds.json"

BANNED_CHARS_RE = re.compile(r"[ŋñḳḵḫėāēīōūȫǖĢĠġ╧└─┌╒Ω┬║╦♠£]")
DRIFT_TERM_RE = re.compile(r"\b(aciycak|oturiyin|gari|nörüyon|haçan|uşağum)\b", re.IGNORECASE)
KRŞ_ONLY_RE = re.compile(r"^\(?\s*krş\.?[^a-zçğıöşü]*$", re.IGNORECASE)


def clean_meaning(raw: str) -> str:
    text = re.sub(r"\s+", " ", raw).strip()
    text = re.sub(r"\s*\(krş\.[^)]*\)\s*", " ", text, flags=re.IGNORECASE).strip()
    return re.sub(r"\s+", " ", text).strip(" ;,-")


def load_clean_lexicon() -> dict[str, list[dict[str, str]]]:
    by_region: dict[str, list[dict[str, str]]] = defaultdict(list)
    seen_terms: set[str] = set()
    for line in LEXICON_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        term = re.sub(r"\s+", " ", obj.get("normalized_term") or obj.get("term") or "").strip()
        meaning = clean_meaning(obj.get("meaning", ""))
        region = obj.get("region", "general")
        if not term or not meaning or len(term) < 2 or len(meaning) < 4:
            continue
        if BANNED_CHARS_RE.search(term) or BANNED_CHARS_RE.search(meaning):
            continue
        if DRIFT_TERM_RE.search(term) or DRIFT_TERM_RE.search(meaning):
            continue
        if KRŞ_ONLY_RE.match(meaning):
            continue
        key = term.lower().rstrip("-")
        if key in seen_terms:
            continue
        seen_terms.add(key)
        by_region[region].append({"term": term, "meaning": meaning, "region": region})
    return by_region


def load_clean_texts() -> dict[str, list[str]]:
    by_region: dict[str, list[str]] = defaultdict(list)
    for line in TEXTS_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        text = re.sub(r"\s+", " ", obj.get("normalized_text", "")).strip()
        region = obj.get("region", "general")
        if len(text) < 25 or BANNED_CHARS_RE.search(text) or DRIFT_TERM_RE.search(text):
            continue
        by_region[region].append(text)
    return by_region


def load_avoid_prompts() -> dict[str, list[str]]:
    by_cat: dict[str, list[str]] = defaultdict(list)
    if not REVIEW_30_PATH.exists():
        return by_cat
    for line in REVIEW_30_PATH.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        obj = json.loads(line)
        cat = obj.get("_category", "uncategorized")
        msgs = obj.get("messages", [])
        if len(msgs) >= 2:
            by_cat[cat].append(msgs[1]["content"].strip())
    return by_cat


MERKEZ_THEMATIC_VOCAB: list[dict[str, str]] = [
    {"term": "boon", "meaning": "bugün"},
    {"term": "onüçün", "meaning": "onun için, o yüzden"},
    {"term": "bahele", "meaning": "bak hele, baksana"},
    {"term": "bahım", "meaning": "bakayım / bakalım"},
    {"term": "eyilik / eyicene", "meaning": "iyilik / iyice"},
    {"term": "accıg / azcık", "meaning": "biraz, azıcık"},
    {"term": "buadar / oadar", "meaning": "bu kadar / o kadar"},
    {"term": "burdiyem / evdiyem", "meaning": "buradayım / evdeyim"},
    {"term": "nootin / neydin / notucuk", "meaning": "ne yapıyorsun / ne yapacağız"},
    {"term": "yamır / hamır / çamır", "meaning": "yağmur / hamur / çamur"},
    {"term": "horanta", "meaning": "ev halkı, aile"},
    {"term": "hanek", "meaning": "sohbet, muhabbet"},
    {"term": "şor", "meaning": "söz, laf"},
    {"term": "salık", "meaning": "haber, bilgi"},
    {"term": "tavatır", "meaning": "çok güzel, harika, olağanüstü"},
    {"term": "yoheri!", "meaning": "gerçekten mi, hayret!"},
    {"term": "bıldır", "meaning": "geçen yıl"},
    {"term": "bayak / debiyak", "meaning": "az önce, demin"},
    {"term": "kelli", "meaning": "bundan sonra, artık"},
    {"term": "diyal / değel", "meaning": "değil"},
    {"term": "yosa", "meaning": "yoksa"},
    {"term": "vahıt", "meaning": "vakit, zaman"},
    {"term": "şindi", "meaning": "şimdi"},
    {"term": "sona / soora", "meaning": "sonra"},
    {"term": "barabar", "meaning": "beraber"},
    {"term": "hemi de", "meaning": "hem de"},
    {"term": "melmeket", "meaning": "memleket"},
    {"term": "gomşu", "meaning": "komşu"},
    {"term": "gardaş / edem / ede", "meaning": "kardeş / ağabey / dostum"},
    {"term": "gadan alım", "meaning": "derdini belanı alayım (sevgi sözü)"},
    {"term": "dinelmek", "meaning": "ayakta durmak, dikilmek"},
    {"term": "denneşmek", "meaning": "dinlenmek, soluklanmak"},
    {"term": "böğsümek", "meaning": "küsmek, darılmak"},
    {"term": "nizah", "meaning": "tartışma, çekişme"},
    {"term": "ığdırık", "meaning": "aralık, tam kapanmamış"},
    {"term": "cıncık", "meaning": "cam; pırıl pırıl temiz"},
    {"term": "çomça", "meaning": "kepçe"},
    {"term": "süllüm", "meaning": "merdiven"},
    {"term": "püsük", "meaning": "kedi"},
    {"term": "saho", "meaning": "ceket"},
    {"term": "sındı", "meaning": "makas"},
    {"term": "ağnanmak", "meaning": "toza toprağa bulanmak, yuvarlanmak"},
    {"term": "çimmek", "meaning": "yüzmek, yıkanmak"},
    {"term": "malamat etmek", "meaning": "rezil etmek, mahcup etmek"},
    {"term": "adeleşmek", "meaning": "inatlaşmak"},
    {"term": "mırhız", "meaning": "cimri, eli sıkı"},
    {"term": "lavlavı", "meaning": "çok ve boş konuşan"},
    {"term": "gartaşık", "meaning": "kartlaşmış, taze olmayan sebze"},
    {"term": "bon", "meaning": "bunaltıcı, boğucu"},
    {"term": "kıyak", "meaning": "hoş, güzel, harika"},
    {"term": "peh / tama / ola / hele", "meaning": "hayranlık / tamam / acaba / haydi"},
    {"term": "samırsak / eşgili / madanız", "meaning": "sarımsak / ekşili / maydanoz"},
    {"term": "bibi / emmi / aba / dezze", "meaning": "hala / amca / abla / teyze"},
    {"term": "yekinmek", "meaning": "hamle etmek, kalkışmak"},
    {"term": "zırpadak", "meaning": "aniden, birdenbire"},
]


BATCH_SPECS = [
    # gunluk_sohbet (5)
    ("batch_01_gunluk_halhatir_hava.jsonl", "gunluk_sohbet",
     "Greetings, check-ins, seasons, weather (summer heat, rain, snow, Ahır Dağı breeze, spring), morning/evening chats, tea/coffee breaks."),
    ("batch_02_gunluk_aile_komsu.jsonl", "gunluk_sohbet",
     "Family (horanta), elders, kids, neighbors (gomşular), relatives (bibi, emmi, aba, dezze), home life, pets (püsük)."),
    ("batch_03_gunluk_is_okul_stres.jsonl", "gunluk_sohbet",
     "Work fatigue, school/exams, deadlines, commute/traffic, motivation, venting about busy days, work-life balance."),
    ("batch_04_gunluk_sosyal_hobi.jsonl", "gunluk_sohbet",
     "Friends, weekend plans, football/sports, movies/books/music, walks, hobbies, lighthearted humor & friendly banter."),
    ("batch_05_gunluk_duygu_dertlesme.jsonl", "gunluk_sohbet",
     "Empathy, encouragement, minor misunderstandings (nizah), moving cities / homesickness (melmeket hasreti), life choices, celebrating good news."),
    # genel_yardim (5)
    ("batch_06_yardim_teknoloji.jsonl", "genel_yardim",
     "Phones, laptops, Wi-Fi, passwords, backups, apps, basic troubleshooting, and digital concepts explained simply in warm Merkez voice."),
    ("batch_07_yardim_mutfak_ev.jsonl", "genel_yardim",
     "Practical cooking tips, ingredient substitutes, food preservation, cleaning/stain hacks, minor home fixes, balcony/garden plants."),
    ("batch_08_yardim_egitim_kariyer.jsonl", "genel_yardim",
     "Study methods, CV/interview tips, language learning, time management, organizing notes, drafting polite everyday messages."),
    ("batch_09_yardim_saglik_yasam.jsonl", "genel_yardim",
     "Everyday wellness: sleep habits, posture, hydration, walking routines, stress habits, safe non-diagnostic practical guidance + reminding when to see a doctor."),
    ("batch_10_yardim_bilgi_aciklama.jsonl", "genel_yardim",
     "General knowledge Q&A: science, history, geography, personal budgeting, travel planning, everyday how-things-work explanations in natural Merkez speech."),
    # maras_kultur (4)
    ("batch_11_kultur_mutfak.jsonl", "maras_kultur",
     "Maraş cuisine: dondurma, tarhana, eli böğründe, eşgili aya sulusu, içli köfte, mumbar, sömelek, tirşik, acem pilavı, ravanda, samsa, çörek, bastık, cevizli sucuk, kırma, biber/salça."),
    ("batch_12_kultur_gezilecek_yerler.jsonl", "maras_kultur",
     "Merkez & surroundings: Kapalı Çarşı, Ulu Cami, Taş Medrese, Kahramanmaraş Kalesi, Ahır Dağı, Başkonuş, Pınarbaşı, Tekir, Yedikuyular, Ilıca, Germanicia, Döngel, Menzelet, Ceyhan/Aksu."),
    ("batch_13_kultur_gelenek_esnaf.jsonl", "maras_kultur",
     "Crafts & customs: bakırcılık, yemeni/köşkerlik, oymacılık, sırma işleme, bayramlar, kız isteme, düğün, komşuluk, misafirperverlik, yayla/bağ kültürü."),
    ("batch_14_kultur_tarih_edebiyat.jsonl", "maras_kultur",
     "Local history & literature: Sütçü İmam, 12 Şubat Kurtuluş, Edebiyatın Başkenti (Yedi Güzel Adam — Cahit Zarifoğlu, Erdem Bayazıt, Rasim Özdenören, Nuri Pakdil, Necip Fazıl, Karacaoğlan, Âşık Mahzuni, Abdurrahim Karakoç)."),
    # sozluk_deyim (4)
    ("batch_15_sozluk_merkez_1.jsonl", "sozluk_deyim",
     "Word & idiom Q&A grounded strictly in the first half of Merkez lexicon entries provided in lexicon_seeds."),
    ("batch_16_sozluk_merkez_2.jsonl", "sozluk_deyim",
     "Word & idiom Q&A grounded strictly in the second half of Merkez lexicon entries provided in lexicon_seeds."),
    ("batch_17_sozluk_genel_1.jsonl", "sozluk_deyim",
     "Word & idiom Q&A grounded strictly in curated daily-use general + Türkoğlu lexicon entries (verbs, adjectives, household, family, food, weather) provided in lexicon_seeds."),
    ("batch_18_sozluk_genel_2.jsonl", "sozluk_deyim",
     "Word & idiom Q&A grounded strictly in the second curated general + Türkoğlu lexicon slice, plus Maraş interjections (yoheri, peh, heri, bahele, tama, ola, gadan alım), idioms, and compare-two-words questions."),
    # yerel_anlati (4)
    ("batch_19_anlati_eski_maras.jsonl", "yerel_anlati",
     "Old Maraş neighborhoods, winter evenings, mangal/soba, bağ evleri, yayla life, old çarşı memories inspired by the Merkez & general dialect excerpts."),
    ("batch_20_anlati_cocukluk_oyun.jsonl", "yerel_anlati",
     "Childhood memories, traditional street games, elders' stories & sayings, school days, summer days by streams inspired by the dialect excerpts."),
    ("batch_21_anlati_mevsim_hasat.jsonl", "yerel_anlati",
     "Seasonal preparations: bağ bozumu, pekmez, tarhana, biber kurutma, salça/turşu, garden/orchard life adapted strictly into Kahramanmaraş Merkez grammar."),
    ("batch_22_anlati_fikra_kisa_hikaye.jsonl", "yerel_anlati",
     "Short Maraş anecdotes, witty neighbor tales, gentle local humor, short bedtime/moral stories told in warm Merkez voice."),
]


def main() -> None:
    lex = load_clean_lexicon()
    texts = load_clean_texts()
    avoid = load_avoid_prompts()

    merkez_lex = lex["merkez"]
    mid_m = len(merkez_lex) // 2
    merkez_1 = merkez_lex[:mid_m]
    merkez_2 = merkez_lex[mid_m:]

    # Curate daily-use general + turkoglu entries (prefer shorter, clearer meanings)
    gen_turk = [
        e for e in (lex["general"] + lex["turkoglu"])
        if 4 <= len(e["meaning"]) <= 180 and len(e["term"]) <= 40
    ]
    gen_1 = gen_turk[:120]
    gen_2 = gen_turk[120:240]

    # Non-overlapping text seeds for yerel_anlati
    dt_merkez = texts["merkez"]
    dt_general = texts["general"]
    dt_turk = texts["turkoglu"]
    t_mid = len(dt_turk) // 2

    text_seed_map = {
        "batch_19_anlati_eski_maras.jsonl": dt_merkez[:15] + dt_general[:8],
        "batch_20_anlati_cocukluk_oyun.jsonl": dt_general[8:] + dt_turk[:40],
        "batch_21_anlati_mevsim_hasat.jsonl": dt_turk[40:90],
        "batch_22_anlati_fikra_kisa_hikaye.jsonl": dt_merkez[15:] + dt_turk[90:130],
    }

    lex_seed_map = {
        "batch_15_sozluk_merkez_1.jsonl": merkez_1,
        "batch_16_sozluk_merkez_2.jsonl": merkez_2,
        "batch_17_sozluk_genel_1.jsonl": gen_1,
        "batch_18_sozluk_genel_2.jsonl": gen_2,
    }

    batches = []
    vocab_n = len(MERKEZ_THEMATIC_VOCAB)
    for idx, (filename, category, topic_brief) in enumerate(BATCH_SPECS, start=1):
        if filename in lex_seed_map:
            seeds = lex_seed_map[filename]
        else:
            # Rotate a 28-item slice of thematic Merkez vocabulary reminders
            start = (idx * 7) % vocab_n
            seeds = [MERKEZ_THEMATIC_VOCAB[(start + j) % vocab_n] for j in range(28)]

        batches.append({
            "batch_id": idx,
            "filename": filename,
            "category": category,
            "topic_brief": topic_brief,
            "target_count": 50,
            "multi_turn_target": "18-22 dialogues with 2-3 user/assistant turns; 28-32 single-turn dialogues",
            "user_dialect_target": "15 dialogues (~30%) with natural Maraş-dialect user prompts; 35 dialogues (~70%) with natural standard Turkish user prompts",
            "lexicon_seeds": seeds,
            "text_seeds": text_seed_map.get(filename, []),
            "avoid_prompts": avoid.get(category, []),
        })

    DEFAULT_OUT.parent.mkdir(parents=True, exist_ok=True)
    DEFAULT_OUT.write_text(
        json.dumps({"batches": batches}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"Wrote {len(batches)} batch specs to {DEFAULT_OUT}")
    for b in batches:
        print(
            f" - {b['batch_id']:02d} {b['filename']} ({b['category']}): "
            f"{len(b['lexicon_seeds'])} lex seeds, {len(b['text_seeds'])} text seeds"
        )


if __name__ == "__main__":
    main()
