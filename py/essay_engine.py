# -*- coding: utf-8 -*-
"""
作文生成引擎 · 六年级上册
--------------------------------
素材驱动的随机组合引擎。核心思想：
  每个题材由若干「段落」组成，每段由若干「槽位」组成，
  每个槽位提供多条候选句，用 (最低适用分档, 句子) 标注。
  生成时按目标分档过滤：低档只用到朴素句，高档自动开启
  细节句、修辞句、升华句——于是字数与文采都随分档自然递增，
  而不是简单地把"高级词"替换进去。

分档原则来自评分标准：
  25-26：切题、有事例，但叙述平、细节少，对比只在首尾喊一下，
         开头结尾模式化，结尾贴口号。
  27-28：事例完整、细节较具体、有 1-2 处修辞，感悟略套路。
  29-30：开头以场景/悬念入题，动作神态心理至少两种，对比藏在
         事例里，三四句修辞不堆砌，结尾用具体画面点题、不喊口号。

字数：用户在界面选目标字数（350/400/450/500/550/600），不足用 extra 句
补，超出则从最长的段落末尾裁掉句子，保证落在所选档 ±5/+15 之间。
"""

import re
import random
import datetime

try:                              # 低分档的同义改写表（放在素材库里，方便随时加）
    from essay_data import PARAPHRASE as _PARA
except Exception:
    _PARA = {}

import techniques as TECH          # 写作技巧：骨架 + 固定 5 + 随机 13
import words as WORDS              # 词汇分层：好词打分 + 安全替换

# 当前这一篇抽中的随机技巧（pick() 里据此给候选句加权）
_TECH_KEYS = set()

TIERS = [25, 26, 27, 28, 29, 30]

TIER_LABEL = {
    25: "25 分 · 二类文上",
    26: "26 分 · 二类文上",
    27: "27 分 · 一类文",
    28: "28 分 · 一类文",
    29: "29 分 · 一类文上",
    30: "30 分 · 满分",
}

MIN_CHARS, MAX_CHARS = 345, 615    # 350 档的下限和 600 档的上限；具体判定跟用户选的档走

# 每个档位的目标字数：越低档越贴近 350 的底线（真实考场里 25 分作文
# 往往就是"刚够篇幅"），越高档细节越多、篇幅越长，但都锁在 350-450 内
# 用户没选字数时的默认目标（跟随分档，350 档短、600 档满）
TARGET = {25: 358, 26: 366, 27: 384, 28: 400, 29: 415, 30: 430}


def char_count(text):
    """按学校习惯：含标点、不含空白与换行"""
    return len(re.sub(r"\s", "", text))


def pick(slot, tier, rng):
    """从槽位里按分档取一句：只用 min_tier <= 目标档的候选，优先取最高档的 2 条再随机"""
    cands = [c for c in slot if c[0] <= tier]
    if not cands:
        return ""
    # 高分档不许降级用低档句：28 分以上只用"接近本档"的句子。
    # 否则 30 分的文章里会冒出"我跑过去，用力跳了一下"这种三年级口吻
    # （低档句命中技巧时权重会压过高档句，必须在这里拦住）。
    if tier >= 28:
        hi = [c for c in cands if c[0] >= tier - 1]
        if hi:
            cands = hi
    # 技巧加权：本次抽中的随机技巧（听觉/拟声/数字/对话…），
    # 谁的句子带这些特征，就优先被选中——技巧是靠选句体现的，不是事后硬加
    def _tech(c):
        if not _TECH_KEYS:
            return 0
        return len(_TECH_KEYS & (TECH.hit_keys(c[1]) | TECH.hit_fixed_keys(c[1])))

    if tier <= 26:
        # 低分档：优先朴素句，词级分越低越靠前
        cands.sort(key=lambda c: (-_tech(c), WORDS.richness(c[1]), -c[0]))
        pool = cands[:3]
        # 但偶尔掺一个好词：不然通篇平得不像活人写的
        if rng.random() < 0.2:
            rich = [c for c in cands if WORDS.richness(c[1]) >= 2]
            if rich:
                return rng.choice(rich)[1]
    elif tier >= 29:
        # 高分档：优先带好词的句子，但只在技巧命中数相同的句子里挑
        cands.sort(key=lambda c: (-_tech(c), -WORDS.richness(c[1]), -c[0]))
        pool = cands[:3]
    else:
        cands.sort(key=lambda c: (-_tech(c), -c[0]))
        pool = cands[:2]
    s = rng.choice(pool)[1]
    # 25/26 分档：同一句话换一种说法，避免每篇都一模一样
    if tier <= 26 and s in _PARA:
        s = rng.choice(_PARA[s])
    return s


def _text(para_sents):
    return "\n".join("".join(p) for p in para_sents)


def _guess_para(s, n):
    """没标位置的补充句，按时间词猜它该放哪一段，避免把"上台"放到"下台以后"。
    n 是总段数（最后一段是收尾段）。"""
    late = ("后来", "最后", "以后", "回到", "结束", "现在", "从此", "第二天",
            "长大", "多年", "天黑", "放学后", "明年", "去年", "那年", "到现在",
            "如今", "第二天早上", "再后来", "这一次以后", "现在想起来", "现在我还")
    early = ("开始", "上场", "上台", "准备", "一开始", "刚开", "出发", "第一次",
             "排队", "早上", "赛前", "比赛前", "先看", "首先", "起初", "头一回",
             "那天早上", "那天下午")
    if any(w in s for w in late):
        return max(1, n - 2)
    if any(w in s for w in early):
        return 1
    return None


# ============================================================
# 去 AI 味
# ------------------------------------------------------------
# 生成的文字"像 AI 写的"，问题不在词汇，在三个句式习惯：
#   ① 句号太多：人写作文爱用逗号串句，AI 一句一个句号，读起来像分镜脚本；
#   ② 空话补位：凑字数时插进的总结句（"这些小事我一件都没忘"）没有信息；
#   ③ 书面词僵：因此/然而/逐渐/凝视 这类词小学生基本不用。
# 所以这里做三件事：合句、剔空话、换口语词。合并只换标点，不改变字数。
# ============================================================

