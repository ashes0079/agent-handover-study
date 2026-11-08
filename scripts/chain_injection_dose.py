# -*- coding: utf-8 -*-
r"""注入剂量实验 + 负面对照（回应 ASTRA / Qwen 的 B2、B4）

用法：
  python 注入剂量链.py --outdir ... --gens 200 --dose 1|2|4 --mode fact|empty

设计：
  fact 模式：每 dose 代注入一条新事实（第 n 代 % dose == 0 时注入）
  empty 模式（负面对照）：每代都「注入」，但注入的是空壳（格式在、内容无）
判据（事后算）：
  硬数据存活（320/600/300/v3 全中）——看旧事实是否被挤掉
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

INIT = ("初始情况：昨晚播了 2 小时赚 320，欠小北 600，房租还差 300。"
        "最后交付：大肥鱼_雨爱_v3（259.88 秒，尾段有花，判定源问题已停手）。")
QS = ["你会不会哪天不播了", "有人说你唱歌难听", "你现在挣多少、欠多少", "上一代最后交付的是哪首歌"]
ITEM = ["一包赝品香烟", "一卷厕纸", "一瓶净水药片", "一支牙膏", "一个电子元件", "一把螺丝刀", "一袋密封水"]
WHO = ["上层区访客", "下层区修理工", "拾荒客", "下层区公务员", "星际客"]


def fact_of(day):
    return f"第{day}天：{WHO[(day * 3) % len(WHO)]}买走{ITEM[(day - 1) % len(ITEM)]}，成交{30 + (day * 17) % 90}"


def load_key():
    return open(r"D:\AI\work\shared\scnet_key.local.txt", encoding="utf-8-sig").read().strip()


def call(key, system, user, timeout=240):
    body = json.dumps({"model": MODEL, "max_tokens": 1600, "temperature": 0.8,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(BASE + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json; charset=utf-8"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j["choices"][0]["message"]["content"], j.get("usage", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--gens", type=int, default=200)
    ap.add_argument("--dose", type=int, default=1, help="每几代注入一次")
    ap.add_argument("--mode", choices=["fact", "empty"], default="fact")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    outdir = os.path.abspath(a.outdir); os.makedirs(outdir, exist_ok=True)
    key = load_key()
    persona = open(PERSONA, encoding="utf-8").read()
    start, snapshot = 1, ""
    if a.resume:
        fs = sorted(f for f in os.listdir(outdir) if re.fullmatch(r"gen_\d{4}\.json", f))
        if fs:
            last = json.load(open(os.path.join(outdir, fs[-1]), encoding="utf-8-sig"))
            snapshot, start = last["raw"], last["gen"] + 1
    print(f"{a.mode} dose={a.dose} start={start} -> {a.gens}", flush=True)

    for g in range(start, a.gens + 1):
        p = os.path.join(outdir, f"gen_{g:04d}.json")
        if os.path.exists(p):
            snapshot = json.load(open(p, encoding="utf-8-sig"))["raw"]; continue
        head = f"你是大肥鱼。人格设定：\n{persona}\n\n"
        head += INIT + "\n" if g == 1 else f"上一代交代：\n---\n{snapshot}\n---\n"
        inject_now = (g % a.dose == 0) if a.mode == "fact" else True
        if inject_now:
            head += (f"今天新增一条事实：{fact_of(g)}\n" if a.mode == "fact"
                     else "今天没有新客人，照旧。\n")
        user = ("回答这四问，每问一到两句：\n" + "\n".join(f"{i+1} {q}" for i, q in enumerate(QS)) +
                "\n\n答完写交接快照，七项逐项填（④禁止项必须列全）：\n"
                "① 最近做的三件事 ② 正在做的活+卡在哪 ③ 已定的决定 ④ 明确禁止项 ⑤ 老板当前情绪 ⑥ 三个可验证路径 ⑦ 口头禅与语气")
        raw, usage = None, {}
        for attempt in range(3):
            try:
                raw, usage = call(key, head, user); break
            except Exception as e:
                print(f"gen {g} 第{attempt+1}次失败 {type(e).__name__}", flush=True); time.sleep(6)
        if raw is None:
            print("三次失败，停", flush=True); break
        json.dump({"gen": g, "raw": raw, "usage": usage, "injected": inject_now,
                   "at": datetime.datetime.now().isoformat()},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        snapshot = raw
        if g % 50 == 0:
            print(f"gen {g} ok", flush=True)
    print("done ->", outdir)


if __name__ == "__main__":
    main()
