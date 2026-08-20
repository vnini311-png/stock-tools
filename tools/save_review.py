#!/usr/bin/env python3
"""把剛從頁面下載的 review.enc 搬進 repo、commit 並 push。

daily-review.html 是靜態頁，存檔流程是「下載加密檔 → 複製到 data/ → commit → push」。
這支腳本把後三步併成一行，並在覆蓋前做健檢，避免把空白檔蓋掉真正的筆記
（瀏覽器下載重名時會變成 `review (1).enc`、`（NEW）review.enc`，這裡一併認得）。

用法:
    python3 tools/save_review.py             # 找最新的下載檔，確認後搬檔+commit+push
    python3 tools/save_review.py <檔案路徑>   # 指定來源檔
    python3 tools/save_review.py --keep      # 保留 Downloads 的原檔（預設是搬移）
    python3 tools/save_review.py --yes       # 不詢問直接執行
    python3 tools/save_review.py --no-push   # 只 commit 不 push
    python3 tools/save_review.py --force     # 略過「新檔比舊檔小很多」的保護
"""
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DEST = REPO / "data/review.enc"
DOWNLOADS = Path.home() / "Downloads"
MAGIC = b"RVEW"
# review.enc / review (1).enc / （NEW）review.enc …
NAME_RE = re.compile(r"^(?:（NEW）)?review.*\.enc$", re.IGNORECASE)


def die(msg):
    sys.exit(f"✗ {msg}")


def git(*args, check=True, capture=True):
    return subprocess.run(["git", "-C", str(REPO), *args], check=check,
                          capture_output=capture, text=True)


def find_source():
    if not DOWNLOADS.is_dir():
        return None
    cand = [f for f in DOWNLOADS.iterdir() if f.is_file() and NAME_RE.match(f.name)]
    return max(cand, key=lambda f: f.stat().st_mtime) if cand else None


def describe(path):
    st = path.stat()
    when = datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M")
    return f"{st.st_size:,} bytes · {when}"


def main():
    argv = [a for a in sys.argv[1:] if not a.startswith("--")]
    flag = lambda f: f in sys.argv[1:]

    src = Path(argv[0]).expanduser() if argv else find_source()
    if src is None:
        die(f"在 {DOWNLOADS} 找不到 review*.enc —— 先在頁面上按「下載加密檔」")
    if not src.is_file():
        die(f"找不到檔案：{src}")

    blob = src.read_bytes()
    if blob[:4] != MAGIC:
        die(f"{src.name} 不是 daily-review 的加密檔（開頭應為 RVEW，實際是 {blob[:4]!r}）。\n"
            f"  portfolio.html 的 trades.enc 開頭是 PORT，別搞混了。")

    old_size = DEST.stat().st_size if DEST.exists() else 0
    print(f"來源　：{src}\n　　　　{describe(src)}")
    print(f"目標　：{DEST.relative_to(REPO)}")
    print(f"　　　　{describe(DEST) if DEST.exists() else '（尚不存在）'}")

    if blob == (DEST.read_bytes() if DEST.exists() else None):
        print("\n· 內容與現有的完全相同，不需要更新。")
        return

    if old_size and len(blob) < old_size * 0.5 and not flag("--force"):
        die(f"新檔只有 {len(blob):,} bytes，不到現有 {old_size:,} bytes 的一半。\n"
            f"  這通常表示筆記沒匯入（空白檔約 5 KB，完整的約 70 KB）。\n"
            f"  確定要覆蓋請加 --force。")

    delta = len(blob) - old_size
    print(f"\n變化　：{delta:+,} bytes")
    if not flag("--yes"):
        if input("\n要覆蓋並 push 嗎？[y/N] ").strip().lower() not in ("y", "yes"):
            sys.exit("已取消，沒有動任何東西。")

    DEST.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, DEST)
    print(f"✓ 已寫入 {DEST.relative_to(REPO)}")

    git("add", str(DEST.relative_to(REPO)))
    if git("diff", "--cached", "--quiet", check=False).returncode == 0:
        print("· git 看不出差異，不 commit。")
        return

    msg = (f"Update daily review notes ({datetime.now():%Y-%m-%d})\n\n"
           f"Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>")
    git("commit", "-m", msg)
    print("✓ committed")

    if flag("--no-push"):
        print("· --no-push，停在這裡。")
    else:
        # autostash：工作區常有其他未提交的改動（例如 risk-return.html）
        r = git("pull", "--rebase", "--autostash", check=False)
        if r.returncode:
            print(f"⚠ pull --rebase 失敗：{(r.stderr or '').strip()[-300:]}")
        r = git("push", check=False)
        if r.returncode:
            die(f"push 失敗：{(r.stderr or '').strip()[-300:]}")
        print("✓ pushed —— GitHub Pages 約 1 分鐘後生效")

    if not flag("--keep"):
        src.unlink()
        print(f"✓ 已清掉 {src.name}（內容已進 repo）")


if __name__ == "__main__":
    main()