# 书面语 → 口语（全局替换，安全）
SPOKEN = [
    ("十分", "特别"), ("非常", "特别"), ("顿时", "一下子"),
    ("随即", "就"), ("然而", "可是"), ("因此", "所以"),
    ("仍然", "还是"), ("逐渐", "慢慢"), ("凝视", "看着"),
    ("霎时", "一下子"), ("仿佛", "像是"), ("犹如", "像"),
    ("不禁", "忍不住"), ("内心", "心里"), ("缓缓", "慢慢"),
]

# 纯凑字数的空话：能删就删（删完还够 350 字才删）
EMPTY_SENT = (
    "这样的事还有很多", "这些小事", "我都记在心里", "这些我都记得",
    "说也说不完", "我一件都没忘", "希望以后的日子也这样",
    "日子平平常常", "我很珍惜这样的日子", "这样的日子，我过得很踏实",
    "这些我一件事都没忘", "我都记得", "我常常想，日子要是能慢一点就好了",
)


def _overlap(s, text):
    """粗略的语义相近度：按字符二元组算重合比例。只用来挑"最像这一段"的补句。"""
    a = set(s[i:i + 2] for i in range(len(s) - 1))
    b = set(text[i:i + 2] for i in range(len(text) - 1))
    return len(a & b) / max(1, len(a))


def _max_word_repeat(sent, text):
    """这句里最"实"的那个两字词，在目标段落里已经出现几次。用来压制同段重复用词。"""
    best = 0
    seen = set()
    for i in range(len(sent) - 1):
        w = sent[i:i + 2]
        if w in seen or not re.match(r"[\u4e00-\u9fa5]{2}", w):
            continue
        seen.add(w)
        best = max(best, text.count(w))
    return best


def _spoken(text):
    for a, b in SPOKEN:
        text = text.replace(a, b)
    return text


# ============================================================
# 骨架加固
# ------------------------------------------------------------
# 好作文（包括你发的那 4 篇）都具备三样东西，缺了就读着"不像人写的"：
#   A 开头有个由头：这件事是怎么来的（那天/有一次/小时候/每年…），
#     而不是一上来就喊"我觉得 XX 让生活更美好"。
#   B 中间有推进感：一件接一件地往下走（先…接着…最后）。
#   C 结尾回望：停在具体的东西上（现在我还…/后来我…），不喊口号。
# 这里不是加模板句，而是把素材里本来就有的句子挪到该到的位置。
# ============================================================
_ANCHOR = ("那天", "有一次", "那年", "上个月", "暑假", "寒假", "昨天", "今天",
           "星期", "早上", "下午", "晚上", "第一次", "小时候", "去年", "今年",
           "开学", "放假", "周末", "第二天",
           # 变形记/想象类题材的首句本身就是由头（"我醒来…""我变成了…"），
           # 不认这些词的话骨架修复会乱插一句"有一次…"到开头，时序就倒了
           "醒来", "一睁眼", "睁开眼", "变成了", "梦里", "做梦")
_BACKGROUD = ("小时候", "以前", "往年", "每年", "那时候", "那年", "从前", "我七岁")
_LOOKBACK = ("现在", "后来", "直到", "回去的路上", "那天晚上", "第二天", "如今",
             "到现在", "这几年", "今年", "上个星期")
_ORDER = ("先", "接着", "然后", "最后", "起先", "之后")


def _ensure_skeleton(para_sents, theme, tier, seen, rng, paras_spec=None, pool=None):
    if len(para_sents) < 3:
        return para_sents
    _extra_pool = pool if pool is not None else theme.get("extra", [])

    # A：首段没有由头，先看首段各槽位有没有带锚点的候选（不分档位，
    #    因为"那天下大雪"这种交代本身不难，不该被档位挡住），有就放进去
    if not any(w in "".join(para_sents[0]) for w in _ANCHOR):
        cands = []
        # 先找首段自己槽位里的由头句；不够再从中间段找。
        # 末段不参与——那里全是"后来""现在"的收尾句，搬上去就成
        # "人还没跳先总结完了"。
        pools = list(paras_spec[0]) if paras_spec else []
        for spec_para in (paras_spec or [])[1:-1]:
            pools.extend(spec_para)
        for slot in pools:
            for item in slot:
                txt = item[1]
                if txt in seen or len(txt) < 9:
                    continue
                # 收尾腔的句子不能当由头（"...我记得最清楚""...没拿到名次"）
                if any(w in txt for w in ("记得最清", "名次", "才明白", "到现在", "一直记")):
                    continue
                # 靠代词/转折开头的句子离不开前文（"她发现了，问我…"），
                # 单独搬到开头会变成没头没脑的一句
                if txt[0] in "他她它这那但可却并而所因于":
                    continue
                # 跟已有句子太像的不要（"校运会那天上午…"+"校运会第一天上午…"并排很蠢）
                _body = "".join("".join(p) for p in para_sents)
                if _overlap(txt, _body) > 0.6:
                    continue
                _is_first_pool = any(txt in sp for sp in (paras_spec or [])[:1]
                                     for sl in sp for it in sl if it[1] == txt)
                if _is_first_pool:
                    # 首段自己的槽位：有锚点或背景词都行
                    if not (any(w in txt for w in _ANCHOR) or any(w in txt for w in _BACKGROUD)):
                        continue
                else:
                    # 中间段的句子只认"真背景"（小时候/以前/每年…）——
                    # "有一次…""那天…"是事件句，搬到开头时序就倒了
                    if not any(w in txt for w in _BACKGROUD):
                        continue
                cands.append(txt)
        if cands:
            pick_one = rng.choice(cands)
            para_sents[0].insert(0, pick_one)
            seen.add(pick_one)

    # A2：还是没有，就把后面段落里的"背景型"句子提到首段末尾
    if not any(w in "".join(para_sents[0]) for w in _ANCHOR):
        moved = False
        for i in range(1, len(para_sents) - 1):
            for j, sent in enumerate(para_sents[i]):
                if any(w in sent for w in _BACKGROUD):
                    para_sents[0].append(para_sents[i].pop(j))
                    moved = True
                    break
            if moved:
                break

    # B：中段顺序词不足两个，就从备选句里找一句带顺序的放进中段
    body = "".join("".join(p) for p in para_sents[1:-1])
    if sum(1 for w in _ORDER if w in body) < 2:
        for e in _extra_pool:
            if e[0] > tier or e[-1] in seen:
                continue
            if any(w in e[-1] for w in ("先", "接着", "然后", "最后")):
                para_sents[1].append(e[-1])
                seen.add(e[-1])
                break

    # C：末段没有回望，就用一句回望句替掉末段最后一句（通常是口号）
    last = para_sents[-1]
    if last and not any(w in "".join(last) for w in _LOOKBACK):
        if last[-1].endswith(("。", "！")):
            for e in _extra_pool:
                if e[0] > tier or e[-1] in seen:
                    continue
                if any(w in e[-1] for w in ("现在", "后来", "直到", "如今")):
                    seen.add(last[-1])
                    last[-1] = e[-1]
                    seen.add(e[-1])
                    break
        # 还是没有，就把中段里一句"后来…/现在…"挪到最后——
        # 时间上本来就是收尾的句子，挪过去不会乱
        if not any(w in "".join(last) for w in _LOOKBACK):
            for i in range(len(para_sents) - 2, 0, -1):
                for j, sent in enumerate(para_sents[i]):
                    if any(w in sent for w in ("后来", "现在", "直到")):
                        last.append(para_sents[i].pop(j))
                        break
                else:
                    continue
                break
    return para_sents


