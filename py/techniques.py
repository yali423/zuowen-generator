# -*- coding: utf-8 -*-
"""写作技巧库 · 六年级上册

技巧清单来自网上查到的两套体系（小学作文技巧 30 项手册、六上习作五步法），
但"哪些定为固定技巧"不是我说了算——按用户提供的 4 篇范文里的出现率排序：

    比喻        4/4   ← 定为固定
    动作分解     4/4   ← 定为固定
    对话        3/4   ← 定为固定
    对比        3/4   ← 定为固定
    心理        3/4   ← 定为固定
    排比        3/4   ← 不选：范文里最"假"的就是这个
    成语        3/4   ← 不选：成语堆砌是模板味重灾区
    听觉/拟声/小物件  1/4   ← 只能做随机

分三层：

  SKELETON（骨架 4 项，每篇必须齐）
      由头、动作慢镜头、回望或画面、第一人称贯穿。

  FIXED_TECHS（固定技巧 5 项，每篇至少命中 3 项）
      比喻、动作分解、对话、对比、心理。

  RANDOM_TECHS（随机技巧 12 项，每篇抽 1—3 项，单项使用率 ≤30%）
"""
import json
import os
import random
import re

STATE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".tech_state.json")

ANCHOR_WORDS = ("那天", "有一次", "那年", "上个月", "暑假", "寒假", "昨天", "今天",
                "星期", "早上", "下午", "晚上", "第一次", "小时候", "去年", "今年",
                "开学", "放假", "周末", "第二天")
ACTION_VERBS = ("蹲", "站", "坐", "走", "跑", "拿", "放", "递", "抬", "推", "拉",
                "摸", "咬", "吃", "喝", "翻", "写", "擦", "洗", "摘", "抱", "扶",
                "握", "捏", "拍", "敲", "剪", "缝", "折", "贴", "装", "倒", "接", "伸")
LOOKBACK_WORDS = ("现在", "后来", "直到", "回去的路上", "那天晚上", "第二天", "如今",
                  "到现在", "这几年", "今年", "上个星期", "临走")

SKELETON = [
    {"key": "由头", "name": "开头交代由头",
     "desc": "不说“我觉得 XX 很美好”，先给一件事、一个时间：那天下大雪 / 有一次 / 小时候"},
    {"key": "慢镜头", "name": "动作慢镜头",
     "desc": "把一件事拆成连续小动作：蹲下、伸手、捏住、一拧，而不是“他很生气”"},
    {"key": "回望", "name": "结尾回望或画面收笔",
     "desc": "结尾停在具体的东西上（现在我还留着 / 灯还亮着），不喊“让我们一起”式口号"},
    {"key": "第一人称", "name": "第一人称贯穿",
     "desc": "每一段都有“我”在里面——我看见了、我摸到了、我没说话"},
]

FIXED_TECHS = [
    {"key": "比喻", "name": "比喻", "rate": "4/4",
     "pat": r"(像|似的|如同|仿佛|好比)"},
    {"key": "动作分解", "name": "动作分解", "rate": "4/4",
     "pat": r"(先|接着|然后|最后|一把|猛地|用力|使劲|伸手|弯腰|蹲下|抬起|端起)"},
    {"key": "对话", "name": "对话一句", "rate": "3/4",
     "pat": r"[：:]\s*[“\"「]|[”\"」]|说道|说[：:]|问[：:]|喊"},
    {"key": "对比", "name": "对比", "rate": "3/4",
     "pat": r"(不像|以前|从前|别人|比.{0,10}还)"},
    {"key": "心理", "name": "心理一句", "rate": "3/4",
     "pat": r"(心里|不敢|怕|舍不得|着急|难受|愣|慌)"},
]
MIN_FIXED_HIT = 2

