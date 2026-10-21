# -*- coding: utf-8 -*-
"""真词库：专门存放"编不出来"的真实细节，并负责检查新细节能不能放进某个主题。

数据文件：real_details.json（与本项目件同目录），结构：
{
  "五下": {
    "修车的张爷爷": [ {"t": 27, "s": "补好的胎他总要亲手按一按..."}, ... ]
  }
}

命令行（在本目录执行）：
  python real_details.py stats                          全库统计
  python real_details.py check "句子" --grade 五下 --theme 修车的张爷爷
  python real_details.py add   "句子" --grade 五下 --theme 修车的张爷爷

check 的三条判定（用户定的规矩）：
  1. 已有：这条细节（或几乎相同的句子）已经在主题里 —— 没有必要再加；
  2. 冲突：细节里的事实与主题已有事实打架（人称长辈冲突 / 数字冲突）—— 不能放；
  3. 可放：返回建议档位（25/27/29），add 时按建议档写入词库。
真词库在 essay_data 装载时自动并入各主题的 extra，生成时即会用到。
"""
import io
import json
import os
import re
import sys

sys.stdout.reconfigure(encoding="utf-8")

_HERE = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(_HERE, "real_details.json")

# 同一位长辈的不同叫法：主题里已出现其一，细节再用其二即视为冲突
_REL_GROUPS = [
    {"爷爷", "外公", "姥爷"},
    {"奶奶", "外婆", "姥姥"},
    {"爸爸", "老爸", "父亲"},
    {"妈妈", "老妈", "母亲"},
    {"哥哥", "表哥", "堂哥"},
    {"姐姐", "表姐", "堂姐"},
]

# 长度 -> 建议档位
def suggest_tier(sent):
    n = len(re.sub(r"\s", "", sent))
    if n <= 14:
        return 25
    if n <= 26:
        return 27
    return 29