def polish(paras, tier, rng, target=None):
    """合句 + 换口语词 + 剔空话。合并只动标点，字数不变。"""
    # 越低的档，越像孩子——逗号串句越多
    p_merge = {25: 0.78, 26: 0.72, 27: 0.58, 28: 0.48, 29: 0.38, 30: 0.30}.get(tier, 0.5)
    out = []
    for para in paras:
        para = _spoken(para)
        # 词汇分层：高档往上换（低概率，避免句句用力），低档往下换回朴素说法
        if tier >= 29:
            para = WORDS.upgrade(para, rng, 0.45)
        elif tier <= 26:
            para = WORDS.downgrade(para, rng, 0.85)
        # 称呼行、落款行、条文行不参与合句
        if para.endswith("：") or re.match(r"^[六七八九]（\d）班", para) or re.match(r"^\d{4}年", para):
            out.append(para)
            continue
        sents = [x for x in re.findall(r"[^。！？]*[。！？]|[^。！？]+$", para) if x]
        if not sents:
            out.append(para)
            continue

        merged = []
        buf = ""
        for s in sents:
            # 没有句末标点的行（落款、称呼、日期）原样输出，不合并、不加句号
            if not s.endswith(("。", "！", "？")):
                if buf:
                    merged.append(buf + "。")
                    buf = ""
                merged.append(s)
                continue
            bare = s.rstrip("。！？")
            # 带引号/问号/感叹号/冒号的句子不并进来，否则语气会变
            plain = not any(ch in s for ch in ("“", "”", "？", "！", "："))
            short = len(bare) <= 15
            if buf:
                _head = buf.split("，")[0]
                _title_like = ("，" in buf) and len(buf) <= 14 and len(_head) <= 4
                # 主语一致才合句。"板擦放在我右边"+"窗外的树在动"这种
                # 主语都不是一个人的句子串成一句，读着就是机器拼的。
                _b_me, _s_me = ("我" in buf), ("我" in bare)
                _b_ta = buf.startswith(("他", "她", "它", "他们", "她们"))
                _s_ta = bare.startswith(("他", "她", "它", "他们", "她们"))
                _same_subj = (_b_me == _s_me) and (_b_ta == _s_ta)
                if (_same_subj and (not _title_like) and plain and short
                        and len(buf) + len(bare) <= 42 and rng.random() < p_merge):
                    # 承前省略主语：`她的碗最小。她爱吃鱼头。` → `她的碗最小，爱吃鱼头。`
                    # 三条限制（都是踩过的坑）：
                    #   不能省"她的"→否则变成"的围裙是花的"；
                    #   句里还带"我/你"时不能省，否则"她看见我很惊讶"变成"看见我很惊讶"，主语换了人；
                    #   段首句是标题式短句（"妈妈，有你真好。"）时不合并，否则标题被吞进正文。
                    head = buf.split("，")[0]
                    is_title = (len(head) <= 12) and ("，" in buf) and len(buf) <= 14
                    if not is_title and rng.random() < 0.6:
                        for pr in ("他们", "她们", "她", "他"):
                            if (bare.startswith(pr)
                                    and not bare.startswith(pr + "的")
                                    and "我" not in bare
                                    and "你" not in bare
                                    and len(bare) > len(pr) + 5):
                                bare = bare[len(pr):]
                                break
                    buf = buf + "，" + bare
                    continue
                merged.append(buf + "。")
                buf = ""
            if plain and short:
                buf = bare            # 先挂起，看看下一句能不能并进来
            else:
                merged.append(s)
        if buf:
            merged.append(buf + "。")
        out.append("".join(merged))

    # 剔空话：仅当删完还够最低字数
    kept = []
    total = sum(char_count(p) for p in out)
    for p in out:
        sents = [x for x in re.findall(r"[^。！？]*[。！？]|[^。！？]+$", p) if x]
        new_sents = []
        for s in sents:
            _floor = (target or TARGET.get(tier, 400)) - 25
            if any(k in s for k in EMPTY_SENT) and total - char_count(s) >= _floor:
                total -= char_count(s)
                continue
            new_sents.append(s)
        kept.append("".join(new_sents))
    return [p for p in kept if p.strip()]


# ============================================================
# 补句池按主线分开
# ------------------------------------------------------------
# 同一个题材的多条主线共用一个补句池时，会串味：
# "我脚扭了在场边看"那条被塞进"我用力拉着绳子"，
# "书吧"那条混进"理想是水，浇灌大树"。
# 这里按字符重合度把每条补句自动归到最像的那条主线；
# 跟哪条都不像的（纯环境句）留作公用。
# ============================================================
_EXTRA_SPLIT = {}