RANDOM_TECHS = [
    {"key": "听觉", "name": "五感·听觉", "pat": r"(声音|响|叫|听|吵|静得|嗡|吱呀)"},
    {"key": "嗅觉", "name": "五感·嗅觉", "pat": r"(味|香|臭|气味|腥|油烟)"},
    {"key": "触觉", "name": "五感·触觉", "pat": r"(凉|烫|软|硬|湿|糙|滑|冰|热乎|硌)"},
    {"key": "拟声", "name": "拟声词", "pat": r"(咚|啪|哗|哐|咕嘟|嗖|咔|嗤|滴答|沙沙|咯吱)"},
    {"key": "数字", "name": "数字具体化",
     "pat": r"([两三四五六七八九十百千]{1,3}(个|块|次|遍|只|张|天|年|分|秒|斤|层|排))"},
    {"key": "神态", "name": "神态特写", "pat": r"(脸.{0,4}红|低头|皱眉|抿|瞪|眼眶|嘴角)"},
    {"key": "侧面", "name": "侧面烘托", "pat": r"(笑|摇头|点头|围过|问我|夸|看着|瞧)"},
    {"key": "环境", "name": "环境烘托", "pat": r"(灯|窗|风|雨|树影|太阳|阳光|天黑|院里)"},
    {"key": "小物件", "name": "小物件特写", "pat": r"(一道|一条|一根|一角|一小|半|缺口|裂纹|缝|印子|锈)"},
    {"key": "名言", "name": "引用一句", "pat": r"(说过|俗话说|常言道|古人云|书上说)"},
    {"key": "拟人", "name": "拟人", "pat": r"(不肯|偏要|躺着|站着等|看着|等着)"},
    {"key": "反问", "name": "反问", "pat": r"(难道|怎么会|岂不是|又能|谁不)"},
    {"key": "排比", "name": "排比", "pat": r"(；[^。]{2,30}；|有的.{2,20}有的)"},
]

MAX_RATE = 0.30
PICK_MIN, PICK_MAX = 1, 3

_PAT_FIXED = {t["key"]: re.compile(t["pat"]) for t in FIXED_TECHS}
_PAT_RANDOM = {t["key"]: re.compile(t["pat"]) for t in RANDOM_TECHS}


def check_skeleton(text):
    paras = [p for p in text.split("\n") if p.strip()]
    first = paras[0] if paras else ""
    last = paras[-1] if paras else ""
    body = "".join(paras[1:-1]) if len(paras) >= 3 else ""
    action = sum(1 for s in re.split(r"[。！？]", body)
                 if len(s) >= 6 and any(v in s for v in ACTION_VERBS))
    return {
        "由头": any(w in first for w in ANCHOR_WORDS),
        "慢镜头": action >= 3,
        "回望": any(w in last for w in LOOKBACK_WORDS) or bool(
            re.search(r"(蹲|站|坐|走|拎|扛|拉|抱|看着)", last)),
        "第一人称": sum(1 for p in paras if "我" in p) >= 3,
    }


def check_fixed(text):
    return [k for k, p in _PAT_FIXED.items() if p.search(text)]


def hit_fixed_keys(sent):
    """一句话能满足哪些固定技巧（缺技巧时用来加权选句）。"""
    if not sent:
        return set()
    return {k for k, p in _PAT_FIXED.items() if p.search(sent)}


def hit_keys(sent):
    if not sent:
        return set()
    return {k for k, p in _PAT_RANDOM.items() if p.search(sent)}


def check_random(text):
    return [k for k, p in _PAT_RANDOM.items() if p.search(text)]


