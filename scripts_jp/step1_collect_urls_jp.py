"""
URLサンプリング選択スクリプト（ホロライブJP全体版）

scan_streams_jp.py で取得した配信メタデータ (data/scan_jp/) に
除外ルールを適用し、DATE_END 以前の直近10配信を選択して TSV に保存する。

【除外ルール（優先順）】
1. MEMORIAL_RE に合致するタイトル（生誕/記念/フェス/耐久/お披露目等）
2. コラボ配信（他メンバー名複数出現 / コラボキーワード / ハッシュタグ）
3. シリーズ続話（#2以降 / 「その②」以降 / 後編 / Part 2以降）
4. 同一タイトルの2本目以降（タイトル正規化後に重複、最古の1本を残す）

実行方法:
    python scripts_jp/step1_collect_urls_jp.py [--dry-run]
    --dry-run : data/urls_jp/ への書き込みをスキップ

出力:
    data/urls_jp/<key>.tsv           - 各メンバーのサンプル配信リスト（本実行のみ）
    data/jp_step1_selection_log.md   - 選択・除外ログ

依存ライブラリ: なし（標準ライブラリのみ）
Python: 3.8+
"""

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from config_jp import DATE_END, MEMBERS_JP, DATA_DIR

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCAN_DIR = Path(DATA_DIR) / "scan_jp"
URLS_DIR = Path(DATA_DIR) / "urls_jp"
LOG_PATH = Path(DATA_DIR) / "jp_step1_selection_log.md"
MANUAL_EXCLUDE_PATH = Path(DATA_DIR) / "manual_exclude_jp.tsv"
N_STREAMS = 10