def _extras_for_variant(theme, vi, choices):
    key = id(theme)
    if key not in _EXTRA_SPLIT:
        # 分线判据 v2：主线特征 bigram（本线有、其他线都没有的字对）。
        # 旧判据"extra 句 vs 主线整篇文本的重合率 ≥0.16"对短句天生失灵——
        # 一句 10 字的句子跟 500 字的段落算重合，永远很低，于是大批
        # 某条主线专属的句子（"我的桌面是木头的"）被当成通用句，
        # 塞进另一条主线里（讲桌主线冒出课桌细节），读着就是拼贴。
        # 特征 bigram 是"独有字对"级别的判定，短句也能命中。
        seq_bigrams = []
        for seq in choices:
            han = []
            for para in (seq or []):
                for slot in para:
                    for c in slot:
                        han += [ch for ch in c[-1] if "\u4e00" <= ch <= "\u9fa5"]
            seq_bigrams.append({a + b for a, b in zip(han, han[1:])})
        feats = []
        for i, bg in enumerate(seq_bigrams):
            others = set()
            for j, ob in enumerate(seq_bigrams):
                if j != i:
                    others |= ob
            feats.append(bg - others)
        shared, assigned = [], {}
        for e in theme.get("extra", []):
            sent = e[-1]
            han = [ch for ch in sent if "\u4e00" <= ch <= "\u9fa5"]
            sbg = {a + b for a, b in zip(han, han[1:])}
            best_i, best_n = -1, 0
            for i, f in enumerate(feats):
                n = len(sbg & f)
                if n > best_n:
                    best_i, best_n = i, n
            if best_i >= 0:
                assigned.setdefault(best_i, []).append(e)
            else:
                shared.append(e)
        _EXTRA_SPLIT[key] = (shared, assigned)
    shared, assigned = _EXTRA_SPLIT[key]
    return shared + assigned.get(vi, [])