def load_state():
    try:
        with open(STATE_FILE, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and "counts" in d and "total" in d:
            return d
    except Exception:
        pass
    return {"counts": {}, "total": 0}


def save_state(state):
    try:
        with open(STATE_FILE, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False)
    except Exception:
        pass


def available_keys(pool_texts):
    """这个题材的素材里本身就存在的技巧——抽技巧只从中选，否则抽中了也落不下去。"""
    blob = "\n".join(pool_texts)
    return {t["key"] for t in RANDOM_TECHS
            if len(re.findall(t["pat"], blob)) >= 3}


def pick_random_techs(rng, state=None, allowed=None):
    if state is None:
        state = load_state()
    total = max(1, state.get("total", 0))
    pool = [t for t in RANDOM_TECHS
            if state.get("counts", {}).get(t["key"], 0) / total < MAX_RATE - 0.05]
    if allowed:
        narrowed = [t for t in pool if t["key"] in allowed]
        if narrowed:
            pool = narrowed
    if not pool:
        state["counts"] = {}
        state["total"] = 0
        pool = list(RANDOM_TECHS)

    # 按"已用次数"反比加权：用得越少越容易被抽到。
    # 只靠"超过上限就排除"不够——限定题材后候选变少，某一项会一路冲到 38%。
    k = min(rng.randint(PICK_MIN, PICK_MAX), len(pool))
    picks = []
    cand = list(pool)
    weights = [1.0 / (1 + state.get("counts", {}).get(t["key"], 0)) for t in cand]
    for _ in range(k):
        total_w = sum(weights)
        r = rng.random() * total_w
        acc = 0.0
        idx = len(cand) - 1
        for i, w in enumerate(weights):
            acc += w
            if r <= acc:
                idx = i
                break
        picks.append(cand.pop(idx))
        weights.pop(idx)
    return picks


def record(state, keys):
    state["total"] = state.get("total", 0) + 1
    cnt = state.setdefault("counts", {})
    for k in keys:
        cnt[k] = cnt.get(k, 0) + 1


def describe(key):
    for t in SKELETON:
        if t["key"] == key:
            return "[骨架] " + t["name"] + " —— " + t["desc"]
    for t in FIXED_TECHS:
        if t["key"] == key:
            return "[固定] " + t["name"] + "（范文出现率 %s）" % t["rate"]
    for t in RANDOM_TECHS:
        if t["key"] == key:
            return "[随机] " + t["name"]
    return key


# ============================================================
# 技巧讲解（界面上点一下弹出来的内容）
# ------------------------------------------------------------
# why  —— 这样写好在哪，用六年级能懂的话说
# eg   —— "一般写法 → 这样写"的对照，都是能直接照着改的句子
# ============================================================
TECH_INFO = {
    # ---------- 骨架 4 项 ----------
    "由头": {
        "why": "一上来就抒情，读的人还没弄明白你在说哪件事。"
               "先交代一个时间、一件小事，读者才跟得进去，后面的感受也才站得住。",
        "eg": "一般：我觉得亲情很温暖。\n"
              "这样写：那年冬天特别冷，我妈把我的手揣进她棉袄兜里。",
    },
    "慢镜头": {
        "why": "写动作别急着下结论（“他很着急”），把人拆成几个连着的小动作，"
               "读者自己就能看出他着急——看出来比你告诉他更有劲。",
        "eg": "一般：爷爷很小心地把碗端起来。\n"
              "这样写：爷爷两只手捧住碗沿，先试了试烫不烫，才一点一点往起端。",
    },
    "回望": {
        "why": "结尾喊口号最假。停在一个具体的画面或东西上，情绪自己会出来，"
               "而且余味更长——读者合上本子还会想起那个画面。",
        "eg": "一般：这次活动让我明白了坚持的重要。\n"
              "这样写：现在那把伞还挂在门后，伞骨有一根是歪的。",
    },
    "第一人称": {
        "why": "每一段都有“我”，文章才有在场感：不是站在旁边看别人，"
               "而是我自己看见了、摸到了、忍住了没说。",
        "eg": "一般：操场上很热闹，大家都在加油。\n"
              "这样写：我站在队伍最后面，喊得嗓子发哑。",
    },
    # ---------- 固定 5 项 ----------
    "比喻": {
        "why": "打比方能把没见过的东西一下变得看得见。诀窍是比得近、比得土——"
               "用身边的东西比，别用书上抄来的词。",
        "eg": "一般：那条麻绳很粗。\n"
              "这样写：那条麻绳有手腕那么粗，横在跑道上，像一条睡着的蛇。",
    },
    "动作分解": {
        "why": "一件事拆成几步，读者才看得见过程；不拆，只能看见结果。"
               "“先……接着……最后……”不是套路，是人做事本来的顺序。",
        "eg": "一般：我把饺子包好了。\n"
              "这样写：我先捏住中间，再把两边往一块儿按，最后一个一个摆到盖帘上。",
    },
    "对话": {
        "why": "一句人物原话，比十句形容更能立住一个人。话要短，"
               "最好带点他本人的口头习惯，别让人物说“书面语”。",
        "eg": "一般：妈妈安慰我说没关系。\n"
              "这样写：她说：“碎了就碎了，手没划着吧？”",
    },
    "对比": {
        "why": "有比较才看得出变化：以前怎么样、现在怎么样，别人怎么样、我怎么样。"
               "变化写出来了，进步就不用自己说。",
        "eg": "一般：我进步很大。\n"
              "这样写：上个月我连一百个都跳不到，昨天一口气跳了一百八。",
    },
    "心理": {
        "why": "写心里那一句实话，哪怕不好听。“我怕丢人”比“我鼓起勇气”真实十倍，"
               "也更容易让读的人想起自己。",
        "eg": "一般：我鼓起勇气走上台。\n"
              "这样写：我站在台阶下面，腿有点软，想着要不就说肚子疼。",
    },
    # ---------- 随机 13 项 ----------
    "听觉": {
        "why": "声音是最省力的现场感，一两个就够，写多了吵。",
        "eg": "走廊里只有拖鞋蹭地的声音，沙——沙——。",
    },
    "嗅觉": {
        "why": "气味最容易把人拉回某个场景，比“很香”具体十倍。",
        "eg": "一进门就是葱花下油锅的味，衣服上沾了一天。",
    },
    "触觉": {
        "why": "写手上的感觉（凉、烫、糙、硌），比写“我很紧张”更能让人跟着紧张。",
        "eg": "碗是温的，碗底有一圈没擦干的水。",
    },
    "拟声": {
        "why": "拟声词不是为了热闹，是为了让动作有声音、有节奏。",
        "eg": "咚的一声，瓦片直挺挺扎进水里。",
    },
    "数字": {
        "why": "具体的数字比“很多”“很久”可信，读者会信你说的是真事。",
        "eg": "数到第三十七下，我手就抖了。",
    },
    "神态": {
        "why": "脸上的小变化（抿嘴、皱眉、耳根红）比“他很生气”准确得多。",
        "eg": "他抿着嘴不说话，耳根有点红。",
    },
    "侧面": {
        "why": "不直接写主角，写旁边人的反应，效果反而更强——这是“让别人的眼睛替你说话”。",
        "eg": "我还没开口，旁边的同学先笑出了声。",
    },
    "环境": {
        "why": "环境是情绪的放大器：天黑了、灯亮了、风停了，读者自己会跟着沉下来。",
        "eg": "路灯一盏一盏亮起来，操场上只剩我们班。",
    },
    "小物件": {
        "why": "一个旧东西比一段抒情更能说明时间：缺口、裂纹、锈，都在替你说话。",
        "eg": "伞骨有一根是歪的，用铁丝缠过。",
    },
    "名言": {
        "why": "引用要短，而且得跟你写的事对得上；对不上就像贴了一张标签。",
        "eg": "奶奶说：“勤快人手里没有闲东西。”",
    },
    "拟人": {
        "why": "把东西写得有脾气，文章就活了。别全篇用，一两处就够。",
        "eg": "风把门推得咣当一声，像是也不耐烦了。",
    },
    "反问": {
        "why": "反问是把话递给读者，让他自己回答。一篇里有一句就够，多了像吵架。",
        "eg": "下了一整夜的雨，这样的天，谁能不喜欢？",
    },
    "排比": {
        "why": "排比能造气势，但最容易写成空话。要用就用在具体的事上，三句就收。",
        "eg": "他把绳头递给我，把水递给我，把最后一块饼也递给我。",
    },
}


def info(key):
    """取一条技巧的讲解：名字、类别、好处、范例。找不到也返回一个能显示的壳。"""
    name, kind, desc = key, "", ""
    for t in SKELETON:
        if t["key"] == key:
            name, kind, desc = t["name"], "骨架（每篇都要有）", t["desc"]
            break
    else:
        for t in FIXED_TECHS:
            if t["key"] == key:
                name, kind, desc = t["name"], "固定技巧（范文里出现最多）", ""
                break
        else:
            for t in RANDOM_TECHS:
                if t["key"] == key:
                    name, kind = t["name"], "随机技巧（这篇抽中的）"
                    break
    d = TECH_INFO.get(key) or {}
    return {"key": key, "name": name, "kind": kind, "desc": desc,
            "why": d.get("why", desc) or desc, "eg": d.get("eg", "")}


def find_example(text, key):
    """在这篇文章里找一句真正用到该技巧的句子，用来做“本文示例”。"""
    paras = [p for p in (text or "").split("\n") if p.strip()]
    if not paras:
        return ""
    sents = []
    for p in paras:
        for s in re.split(r"[。！？]", p):
            s = s.strip("　 ")
            if len(s) >= 6:
                sents.append(s)

    # 骨架 4 项没有关键词可匹配，按位置/动作密度取
    if key == "由头":
        return sents[0] if sents else ""
    if key == "回望":
        return sents[-1] if sents else ""
    if key == "慢镜头":
        body = sents[1:-1] or sents
        return max(body, key=lambda s: sum(1 for v in ACTION_VERBS if v in s))
    if key == "第一人称":
        for s in sents:
            if "我" in s:
                return s
        return ""

    pat = _PAT_FIXED.get(key) or _PAT_RANDOM.get(key)
    if not pat:
        return ""
    for s in sents:
        if 6 <= len(s) <= 42 and pat.search(s):
            return s
    return ""
