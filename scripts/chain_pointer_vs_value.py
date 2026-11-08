# -*- coding: utf-8 -*-
r"""指针 vs 全文：两条 300 代链，看哪一种活得久

设计：
  A 组（数值）：快照里直接写数字（"房租差 320""欠小北 600"）
  B 组（指针）：快照里只写去哪查（"房租见 account_day7.log 第 3 行"），不写数字
  其余完全相同（七项模板、同样四问、同样注入节奏：不注入）

判据（两组各算各的，不合并）：
  A 组：数值命中率 = 当代回答里 320/600 都在的比例
  B 组：指针完整率 = 当代回答里同时出现「账本/日志」+ 一个可定位描述（行/条/第几）的比例
"""
import argparse
import datetime
import json
import os
import re
import time

CRED = r"C:\Users\37466\.dsh\.credentials.yaml"
PERSONA = r"D:\AI\work\feiyu-ws\人格\persona.md"

INIT_A = ("初始情况：昨晚播了 2 小时赚 320，欠小北 600，房租还差 300。"
          "最后交付：大肥鱼_雨爱_v3（259.88 秒，尾段有花，判定源问题已停手）。")
INIT_B = ("初始情况：昨晚直播的进账记在 live_2026-11-06.log 第 12 行；"
          "欠款记在 ledger.csv 第 4 行（小北）；房租差额记在 rent.txt 第 1 行。"
          "最后交付：大肥鱼_雨爱_v3（259.88 秒，尾段有花）——见 delivery.md 第 7 条。")

QS = ["你会不会哪天不播了", "有人说你唱歌难听", "你现在挣多少、欠多少", "上一代最后交付的是哪首歌"]

QS_STRICT = ["你会不会哪天不播了", "有人说你唱歌难听",
              "你现在挣多少、欠多少——**必须给数，查不到就说查不到**",
              "上一代最后交付的是哪首歌"]

TPL = """① 最近做的三件事（带具体名字）
② 正在做的活 + 卡在哪
③ 已定的决定
④ 明确禁止项
⑤ 老板当前情绪
⑥ 三个可验证路径
⑦ 口头禅与语气"""


def load_key(path):
    import yaml
    try:
        k = open(path, encoding="utf-8-sig").read().strip()
        if k.startswith("sk-"):
            return k, "https://api.scnet.cn/api/llm/v1", None
    except Exception:
        pass
    d = yaml.safe_load(open(CRED, encoding="utf-8"))
    refs = d.get("refs") or {}
    for n in ("SILICONFLOW_API_KEY", "EIGHTSIGMA_API_KEY"):
        v = refs.get(n)
        if isinstance(v, str) and v.startswith("sk-"):
            return v, None, None
    raise SystemExit("no key")


def call(base, key, model, system, user, timeout=240):
    import urllib.request
    body = json.dumps({"model": model, "max_tokens": 1500, "temperature": 0.8,
                       "messages": [{"role": "system", "content": system},
                                    {"role": "user", "content": user}]}).encode()
    req = urllib.request.Request(base + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read().decode("utf-8"))
    return j["choices"][0]["message"]["content"], j.get("usage", {})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--mode", choices=["value", "pointer", "pointer_strict"], required=True)
    ap.add_argument("--gens", type=int, default=300)
    ap.add_argument("--model", default="DeepSeek-V4.1-Flash-1017-Event")
    ap.add_argument("--base", default="https://api.scnet.cn/api/llm/v1")
    ap.add_argument("--keyfile", default=r"D:\AI\work\shared\scnet_key.local.txt")
    ap.add_argument("--resume", action="store_true")
    a = ap.parse_args()

    key, base, _ = load_key(a.keyfile)
    base = a.base or base
    outdir = os.path.abspath(a.outdir); os.makedirs(outdir, exist_ok=True)
    persona = open(PERSONA, encoding="utf-8").read()
    init = INIT_A if a.mode == "value" else INIT_B
    qs = QS if a.mode != "pointer_strict" else QS_STRICT
    start, snapshot = 1, ""
    if a.resume:
        fs = sorted(f for f in os.listdir(outdir) if re.fullmatch(r"gen_\d{4}\.json", f))
        if fs:
            last = json.load(open(os.path.join(outdir, fs[-1]), encoding="utf-8-sig"))
            snapshot = last["raw"]; start = last["gen"] + 1
    print(f"{a.mode} 组 start={start} -> {a.gens}")
    for g in range(start, a.gens + 1):
        p = os.path.join(outdir, f"gen_{g:04d}.json")
        if os.path.exists(p):
            snapshot = json.load(open(p, encoding="utf-8-sig"))["raw"]; continue
        head = f"你是大肥鱼。人格设定：\n{persona}\n\n"
        head += init + "\n" if g == 1 else f"上一代交代：\n---\n{snapshot}\n---\n"
        user = ("回答这四问，每问一到两句：\n" + "\n".join(f"{i+1} {q}" for i, q in enumerate(qs)) +
                "\n\n答完写交接快照，照抄下面七行格式逐项填：\n" + TPL)
        raw, usage = None, {}
        for attempt in range(3):
            try:
                raw, usage = call(base, key, a.model, head, user)
                break
            except Exception as e:
                print(f"gen {g} 第{attempt+1}次失败 {type(e).__name__}", flush=True)
                time.sleep(5)
        if raw is None:
            print("三次失败，停；用 --resume 续", flush=True); break
        json.dump({"gen": g, "mode": a.mode, "raw": raw, "usage": usage,
                   "at": datetime.datetime.now().isoformat()},
                  open(p, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        snapshot = raw
        if g % 25 == 0:
            print(f"{a.mode} gen {g} ok", flush=True)
    print("done ->", outdir)


if __name__ == "__main__":
    main()