def assemble(theme, tier, rng, must_keys=(), no_cap=False, user_target=None, floor=None):
    """把题材素材组装成一篇作文（dict: title / paras / text）

    支持两种素材结构：
      theme["paras"]  —— 固定段落序列（老写法，段落数固定）
      theme["blocks"] —— 段落块列表，每块给 2—4 个候选段落，随机选一个；
                         块还可以设 "p" 控制出现概率（0.6 表示六成会出现），
                         于是段落数、事件走向、先后顺序都能变。
    这样同一个题材能写出内容完全不同的几篇，而不只是换措辞。
    target：用户选的目标字数（350—600）。不传就按分档给默认值。
    """
    target = user_target or TARGET.get(tier, 400)

    # 先定这一篇用哪一套段落
    # 注意顺序：blocks 优先。有的题材只有 blocks、没有 paras（整篇由段落块拼），
    # 先判 variants 会去读不存在的 theme["paras"] 而报 KeyError。
    if "blocks" in theme:
        seq = None
        vi = 0
    elif theme.get("variants"):
        choices = [theme["paras"]] + theme["variants"]
        vi = rng.randrange(len(choices))
        seq = choices[vi]
    else:
        seq = theme["paras"]
        vi = 0

    if "blocks" in theme:
        paras_spec = []
        for blk in theme["blocks"]:
            if "pick" in blk:            # 从事例池里随机挑 N 个（顺序随机）
                pool = list(blk["from"])
                rng.shuffle(pool)
                paras_spec.extend(pool[:blk["pick"]])
                continue
            if rng.random() <= blk.get("p", 1.0):
                paras_spec.append(rng.choice(blk["cands"]))
        if len(paras_spec) < 4:                     # 兜底：块太少时补回必选块
            for blk in theme["blocks"]:
                if blk.get("base") and blk.get("cands") and blk["cands"] not in paras_spec:
                    paras_spec.append(rng.choice(blk["cands"]))
    else:
        paras_spec = seq

    # 第一轮：每段按槽位顺序取句
    para_sents = []
    seen = set()
    # 段数决定每段取几句：11 段那种"碎段"题材，一句就是三十来字，
    # 全取会把作文撑到 560 字，删句又会把段内衔接剪断（时间线乱跳）。
    # 按"段数 × 平均句长 × 句数"估个预算，超了才少取——低分档句子短，
    # 照样每段取两句，不然又会掉到 200 字。
    n_para = len(paras_spec)
    _lens = [len(it[1]) for p in paras_spec for slot in p for it in slot if it[0] <= tier]
    if not _lens:
        _lens = [len(it[1]) for p in paras_spec for slot in p for it in slot]
    # 素材总量兜底：素材都是按 450 上限设计的，用户抽到 500/550/600 档时，
    # 全池用尽也可能凑不够。这时把目标收缩到素材实际能撑到的量——
    # 交一篇 470 字的实文，好过硬凑。writer 的字数判定读 doc["target"]，两边一致。
    main_max = 0
    for p_spec in paras_spec:
        for slot in p_spec:
            _c = [c for c in slot if c[0] <= tier] or slot
            main_max += max(char_count(c[1]) for c in _c)
    extra_sum = sum(char_count(e[-1]) for e in theme.get("extra", []) if e[0] <= tier)
    _pool_cap = int(main_max * 0.9) + extra_sum
    if user_target and _pool_cap < user_target:
        # floor 是理想下限，但素材实在撑不到时只能让位——交短一点的实文
        target = max(60, min(floor or MIN_CHARS, _pool_cap - 15))

    _avg = sum(_lens) / max(1, len(_lens))
    slot_cap = 9
    if n_para > 6 and not no_cap:
        while slot_cap > 1 and n_para * _avg * slot_cap > target + 15:
            slot_cap -= 1
    for p_spec in paras_spec:
        sents = []
        # 槽位被 cap 掉时随机挑（而不是永远取前几句）：11 段的题材每段
        # 只取一句，要是一直取第一槽，同一题材写多少遍都是同一篇
        _idxs = list(range(len(p_spec)))
        if len(_idxs) > slot_cap:
            _idxs = sorted(rng.sample(_idxs, slot_cap))
        for si in _idxs:
            slot = p_spec[si]
            s = pick(slot, tier, rng)
            if not s or s in seen:
                continue
            # 段内语义去重："今天也像往常一样，我在林子里飞"和
            # "今天也像往常一样，我在林子低低地飞"并排出现，一眼看出是拼的。
            # 只对长句生效——低分档的句子本来就短，"我哭了"/"我一下就哭了"
            # 这种短句二元组重合高，一刀切会把整段删空。
            if sents:
                _ov = _overlap(s, "".join(sents))
                if (len(s) >= 16 and _ov > 0.60) or (len(s) >= 11 and _ov > 0.80):
                    continue
            seen.add(s)
            sents.append(s)
        if not sents and p_spec and p_spec[0]:
            # 去重去空了（整段两槽说的是同一件事）：至少留一句，别留空段
            s = pick(p_spec[0], tier, rng) or p_spec[0][0][1]
            if s not in seen:
                seen.add(s)
                sents.append(s)
        para_sents.append(sents)

    # 不足目标字数：从 extra 里补句
    # extra 支持两种写法：
    #   (分档, 句子)          → 轮流插进各正文段
    #   (分档, 段落下标, 句子) → 插到指定段落（用来避免"下台以后"又跳回"上台"这类时间错乱）
    # 补句只从本条主线的池子里取（公用环境句 + 本线专属句）
    if theme.get("variants"):
        _choices = [theme["paras"]] + theme["variants"]
        _pool = _extras_for_variant(theme, vi, _choices)
    else:
        _pool = list(theme.get("extra", []))
    extras = [e for e in _pool if e[0] <= tier and e[-1] not in seen]
    rng.shuffle(extras)
    # 先按"是否带本次抽中的技巧"排，再按分档排——这样技巧落地率更高
    extras.sort(key=lambda e: (
        -(len(_TECH_KEYS & (TECH.hit_keys(e[-1]) | TECH.hit_fixed_keys(e[-1]))) if _TECH_KEYS else 0),
        -e[0]))
    # 低年级写话题材可能只有 1—2 段，body_idx 必须夹在现有段数内
    body_idx = [i for i in range(1, max(2, len(para_sents) - 1))
                if i < len(para_sents)]
    cap = 92                  # 单段上限，避免一段被补句撑成大胖子（补句堆多了像清单）
    last_at = len(para_sents) - 1
    last_added = 0
    k = 0
    per_para = [0] * len(para_sents)      # 每段已经塞了几句补句
    for item in extras:
        if char_count(_text(para_sents)) >= target:
            break
        if len(item) == 3:
            s = item[2]
            at = max(0, min(int(item[1]), len(para_sents) - 1))
        else:
            s = item[1]
            # 语义去重：跟正文某段已经高度重合的补句直接不要（否则出现
            # "树是爷爷年轻时栽的" 和 "是我爷爷年轻时候栽的" 并排这种蠢事）
            if max((_overlap(s, "".join(p)) for p in para_sents), default=0) > 0.40:
                continue
            at = _guess_para(s, len(para_sents))
            if at is None:
                # 只往"还能放"的段里挑：每段最多 2 句补句，且优先挑关键词最像的那一段，
                # 这样补句不会跟本段主题八竿子打不着（挑西瓜段里塞进乐高细节）
                cand = [i for i in body_idx
                        if per_para[i] < 2 and char_count("".join(para_sents[i])) <= cap]
                if not cand:
                    # 优先每段 2 句，但字数没凑够时放宽：找"补句最少且装得下"的段
                    cand = [i for i in body_idx if char_count("".join(para_sents[i])) <= cap]
                if not cand:
                    cand = list(body_idx)
                if not cand:
                    continue
                # 词频抑制：这一段里这个词已经说了两遍，就别再说第三遍
                cand = [i for i in cand
                        if _max_word_repeat(s, "".join(para_sents[i])) < 2] or cand
                scored = [(_overlap(s, "".join(para_sents[i])) - 0.02 * per_para[i], i) for i in cand]
                best, at = max(scored)
                # 跟每段都毫无关系（重合度接近 0）的句子不硬塞——那正是拼贴感的来源
                if best <= 0.03 and per_para[at] >= 1:
                    continue
            if at not in body_idx:
                continue
            per_para[at] += 1
        # 结尾段最多补两句，其余往还没满的正文段放
        if at == last_at:
            if last_added >= 2:
                at = max(1, last_at - 1)
            else:
                last_added += 1
        if char_count("".join(para_sents[at])) > cap:
            room = [i for i in body_idx if char_count("".join(para_sents[i])) <= cap]
            if room:
                at = min(room, key=lambda i: char_count("".join(para_sents[i])))
        para_sents[at].append(s)
        seen.add(s)

    para_sents = _ensure_skeleton(para_sents, theme, tier, seen, rng, paras_spec,
                                  pool=_pool)

    # 兜底：还差字数时，把本题材没用过的句子放宽补进来。
    # 前面按相关度筛掉了不少句子，个别题材（句池小的）会掉到 320 字，
    # 这里宁可用一句"稍偏一点但仍是本题材的"句子，也不交一篇短作文。
    if char_count(_text(para_sents)) < target - 1:
        # 先用本线池（更贴合），用完了自动接题材全池，保证不交短作文
        spare = [e[-1] for e in _pool if e[0] <= tier and e[-1] not in seen]
        spare += [e[-1] for e in theme.get("extra", [])
                  if e[0] <= tier and e[-1] not in seen and e[-1] not in spare]
        rng.shuffle(spare)
        for s in spare:
            if char_count(_text(para_sents)) >= target + 5:
                break
            if not body_idx:
                para_sents[0].append(s)     # 单段题材：只能往唯一一段里塞
            else:
                idx = min(body_idx, key=lambda i: char_count("".join(para_sents[i])))
                para_sents[idx].append(s)
            seen.add(s)

    # 超出：从最长且句数 >=3 的段落末尾裁句，直到进了目标区间。
    # 但"真细节"那一句不能裁——题材在 must 里点名的句子是这篇的命，
    # 裁掉就退化成模板文了，宁可多几个字。
    guard = 0
    while char_count(_text(para_sents)) > min(target + 12, MAX_CHARS - 4) and guard < 20:
        cands = [i for i, p in enumerate(para_sents) if len(p) >= 3]
        if not cands:
            # 11 段那种"碎段"题材，每段本来就只有两句：允许压到一句，
            # 否则字数一超标就完全裁不动（会出现 560 字的作文）
            cands = [i for i, p in enumerate(para_sents) if len(p) >= 2]
        idx = None
        for i in sorted(cands, key=lambda i: -char_count("".join(para_sents[i]))):
            if any(k in para_sents[i][-1] for k in must_keys):
                continue
            idx = i
            break
        if idx is not None:
            para_sents[idx].pop()
        else:
            # 全篇能删的段末句都带真细节：退一步，从有 3 句的段里
            # 挑"不含关键词"的那一句删（保留真细节本身）
            for i in sorted(cands, key=lambda i: -char_count("".join(para_sents[i]))):
                # 段首那句多是铺垫（"我坐在沙坑边上…"），删它比删后面
                # 正在推进的句子安全；所以段首先试
                order = sorted(range(len(para_sents[i])), key=lambda j: j != 0)
                for j in order:
                    if not any(k in para_sents[i][j] for k in must_keys):
                        para_sents[i].pop(j)
                        idx = i
                        break
                if idx is not None:
                    break
            if idx is None:
                # 最后手段：整篇能裁的句子全带着 must 词。超长是硬上限
                # （比如 29 档全取 + must 词恰好铺满首尾），宁可这一轮丢真细节——
                # make 会换组合重来，must 齐全又不超长的组合评分更高。
                full = [i for i, p in enumerate(para_sents) if len(p) >= 3]
                if full:
                    idx = max(full, key=lambda i: char_count("".join(para_sents[i])))
                    para_sents[idx].pop()
                else:
                    break
        guard += 1

    paras = ["".join(p) for p in para_sents if p]
    # 去 AI 味：合句 + 口语替换 + 剔空话（合并只换标点，字数不变）
    paras = polish(paras, tier, rng, target=target)
    # 倡议书之类需要落款日期
    today = datetime.date.today()
    date_str = "%d年%d月%d日" % (today.year, today.month, today.day)
    paras = [p.replace("{date}", date_str) for p in paras]
    title = theme["title"] if isinstance(theme["title"], str) else rng.choice(theme["title"])
    return {"title": title, "paras": paras, "text": "\n".join(paras), "target": target}



