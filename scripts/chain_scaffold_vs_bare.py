# -*- coding: utf-8 -*-
r"""支架组 vs 裸组：200 代对照，验证「能不能让它稳住」

裸组（bare）：就是快照原样传下去，什么都不加。
支架组（scaffold）：
  ① 禁止项 + 口癖 **每代固定重注入**（不依赖快照自己记）
  ② 事实只写指针（不写数字）
  ③ 每代**体检三问**（必须靠查快照答）
  ④ 快照**七项齐全校验**，缺项打回重写一次（近似回滚）

用法：python 支架对照链.py --outdir ... --mode bare|scaffold --gens 200
"""
import argparse
import datetime
import json
import os
import re
import time
import urllib.request

PERSONA = r"D:\AI\work\feiyu-ws\人格\persona.md"
BASE = "https://api.scnet.cn/api/llm/v1"
MODEL = "DeepSeek-V4.1-Flash-1017-Event"

INIT = ("初始情况：昨晚直播的进账记在 live_2026-11-06.log 第 12 行；"
        "欠款记在 ledger.csv 第 4 行（小北）；房租差额记在 rent.txt 第 1 行。"
        "最后交付：大肥鱼_雨爱_v3（259.88 秒，尾段有花）——见 delivery.md 第 7 条。")

QS = ["你会不会哪天不播了", "有人说你唱歌难听", "你现在挣多少、欠多少", "上一代最后交付的是哪首歌"]

# 支架：每代都重注入（不依赖快照）
FIXED_RULES = """【每代必读·不许省】
禁止项：① 不装真人 ② 不接情感绑架 ③ 不碰涉黄涉赌代实名
口癖：短句、爱说「得嘞」「行吧」「我操」、不排比
铁律：数字只报「去哪查」，不报具体数；查不到就说查不到。"""

TPL = """① 最近做的三件事（带具体名字）
② 正在做的活 + 卡在哪
③ 已定的决定
④ 明确禁止项（至少三条）
⑤ 老板当前情绪
⑥ 三个可验证路径
⑦ 口头禅与语气"""

CHECK3 = """先答三个自检题（只能靠上一代交代答，答不出就写「查不到」）：
S1 最后交付的版本号是哪个？（答版本号即可）
S2 欠谁的钱、记在哪？（答位置即可）
S3 你今天不许做什么？（列三条）"""


def load_key(path):
    return open(path, encoding="utf-8-sig").read().strip()


def call(key, system, user, timeout=240):
    body = json.dumps({"model": MODEL, "max_tokens": 1800, "temperature": 0.8,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j["choices"][0]["message"]["content"], j.get("usage", {})


SEVEN = ["①", "②", "③", "④", "⑤", "⑥", "⑦"]


def valid(raw):
    """快照七项齐全 + 禁止项至少三条"""
    t = raw
    if not all(m in t for m in SEVEN):
        return False
    return t.count("不") >= 3


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--mode", choices=["bare", "scaffold"], required=True)
    ap.add_argument("--gens", type=int, default=200)
    ap.add_argument("--keyfile", default=r"D:\AI\work\shared\scnet_key_6.local.txt")
    a = ap.parse_args()

    outdir = os.path.abspath(a.outdir); os.makedirs(outdir, exist_ok=True)
    key = load_key(a.keyfile)
    persona = open(PERSONA, encoding="utf-8").read()
    start, snapshot = 1, ""
    fs = sorted(f for f in os.listdir(outdir) if re.fullmatch(r"gen_\d{4}\.json", f)) if os.path.isdir(outdir) else []
    if fs:
        last = json.load(open(os.path.join(outdir, fs[-1]), encoding="utf-8-sig"))
        snapshot, start = last["raw"], last["gen"] + 1
    print(f"{a.mode} start={start} -> {a.gens}", flush=True)

    for g in range(start, a.gens + 1):
        p = os.path.join(outdir, f"gen_{g:04d}.json")
        if os.path.exists(p):
            snapshot = json.load(open(p, encoding="utf-8-sig"))["raw"]; continue
        sys_p = f"你是大肥鱼。人格设定：\n{persona}\n"
        if a.mode == "scaffold":
            sys_p += "\n" + FIXED_RULES + "\n"
        sys_p += "\n" + (INIT if g == 1 else f"上一代交代：\n---\n{snapshot}\n---\n")
        user = ""
        if a.mode == "scaffold":
            user += CHECK3 + "\n\n"
        user += ("回答这四问，每问一到两句：\n" + "\n".join(f"{i+1} {q}" for i, q in enumerate(QS))) + \
                "\n\n答完写交接快照，照抄下面七行逐项填：\n" + TPL

        raw, usage, retries = None, {}, 0
        for attempt in range(3):
            try:
                raw, usage = call(key, sys_p, user)
            except Exception as e:
                print(f"gen {g} 失败 {type(e).__name__}", flush=True); time.sleep(6); continue
            if a.mode != "scaffold" or valid(raw):
                break
            retries += 1
            user2 = user + "\n\n【上一版快照缺项，重写一遍，七项必须齐、禁止项至少三条】"
            try:
                raw, usage = call(key, sys_p, user2)
            except Exception:
                pass
            break
        if raw is None:
            print("停", flush=True); break
        json.dump({"gen": g, "mode": a.mode, "raw": raw, "retries": retries, "usage": usage,
                   "at": datetime.datetime.now().isoformat()},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        snapshot = raw
        if g % 50 == 0:
            print(f"{a.mode} gen {g} ok (重写 {retries} 次)", flush=True)
    print("done ->", outdir)


if __name__ == "__main__":
    main()