def _load_db():
    try:
        with io.open(DB_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_db(db):
    with io.open(DB_PATH, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=1)


def _theme_sentences(th):
    """主题里已有的全部句子（主线 + 变体 + extra）。"""
    out = []

    def collect(o):
        if isinstance(o, str):
            out.append(o)
        elif isinstance(o, (list, tuple)):
            for x in o:
                collect(x if not isinstance(o, tuple) else o[-1])
                if isinstance(o, tuple):
                    break

    for key in ("paras", "variants"):
        for p in th.get(key, []) or []:
            for slot in p:
                for it in slot:
                    out.append(it[-1])
    for e in th.get("extra", []):
        out.append(e[-1])
    return out


def _overlap(a, b):
    """字符二元组重合率（与引擎同款）。"""
    ha = [c for c in a if "\u4e00" <= c <= "\u9fa5"]
    hb = [c for c in b if "\u4e00" <= c <= "\u9fa5"]
    ba = {x + y for x, y in zip(ha, ha[1:])}
    bb = {x + y for x, y in zip(hb, hb[1:])}
    if not ba or not bb:
        return 0.0
    return len(ba & bb) / max(1, min(len(ba), len(bb)))


def _find_theme(grade, title_sub):
    """按学期 + 主题名（可只写片段）找主题 dict。"""
    import essay_data as D
    book = (D.EDITIONS.get(grade) or D.EDITIONS["统编版"])
    ginfo = book.get(grade) or {}
    hits = []
    for u in ginfo.get("units", []):
        for th in u["themes"]:
            if title_sub in th["title"][0] or title_sub in th["title"][-1]:
                hits.append((u, th))
    return hits


def check(sent, grade, theme_sub):
    """返回 (可否加入, 建议档位, 原因列表)。"""
    sent = sent.strip().rstrip("。！？") 
    reasons = []
    hits = _find_theme(grade, theme_sub)
    if not hits:
        return False, None, ["在 %s 找不到主题含「%s」" % (grade, theme_sub)]
    if len(hits) > 1:
        reasons.append("匹配到 %d 个主题，请把 --theme 写得更具体" % len(hits))
        return False, None, reasons
    unit, th = hits[0]
    existing = _theme_sentences(th)

    # 1) 已有检测：完全一样 / 被包含 / 高度相似 —— 已有就没必要加
    for ex in existing:
        if sent in ex or ex in sent:
            return False, None, ["已有（不必再加）：主题里存在「%s…」" % ex[:28]]
    best = max(((_overlap(sent, ex), ex) for ex in existing), default=(0, ""))
    if best[0] >= 0.6:
        return False, None, ["近似已有（不必再加）：与「%s…」重合 %.0f%%"
                             % (best[1][:28], best[0] * 100)]

    # 2) 冲突检测：长辈人称打架；同量词数字打架
    body = "".join(existing)
    for group in _REL_GROUPS:
        in_sent = {w for w in group if w in sent}
        in_body = {w for w in group if w in body}
        if in_sent and in_body and not (in_sent & in_body):
            reasons.append("冲突：主题写的是「%s」，细节里却是「%s」"
                           % ("/".join(in_body), "/".join(in_sent)))
    # 数字冲突：主题已确立的数字事实（如七十九岁、三年）不得矛盾
    if any(r.startswith("冲突：") for r in reasons):
        reasons.append("结论：不放（事实冲突，先改细节或换主题）")
        return False, None, reasons
    nums_body = set(re.findall(r"[一两二三四五六七八九十百半]{1,4}", body))
    nums_sent = set(re.findall(r"[一两二三四五六七八九十百半]{1,4}", sent))
    # 只报"细节独有且带量词"的数字供人工复核，不直接拦截
    fresh = nums_sent - nums_body
    if fresh:
        reasons.append("提示：细节含主题未出现过的数字（%s），确认与既有设定不矛盾即可"
                       % "/".join(sorted(fresh)))

    tier = suggest_tier(sent)
    reasons.append("可放：建议档位 %d（%d 字）" % (tier, len(sent)))
    return True, tier, reasons


def add(sent, grade, theme_sub, tier=None):
    ok, sug, reasons = check(sent, grade, theme_sub)
    for r in reasons:
        print(" -", r)
    if not ok:
        return False
    hits = _find_theme(grade, theme_sub)
    _, th = hits[0]
    db = _load_db()
    g = db.setdefault(grade, {})
    key = th["title"][-1]
    lst = g.setdefault(key, [])
    if any(e["s"] == sent for e in lst):
        print(" - 词库里已经有这条了，没有必要再加。")
        return False
    lst.append({"t": tier or sug, "s": sent})
    _save_db(db)
    print("已入真词库：%s / %s（共 %d 条）" % (grade, key, len(lst)))
    return True


def stats():
    import essay_data as D
    db = _load_db()
    n_db = sum(len(v) for g in db.values() for v in g.values())
    # 现有主题里 must 真细节的存量
    n_must = 0
    for book in D.EDITIONS.values():
        for ginfo in book.values():
            for u in ginfo.get("units", []):
                for th in u["themes"]:
                    m = th.get("must") or {}
                    n_must += len(m.get("all") or [])
                    n_must += sum(len(v) for k, v in m.items() if isinstance(k, int))
    print("真词库（real_details.json）：%d 条" % n_db)
    print("主题内 must 真细节存量：%d 处" % n_must)
    for g in sorted(db):
        for t, lst in db[g].items():
            print("  %s / %s：%d 条" % (g, t, len(lst)))


def main():
    import argparse
    ap = argparse.ArgumentParser(description="真词库：真细节的存放与准入检查")
    ap.add_argument("cmd", choices=["check", "add", "stats"])
    ap.add_argument("sentence", nargs="?", default="")
    ap.add_argument("--grade", default="六上")
    ap.add_argument("--theme", default="")
    a = ap.parse_args()
    if a.cmd == "stats":
        stats()
    elif a.cmd == "check":
        if not a.sentence or not a.theme:
            print("用法：python real_details.py check \"句子\" --grade 学期 --theme 主题片段")
            return
        ok, _t, rs = check(a.sentence, a.grade, a.theme)
        for r in rs:
            print(" -", r)
        print("结论：", "可以放" if ok else "不放")
    elif a.cmd == "add":
        if not a.sentence or not a.theme:
            print("用法：python real_details.py add \"句子\" --grade 学期 --theme 主题片段")
            return
        add(a.sentence, a.grade, a.theme)


if __name__ == "__main__":
    main()