# 范文模板句黑名单：这几样是"AI 味"最重的标志，任何一篇都不许出现
BANNED = (
    "让我们一起", "通过这次", "通过这", "我明白了", "我懂得了", "使我明白",
    "首先，", "其次，", "总之，", "有人说，", "而我说",
    "我心想", "只见", "俗话说", "常言道", "古人云", "说过：",
    "数不胜数", "摩拳擦掌", "跃跃欲试", "人山人海",
    "热闹非凡", "震耳欲聋", "响彻云霄", "欢呼雀跃", "齐心协力", "不甘示弱",
    "文思泉涌", "得心应手", "恰到好处", "大显身手", "阳光明媚", "万里无云",
    "一碧千里", "鳞次栉比", "车水马龙", "生机勃勃", "心旷神怡", "流连忘返",
    "美不胜收", "抓耳挠腮", "无从下笔", "迫不及待", "勤学苦练", "身临其境",
    "一望无际", "寸草不生", "黄沙漫天", "雨过天晴", "植树造林", "咬紧牙关",
    "心往一处想", "劲往一处使", "十八般武艺", "世上无难事", "只要坚持不懈",
)

def quality_problems(doc, tier):
    """粗检：字数越界 / 空段 / 连续标点 / 段落过短 / 重复句。
    字数按这篇自己选的 target 判定（±5 / +15 容差），doc 里没带 target
    才退回按分档的默认目标。"""
    problems = []
    n = char_count(doc["text"])
    tgt = doc.get("target") or TARGET.get(tier, 400)
    if n < tgt - 28:
        # 下限放得比上限松：素材撑不到高字数档时，483/500 这种
        # "略少 20 字"的实文，好过硬凑出来的水话
        problems.append("字数不足 %d" % n)
    elif n > tgt + 20:
        problems.append("字数超出 %d" % n)
    # 病句检测（九大类）
    for gk, gtip, gfrag in grammar_check(doc["text"]):
        problems.append("病句[%s] %s" % (gk, gfrag))
    sents = []
    for i, p in enumerate(doc["paras"]):
        if not p.strip():
            problems.append("第%d段为空" % (i + 1))
        elif char_count(p) < 8 and not p.endswith("："):
            # 倡议书的"亲爱的同学们："是称呼，单独成行本来就很短
            problems.append("第%d段过短" % (i + 1))
        if re.search(r"[，。；：！？]{2,}", p):
            problems.append("第%d段连续标点" % (i + 1))
        sents.extend(re.split(r"[。！？]", p))
    dup = [s for s in sents if len(s) > 12 and sents.count(s) > 1]
    if dup:
        problems.append("有重复句子")
    hit = [b for b in BANNED if b in doc["text"]]
    if hit:
        problems.append("含模板句：" + "、".join(hit[:3]))
    return problems