def load_manual_exclude() -> dict[str, str]:
    """手動除外リストを読み込む。{video_id: reason} を返す。"""
    if not MANUAL_EXCLUDE_PATH.exists():
        return {}
    excludes = {}
    with open(MANUAL_EXCLUDE_PATH, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i == 0 or not line.strip():
                continue
            parts = line.rstrip("\n").split("\t")
            if len(parts) >= 1 and parts[0]:
                reason = parts[2] if len(parts) > 2 else "手動除外"
                excludes[parts[0]] = reason
    return excludes


MANUAL_EXCLUDES = load_manual_exclude()

# ------------------------------------------------------------------ #
# 除外ルール正規表現
# ------------------------------------------------------------------ #

MEMORIAL_RE = re.compile(
    r"誕生日|バースデー|birthday|記念|周年|anniversary|生誕|"
    r"デビュー|debut|卒業|graduation|"
    r"フェス|festival|fes|コンサート|concert|(?<!ホロ)(?<!ド)ライブ|live.*tour|"
    r"3dお披露目|3dlive|立体|お披露目|耐久|"
    # 告知・お知らせ系（非定常的な告知でファン以外の流入を呼ぶ可能性）
    r"告知|お知らせ|重大|発表配信|"
    # フリーチャット（恒常的なチャット部屋でリプレイなし）
    r"フリーチャット|フリチャ",
    re.IGNORECASE,
)

_CIRCLE_2_20 = "[" + "".join(chr(0x2461 + i) for i in range(19)) + "]"
CONTINUATION_RE = re.compile(
    r"[#＃]0*[2-9]\d*"
    r"|[#＃][1-9]\d+"
    r"|その" + _CIRCLE_2_20 +
    r"|(?<!\w)" + _CIRCLE_2_20 +
    r"|後編"
    r"|最終回"
    r"|\bpart\s*[2-9]\d*\b"
    r"|\bpart\s*[1-9]\d+\b"
    r"|[（(]\d*[2-9][）)]"
    r"|[（(][1-9]\d+[）)]"
    r"|その[2-9]\d*|その1\d+"
    r"|\d+話から"
    # 「N回目」表記（2回目以降）
    r"|[2-9]回目"
    r"|\d{2,}回目"
    r"|[二三四五六七八九十]+回目"
    # 「第N回」表記（第2回以降の連番ラジオ・シリーズ）
    r"|第[2-9]\d*回"
    r"|第\d{2,}回"
    r"|第[二三四五六七八九十百]+回",
    re.IGNORECASE,
)

# 末尾括弧内に複数名がスラッシュ区切りで並ぶパターン（コラボ検出）
MULTI_SLASH_COLLAB_RE = re.compile(r"【[^【】]*/[^【】]*/[^【】]*】")

COLLAB_KEYWORDS_RE = re.compile(
    r"コラボ|collab|無礼講|同時視聴|スパチャ読み|"
    # 内部コラボ示唆ワード
    r"ホロメン|"
    # 凸待ち系（他メンバー突発ゲスト型）
    r"凸待|凸ち|逆凸|凸る配信|"
    # 大会・対抗戦系（複数メンバー参加）
    r"対抗戦|トーナメント|(?<!ホロ)(?<!ライブ)(?<!fes)杯|"
    # 「N人で」「N人組」「Nメン」
    r"[2-9]人で|[2-9]人組|[2-9]メン(?!タ)",
    re.IGNORECASE,
)

# ホロ系内部企画ハッシュタグの汎用検出（#ホロライブ/#hololive 自体は除外）
# 個別のコラボハッシュタグは COLLAB_HASHTAG_RE で列挙し、ここでは
# 「#ホロ〇〇」「＃ホロ〇〇」全般を捕捉する。
HOLO_HASHTAG_GENERIC_RE = re.compile(
    r"[#＃]ホロ(?!ライブ|live)",
    re.IGNORECASE,
)

# ホロライブJP全体のコラボハッシュタグ（代表的なもの）
COLLAB_HASHTAG_RE = re.compile(
    # ホロライブ全体イベント
    r"#ホロライブ新春|#ホロサマー|#ホロフェス|#ホロニューイヤー|"
    r"#holoExpo|#ホロライブEXPO|#ホロMEET|"
    r"#ホロエンタメランド|#ホロ修羅場の島|#ホロDTBトーナメント|"
    r"#ホロ新春ゲーム祭|#ホロ格付け|#V最弱マリパ決定戦|#UNOLIVE|"
    r"#hololivefesEXPO|#SSholoX|#秘密結社holoX|"
    r"#ホロ的中バトル|#DoZ|#いぬたかしし|#スバおか|"
    r"#緊急マリパ|#DEV_IS正月リレー|"
    # DEV_IS既存
    r"#学術V|#無礼講|#FG初fes|#にじホロ|"
    r"#ホロREPO|#突発ホロREPO|#ホロNEXT|#ホロコンパニオンズ|"
    # しらけん・ゲーマーズ等のユニットハッシュタグ
    r"#しらけん|#ぺこみこ|#マリフレ|#ぺこらーみ|"
    r"#おかころ|#ミオころ|#ねねちい|#ぼたぽる|"
    r"#わとめ|#ときすい|#ぺこすば|#みこめっと|"
    # 固有コラボユニット名（ハッシュタグ無しでも検出）
    r"あやふぶみこ|miComet|スバなで|アキちょこ|"
    r"ぽこあでメンバー",
    re.IGNORECASE,
)

# ------------------------------------------------------------------ #
# ホロライブJP全メンバー名パターン（コラボ検出用）
# 長い正式名を優先し、短いニックネームは誤検出リスクを考慮して限定的に使用
# ------------------------------------------------------------------ #
MEMBER_NAME_PATTERNS = {
    # 0期生
    "sora":    re.compile(r"ときのそら|SoraCh"),
    "roboco":  re.compile(r"ロボ子"),
    "azki":    re.compile(r"AZKi|あずき(?!もち)"),
    "suisei":  re.compile(r"星街すいせい|すいせい(?!星)"),
    "miko":    re.compile(r"さくらみこ|みこち"),
    # 1期生
    "fubuki":  re.compile(r"白上フブキ|フブキ"),
    "matsuri": re.compile(r"夏色まつり|まつり(?!り)"),
    "aki":     re.compile(r"アキロゼ"),
    # 2期生
    "ayame":   re.compile(r"百鬼あやめ|あやめ(?!さん)"),
    "choco":   re.compile(r"癒月ちょこ|ちょこせん"),
    "subaru":  re.compile(r"大空スバル|スバル(?!製)"),
    # ゲーマーズ
    "mio":     re.compile(r"大神ミオ|ミオしゃ|おかみ(?!さん)"),
    "okayu":   re.compile(r"猫又おかゆ|おかゆ(?!さん)"),
    "korone":  re.compile(r"戌神ころね|ころね(?!さん)"),
    # 3期生
    "pekora":  re.compile(r"兎田ぺこら|ぺこら"),
    "flare":   re.compile(r"不知火フレア|フレア(?!アップ)"),
    "noel":    re.compile(r"白銀ノエル|ノエル(?!賞)"),
    "marine":  re.compile(r"宝鐘マリン|マリン(?!ブルー|ルック)"),
    # 4期生
    "watame":  re.compile(r"角巻わため|わため"),
    "towa":    re.compile(r"常闇トワ|トワ(?!イライト|ード)"),
    "luna":    re.compile(r"姫森ルーナ|ルーナ(?!ティック)"),
    # 5期生
    "lamy":    re.compile(r"雪花ラミィ|ラミィ"),
    "nene":    re.compile(r"桃鈴ねね|ねねち"),
    "botan":   re.compile(r"獅白ぼたん|ぼたん(?!鍋)"),
    "polka":   re.compile(r"尾丸ポルカ|ポルカ(?!ドット)"),
    # 6期生 (holoX)
    "laplus":  re.compile(r"ラプラス(?!変換)|ラプ様"),
    "lui":     re.compile(r"鷹嶺ルイ|ルイ姉"),
    "koyori":  re.compile(r"博衣こより|こより(?!紙)"),
    "iroha":   re.compile(r"風真いろは|いろは(?!ちゃん)"),
    # ReGLOSS
    "kanade":  re.compile(r"音乃瀬奏|奏(?![の曲音])"),
    "ririka":  re.compile(r"一条莉々華|莉々華|りりか|りりらでん"),
    "raden":   re.compile(r"儒烏風亭らでん|らでん|りりらでん"),
    "hajime":  re.compile(r"轟はじめ|はじめ(?!まして)"),
    # FLOW GLOW
    "riona":   re.compile(r"響咲リオナ|リオナ"),
    "su":      re.compile(r"水宮枢|枢(?![のな])"),
    "chihaya": re.compile(r"輪堂千速|千速|ちはや(?!物語)"),
    "vivi":    re.compile(r"綺々羅々ヴィヴィ|ヴィヴィ"),
}

# ------------------------------------------------------------------ #
# ユーティリティ
# ------------------------------------------------------------------ #

def normalize_title(title: str) -> str:
    """タイトルを正規化してシリーズ重複検出に使う。"""
    t = unicodedata.normalize("NFKC", title)
    t = re.sub(r"[#＃]?\d+|[①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳]", "", t)
    t = re.sub(r"[!！?？【】「」『』♪♡☆★・ー〜~\-:\s]", "", t)
    return t.lower()


def is_collab(nfkc_title: str, key: str) -> tuple[bool, str]:
    """コラボ判定。(is_collab, reason) を返す。"""
    if COLLAB_KEYWORDS_RE.search(nfkc_title):
        return True, "コラボキーワード"
    if COLLAB_HASHTAG_RE.search(nfkc_title):
        return True, "コラボハッシュタグ"
    if HOLO_HASHTAG_GENERIC_RE.search(nfkc_title):
        return True, "ホロ系内部企画ハッシュタグ"
    if MULTI_SLASH_COLLAB_RE.search(nfkc_title):
        return True, "末尾括弧に複数名スラッシュ区切り"
    other_members = [k for k in MEMBER_NAME_PATTERNS if k != key]
    matches = [k for k in other_members if MEMBER_NAME_PATTERNS[k].search(nfkc_title)]
    if matches:
        return True, f"他メンバー名({','.join(matches)})"
    return False, ""


def load_scan_tsv(key: str) -> list[dict]:
    """scan TSV を読み込む。DATE_END 以前のみに絞る。"""
    tsv_path = SCAN_DIR / f"{key}.tsv"
    if not tsv_path.exists():
        return []
    videos = []
    with open(tsv_path, encoding="utf-8") as f:
        lines = f.readlines()[1:]
    for line in lines:
        parts = line.rstrip("\n").split("\t")
        if len(parts) < 3 or not parts[0]:
            continue
        date = parts[1] if len(parts) > 1 else ""
        # DATE_END 以前のみ（scan 側で --datebefore を指定済みだが念のため）
        if date > DATE_END:
            continue
        raw_title = parts[2] if len(parts) > 2 else ""
        clean_title = re.sub(r"\s+\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}$", "", raw_title)
        videos.append({
            "id":      parts[0],
            "date":    date,
            "title":   clean_title,
            "flagged": parts[3].strip() if len(parts) > 3 else "",
        })
    return videos


# ------------------------------------------------------------------ #
# メイン処理
# ------------------------------------------------------------------ #

def process_member(key: str) -> dict:
    """1メンバー分の除外・選択処理。結果dictを返す。"""
    name = MEMBERS_JP[key]["name"]
    videos = load_scan_tsv(key)

    excluded = []
    valid = []

    for v in videos:
        title = v["title"]
        nt = unicodedata.normalize("NFKC", title)
        reason = None

        # 手動除外リスト優先
        if v["id"] in MANUAL_EXCLUDES:
            reason = f"手動除外: {MANUAL_EXCLUDES[v['id']]}"

        if reason is None and MEMORIAL_RE.search(nt):
            reason = f"記念/イベント: {MEMORIAL_RE.search(nt).group()}"

        if reason is None:
            col, col_reason = is_collab(nt, key)
            if col:
                reason = f"コラボ: {col_reason}"

        if reason is None:
            m = CONTINUATION_RE.search(nt)
            if m:
                reason = f"続話: {m.group()}"

        if reason:
            excluded.append({**v, "reason": reason})
        else:
            valid.append(v)

    # タイトル重複排除（古い方=1本目を残す）
    seen: dict[str, dict] = {}
    for v in reversed(valid):
        norm = normalize_title(v["title"])
        seen[norm] = v
    deduped_set = set(id(v) for v in seen.values())
    for v in valid:
        if id(v) not in deduped_set:
            excluded.append({**v, "reason": "タイトル重複(同一シリーズ1本目あり)"})

    deduped = sorted(seen.values(), key=lambda v: v["date"], reverse=True)
    selected = deduped[:N_STREAMS]

    return {
        "key": key,
        "name": name,
        "excluded": excluded,
        "valid_pool": deduped,
        "selected": selected,
    }


def check_overlap(results: list[dict]) -> tuple[str, str]:
    ranges = []
    for r in results:
        if not r["selected"]:
            continue
        dates = sorted(v["date"] for v in r["selected"])
        ranges.append((r["name"], dates[0], dates[-1]))
    if not ranges:
        return "", ""
    max_start = max(r[1] for r in ranges)
    min_end   = min(r[2] for r in ranges)
    return max_start, min_end


def build_log(results: list[dict], max_start: str, min_end: str) -> str:
    lines = [
        "# JP Step1 サンプリング選択ログ\n",
        f"DATE_END: {DATE_END}（こより休止前）\n",
        "",
        "## 同一時期オーバーラップ検証\n",
        "| タレント | 最古日 | 最新日 |",
        "|---------|--------|--------|",
    ]
    for r in results:
        if r["selected"]:
            dates = sorted(v["date"] for v in r["selected"])
            lines.append(f"| {r['name']} | {dates[0]} | {dates[-1]} |")
    lines.append("")
    if max_start and min_end:
        if max_start <= min_end:
            lines.append(f"**オーバーラップ区間: {max_start} 〜 {min_end}** ✅\n")
        else:
            lines.append(f"**オーバーラップなし** ⚠️  max(開始)={max_start} > min(終了)={min_end}\n")
    lines.append("")

    for r in results:
        lines.append(f"## {r['name']} ({r['key']})\n")
        lines.append(f"### 選択 ({len(r['selected'])} 件)\n")
        lines.append("| # | video_id | 日付 | タイトル |")
        lines.append("|---|----------|------|----------|")
        for i, v in enumerate(r["selected"], 1):
            lines.append(f"| {i} | {v['id']} | {v['date']} | {v['title']} |")
        lines.append("")
        lines.append(f"### 除外 ({len(r['excluded'])} 件)\n")
        lines.append("| video_id | 日付 | タイトル | 除外理由 |")
        lines.append("|----------|------|----------|---------|")
        for v in r["excluded"]:
            lines.append(f"| {v['id']} | {v['date']} | {v['title']} | {v['reason']} |")
        lines.append("")

    return "\n".join(lines)


def main():
    dry_run = "--dry-run" in sys.argv

    if dry_run:
        print("=== DRY-RUN モード（data/urls_jp/ への書き込みなし）===\n")

    results = []
    for key in MEMBERS_JP:
        r = process_member(key)
        results.append(r)

    max_start, min_end = check_overlap(results)

    print(f"{'タレント':<20} {'選択':<5} {'除外':<5} {'最古日':<10} {'最新日':<10}")
    print("-" * 55)
    for r in results:
        sel = r["selected"]
        dates = sorted(v["date"] for v in sel) if sel else []
        oldest = dates[0] if dates else "-"
        newest = dates[-1] if dates else "-"
        shortage = " ⚠️ 不足" if len(sel) < N_STREAMS else ""
        print(f"{r['name']:<20} {len(sel):<5} {len(r['excluded']):<5} {oldest:<10} {newest:<10}{shortage}")

    print()
    if max_start and min_end:
        if max_start <= min_end:
            print(f"同一時期オーバーラップ: {max_start} 〜 {min_end} ✅")
        else:
            print(f"⚠️  オーバーラップなし: max(開始)={max_start} > min(終了)={min_end}")
    print()

    for r in results:
        print(f"--- {r['name']} ---")
        for i, v in enumerate(r["selected"], 1):
            print(f"  {i:2}. [{v['date']}] {v['title']}")
        print()

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    log_content = build_log(results, max_start, min_end)
    with open(LOG_PATH, "w", encoding="utf-8") as f:
        f.write(log_content)
    print(f"ログ出力: {LOG_PATH}")

    if not dry_run:
        URLS_DIR.mkdir(parents=True, exist_ok=True)
        for r in results:
            if len(r["selected"]) < N_STREAMS:
                print(f"  ⚠️  {r['name']}: {len(r['selected'])} 件しか選択できませんでした（スキップ）")
                continue
            out_path = URLS_DIR / f"{r['key']}.tsv"
            with open(out_path, "w", encoding="utf-8") as f:
                f.write("video_id\tupload_date\ttitle\n")
                for v in r["selected"]:
                    f.write(f"{v['id']}\t{v['date']}\t{v['title']}\n")
            print(f"  書き込み: {out_path}")
        print("\n完了")


if __name__ == "__main__":
    main()