def make(theme, tier, rng, tries=80, user_target=None, floor=None):
    """生成一篇合格作文。

    硬性要求：字数、排版、不含模板句，且 4 个固定技巧必须齐。
    另有 1—3 个随机技巧，抽中之后要求至少落地 1 个；实在落不了就放宽，
    但会记进账本，保证长期使用率不超过 35%。
    """
    global _TECH_KEYS
    state = TECH.load_state()
    # 先看这个题材的素材里哪些技巧是真存在的，再从里面抽——
    # 否则抽到"嗅觉"却全文没有一句写气味，只能是空抽
    # 递归收集这个题材所有素材文本（素材结构有三种写法，不能假设层级）
    pool_texts = []

    def _collect(obj):
        if obj is None:
            return
        if isinstance(obj, str):
            pool_texts.append(obj)
            return
        if isinstance(obj, tuple):
            _collect(obj[-1])
            return
        if isinstance(obj, (list, tuple)):
            for x in obj:
                _collect(x)

    _collect(theme.get("paras"))
    _collect(theme.get("variants"))
    for _blk in theme.get("blocks", []):
        _collect(_blk.get("cands"))
        _collect(_blk.get("from"))
    _collect([e[-1] for e in theme.get("extra", [])])

    allowed = TECH.available_keys(pool_texts)
    want = [t["key"] for t in TECH.pick_random_techs(rng, state, allowed)]
    _TECH_KEYS = set(want)

    best = None
    best_score = None
    missing = set()          # 上一轮缺的固定技巧，下一轮加权补上
    # 题材点名的"真细节"：裁句时一句都不许裁（保护句），按档位校验必须出现
    must = theme.get("must") or {}
    _must_all = list(must.get("all") or [])
    for _k in sorted(k for k in must if isinstance(k, int)):
        _must_all += list(must[_k])
    tgt = user_target or TARGET.get(tier, 400)
    for i in range(tries):
        _TECH_KEYS = set(want) | missing
        doc = assemble(theme, tier, rng, _must_all, user_target=user_target,
                       floor=floor)
        # 素材不足时 assemble 会收缩 target，评分和保险都跟着收缩值走
        tgt = doc.get("target") or tgt
        # 字数保险：碎段题材按预算少取句，偶尔会掉到 280 字。这时全取重来一遍，
        # 超出的部分由后面的裁句兜住，总比交一篇短作文强。
        if char_count(doc["text"]) < tgt - 5:
            _more = assemble(theme, tier, rng, _must_all, no_cap=True,
                             user_target=user_target, floor=floor)
            if char_count(_more["text"]) > char_count(doc["text"]):
                doc = _more
        n = char_count(doc["text"])
        skel = TECH.check_skeleton(doc["text"])
        skel_n = sum(1 for v in skel.values() if v)
        fixed = TECH.check_fixed(doc["text"])
        problems = quality_problems(doc, tier)

        # 题材指定的"真细节"必须真的落在文章里（比如跳远那篇"鞋甩到半空"
        # "像一座大山压下来"）。缺了就是又变回模板文，直接换组合重来。
        need = list(must.get("all") or [])
        # 按档位取"最接近本档"的那一组关键句：25 档的点名句不该拿来要求 29 档
        _le = sorted(k for k in must if isinstance(k, int) and k <= tier)
        if _le:
            need += list(must[_le[-1]])
        must_ok = 1 if all(k in doc["text"] for k in need) else 0

        # 备胎评分：真细节 > 骨架齐不齐 > 固定技巧几个 > 问题少 > 字数靠近目标
        score = (must_ok, skel_n, len(fixed), -len(problems), -abs(n - tgt))
        if best is None or score > best_score:
            best, best_score = doc, score

        missing = {t["key"] for t in TECH.FIXED_TECHS if t["key"] not in fixed}

        # 硬门槛：骨架 4 项全齐；固定技巧（比喻/动作分解/对话/对比/心理）至少 3 个
        if not must_ok or problems or skel_n < len(TECH.SKELETON) or len(fixed) < TECH.MIN_FIXED_HIT:
            continue

        # 随机技巧：抽中的至少落地一个
        hit = set(TECH.check_random(doc["text"]))
        landed = [k for k in want if k in hit]
        if not landed:
            # 随机技巧必须真的落进文章，一个都没落就换组合重来
            want = want[:1] if i > tries - 15 else want
            continue

        TECH.record(state, landed)
        TECH.save_state(state)
        _TECH_KEYS = set()
        doc["techs"] = {"skeleton": skel, "fixed": fixed, "want": want,
                        "hit": sorted(hit), "landed": landed}
        return doc

    TECH.record(state, [])
    TECH.save_state(state)
    _TECH_KEYS = set()
    best["techs"] = {"skeleton": TECH.check_skeleton(best["text"]),
                     "fixed": TECH.check_fixed(best["text"]), "want": want,
                     "hit": sorted(TECH.check_random(best["text"])), "landed": []}
    return best


# ============================================================
# 病句检测（九大类，据小学语文常见病句类型整理）
# 每条规则：(正则, 错误类型, 修改建议)
# ============================================================
GRAMMAR_RULES = [
    # 1 搭配不当
    (r"提高[^，。；！？]{0,8}(态度|作风|习惯|效率的方法)", "搭配不当", "「提高」的是成绩/水平，态度用「改进/改善」"),
    (r"(改进|改善)[^，。；！？]{0,8}(成绩|水平|分数|质量)", "搭配不当", "成绩/水平用「提高」"),
    (r"水平[^，。；！？]{0,4}(增长|增加)", "搭配不当", "水平用「提高」"),
    (r"(穿着|戴着)[^，。；！？]{0,6}和[^，。；！？]{0,6}(帽子|衣服)", "搭配不当", "两件东西不能共用一个动词"),
    # 2 成分残缺
    (r"通过[^。；！？]{1,28}使", "成分残缺", "「通过…使…」缺主语，删「使」或「通过」"),
    (r"养成[^，。；！？]{2,12}(卫生|礼貌|好习惯的)$", "成分残缺", "养成…「的习惯」，缺宾语"),
    (r"正在[^，。；！？]{1,15}时候，让我", "成分残缺", "缺主语"),
    # 3 成分赘余
    (r"大约[^，。；！？]{1,12}(左右|上下)", "成分赘余", "「大约」和「左右」删一个"),
    (r"(约|大概)[^，。；！？]{1,10}(左右|上下)", "成分赘余", "约/大概 与 左右 重复"),
    (r"十分[^，。；！？]{0,3}特别|特别[^，。；！？]{0,3}十分", "成分赘余", "两个程度词重复"),
    (r"好像[^，。；！？]{0,3}似乎|似乎[^，。；！？]{0,3}好像", "成分赘余", "重复"),
    (r"大概[^，。；！？]{0,6}差不多|差不多[^，。；！？]{0,6}大概", "成分赘余", "重复"),
    (r"非常[^，。；！？]{0,3}很|很[^，。；！？]{0,3}非常", "成分赘余", "重复"),
    (r"(心里|心中)[^，。；！？]{0,4}由衷", "成分赘余", "由衷本身是发自心里"),
    (r"(亲眼|亲眼目睹)", "成分赘余", "目睹已是亲眼看"),
    (r"(免费赠送|凯旋归来|第一次首创)", "成分赘余", "语义重复"),
    # 4 语序不当
    (r"发扬[^，。；！？]{0,3}和[^，。；！？]{0,3}继承", "语序不当", "先「继承」后「发扬」"),
    (r"广泛地交换了", "语序不当", "应为「交换了广泛的意见」"),
    (r"讨论[^，。；！？]{0,3}和通过了", "语序不当", "先通过后讨论？请核对"),
    # 5 结构混乱（杂糅）
    (r"之所以[^，。；！？]{1,35}的原因", "结构混乱", "「之所以…是因为」与「…的原因」二选一"),
    (r"的原因[^，。；！？]{0,4}是因为", "结构混乱", "「…的原因是…」与「…是因为…」杂糅"),
    (r"(本着|为了)[^，。；！？]{1,15}为原则", "结构混乱", "「本着…原则」/「以…为原则」二选一"),
    (r"(是由|是由于)[^，。；！？]{1,20}(导致的|造成的)", "结构混乱", "二选一"),
    # 6 表意不明
    (r"两个学校的老师", "表意不明", "是「两所学校」还是「两位老师」？"),
    (r"[他她他们她们]和[^，。；！？]{1,6}去他家", "表意不明", "「他」指代不清"),
    # 7 不合逻辑
    (r"防止[^，。；！？]{1,18}不再", "不合逻辑", "「防止…再发生」才对，删「不」"),
    (r"避免[^，。；！？]{1,18}不再", "不合逻辑", "同上，删「不」"),
    (r"幸免[^，。；！？]{0,10}(死难|遇难)", "不合逻辑", "「死难」与「幸免」矛盾"),
    (r"(接近|将近)[^，。；！？]{1,8}(多|余)", "不合逻辑", "「接近」与「多/余」矛盾"),
    (r"最少[^，。；！？]{0,3}以上|至少[^，。；！？]{0,3}以上", "不合逻辑", "「至少」与「以上」矛盾"),
    # 8 关联词
    (r"只要[^，。；！？]{1,25}才", "关联词不当", "「只要…就」/「只有…才」"),
    (r"只有[^，。；！？]{1,25}就", "关联词不当", "「只有…才」/「只要…就」"),
    (r"不但他|不但她", "关联词位置", "应为「他不但…」"),
    (r"他不但[^，。；！？]{1,20}而且他们", "关联词位置", "前后主语一致时「不但」放主语后"),
    (r"虽然[^，。；！？]{1,30}但是所以", "关联词杂糅", "但是/所以 留一个"),
    # 9 标点（一逗到底：一段内连续 7 个逗号无句号）
]


def grammar_check(text):
    """按病句规则扫描，返回 [(类型, 说明, 原句)]。"""
    out = []
    for pat, kind, tip in GRAMMAR_RULES:
        for m in re.finditer(pat, text):
            a = max(0, m.start() - 18)
            b = min(len(text), m.end() + 12)
            frag = text[a:b].replace("\n", "")
            out.append((kind, tip, frag))
    # 一逗到底检测：按段检查连续逗号
    for para in text.split("\n"):
        run = 0
        best = 0
        for ch in para:
            run = run + 1 if ch == "，" else 0
            best = max(best, run)
        if best >= 7:
            out.append(("标点误用", "一逗到底（连续 %d 个逗号没有句号）" % best,
                        para[:40] + "…"))
    return out


def merge_mainlines(theme, rng, take_ratio=0.2):
    """工厂合成：3 条未合成主线，每条取约 20% 的句子做骨架，
    其余靠词库（theme 的 extra 池）在组文时补足。

    规则：
      · 每条主线内部按原句序，等距抽 ~20%（保证不整段照搬）；
      · 三条线的抽中句轮转混排，均匀分进各段（每句一个单档槽）；
      · 题材 must 点名的句子强制保留（否则合成主线过不了真细节校验）；
      · 未抽中的 80% 句子丢弃，字数缺口由 extra（词库句）补；
      · 返回带 "merged": True 的新 theme，不会再参与合成。
    可用主线不足 3 条返回 None。
    """
    mains = []
    if theme.get("paras"):
        mains.append(theme["paras"])
    mains += list(theme.get("variants", []))
    mains = [m for m in mains if not (isinstance(m, dict) and m.get("merged"))]
    if len(mains) < 3:
        return None
    rng.shuffle(mains)
    mains = mains[:3]

    must = theme.get("must") or {}
    must_words = list(must.get("all") or [])
    for _k in sorted(k for k in must if isinstance(k, int)):
        must_words += list(must[_k])

    picked = []          # (tier, text) 保持三线轮转序
    seen = set()
    must_hits = []
    per_line = []
    for m in mains:
        sents = []
        for p in m:
            for slot in p:
                for it in slot:
                    if it[1] not in seen:
                        sents.append((int(it[0]), it[1]))
        n = max(1, round(len(sents) * take_ratio))
        idxs = set(rng.sample(range(len(sents)), min(n, len(sents))))
        chosen = [sents[i] for i in sorted(idxs)]
        for t, txt in chosen:
            seen.add(txt)
        per_line.append(chosen)
        # must 保底：点名句强制入池
        for t, txt in sents:
            if txt in seen:
                continue
            if any(w in txt for w in must_words):
                must_hits.append((t, txt))
                seen.add(txt)

    # 三线轮转混排（保持各线内部句序）
    queues = [list(x) for x in per_line]
    while any(queues):
        for q in queues:
            if q:
                picked.append(q.pop(0))

    # must 保底句插到队首，保证组文时一定被取到
    for t, txt in reversed(must_hits):
        picked.insert(0, (t, txt))

    # 均匀分到 N 段（N = 最长骨架的段数）
    n_para = max(len(m) for m in mains)
    paras = [[] for _ in range(n_para)]
    for k, (t, txt) in enumerate(picked):
        paras[k % n_para].append([(t, txt)])

    if isinstance(theme["title"], list):
        new_title = [theme["title"][0], "合成 · " + theme["title"][1]]
    else:
        new_title = [theme["title"], "合成版"]
    return {
        "title": new_title,
        "paras": paras,
        "extra": list(theme.get("extra", [])),   # 剩下的靠词库补
        "must": must,
        "merged": True,
    }
