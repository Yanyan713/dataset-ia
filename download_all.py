# -*- coding: utf-8 -*-
"""download_all.py — Regenere le dataset IA complet (~44 Go) depuis les sources publiques.
Usage :  python download_all.py [fr|en|code|all]
Toutes les sources sont libres et accessibles depuis la Chine (hf-mirror, dumps.wikimedia.org, gutenberg.org, beq).
"""
import os, sys, json, time, urllib.request, urllib.parse, gzip, io

BASE = r"D:\datasets"
os.makedirs(BASE, exist_ok=True)

def dl(url, dest, resume=True):
    """Telecharge url vers dest (reprise si partiel). Retourne True si OK."""
    if os.path.exists(dest):
        size = os.path.getsize(dest)
        if size > 1000:
            print("  deja present (%d Mo)" % (size//1024//1024), flush=True)
            return True
    print("  telechargement: %s" % url, flush=True)
    req = urllib.request.Request(url, headers={"User-Agent": "dataset-downloader/1.0"})
    tmp = dest + ".part"
    mode = "ab" if resume and os.path.exists(tmp) else "wb"
    offset = os.path.getsize(tmp) if mode == "ab" else 0
    if offset:
        req.add_header("Range", "bytes=%d-" % offset)
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(tmp, mode) as f:
            while True:
                chunk = r.read(4 * 1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)
        os.replace(tmp, dest)
        return True
    except Exception as e:
        print("    erreur: %s" % e, flush=True)
        return False

# ---------------- Wikipedia FR/EN 2022 (hf-mirror legacy) ----------------
def wiki_2022(lang, files):
    out = os.path.join(BASE, "wikipedia_%s" % lang)
    os.makedirs(out, exist_ok=True)
    for i in range(files):
        name = "train-%05d-of-%05d.parquet" % (i, files)
        url = ("https://hf-mirror.com/datasets/legacy-datasets/wikipedia/resolve/"
               "main/20220301.%s/%s?download=true" % (lang, name))
        p = os.path.join(out, name)
        if dl(url, p):
            try:
                import pyarrow.parquet as pq
                t = pq.read_table(p).to_pandas()["text"]
                with open(os.path.join(out, name.replace(".parquet", ".txt")), "w", encoding="utf-8") as f:
                    f.write("\n\n".join(t.astype(str)))
            except ImportError:
                print("  pyarrow manquant; parquet laisse tel quel", flush=True)

# ---------------- Wikipedia FR/EN 2023 (hf-mirror wikimedia) ----------------
def wiki_2023(lang, files):
    out = os.path.join(BASE, "wikipedia_%s_2023" % lang)
    os.makedirs(out, exist_ok=True)
    for i in range(files):
        name = "train-%05d-of-%05d.parquet" % (i, files)
        url = ("https://hf-mirror.com/datasets/wikimedia/wikipedia/resolve/"
               "main/20231101.%s/%s?download=true" % (lang, name))
        p = os.path.join(out, name)
        if dl(url, p):
            try:
                import pyarrow.parquet as pq
                t = pq.read_table(p).to_pandas()["text"]
                with open(os.path.join(out, name.replace(".parquet", ".txt")), "w", encoding="utf-8") as f:
                    f.write("\n\n".join(t.astype(str)))
            except ImportError:
                pass

# ---------------- Gutenberg FR ----------------
def gutenberg_fr():
    out = os.path.join(BASE, "gutenberg_fr_bulk")
    os.makedirs(out, exist_ok=True)
    print("  recuperation de la liste des livres FR...", flush=True)
    if not dl("https://www.gutenberg.org/browse/languages/fr", os.path.join(out, "_liste.html")):
        return
    import re
    ids = re.findall(r"/ebooks/(\d+)", open(os.path.join(out, "_liste.html"), encoding="utf-8", errors="ignore").read())
    print("  %d livres trouves" % len(ids), flush=True)
    for eid in ids:
        dest = os.path.join(out, "pg%s.txt" % eid)
        if os.path.exists(dest) and os.path.getsize(dest) > 1000:
            continue
        dl("https://www.gutenberg.org/cache/epub/%s/pg%s.txt" % (eid, eid), dest)
        time.sleep(0.3)

# ---------------- BEQ classiques ----------------
def beq():
    out = os.path.join(BASE, "auteurs_classiques")
    os.makedirs(out, exist_ok=True)
    for cat in ["classiques", "ventm", "poesie", "theatre"]:
        idx = "https://beq.ebooksgratuits.com/%s/index.htm" % cat
        try:
            req = urllib.request.Request(idx, headers={"User-Agent": "Mozilla/5.0"})
            html = urllib.request.urlopen(req, timeout=30).read().decode("utf-8", "ignore")
        except Exception:
            continue
        import re
        for m in re.findall(r'href="([^"]+\.epub)"', html):
            url = "https://beq.ebooksgratuits.com/%s/%s" % (cat, m)
            dest = os.path.join(out, "beq_" + m.replace("/", "_").replace(".epub", ".txt"))
            if os.path.exists(dest) and os.path.getsize(dest) > 500:
                continue
            ep = os.path.join(out, "beq_" + m.replace("/", "_"))
            if dl(url, ep):
                try:
                    import zipfile
                    with zipfile.ZipFile(ep) as z:
                        content = "".join(z.read(n).decode("utf-8", "ignore") for n in z.namelist() if n.endswith(".html") or n.endswith(".xhtml"))
                    open(dest, "w", encoding="utf-8").write(content)
                    os.remove(ep)
                except Exception:
                    pass

# ---------------- Wikinews / Wikiquote FR (dumps) ----------------
def wikimedia_dump(wiki, lang, outname):
    out = os.path.join(BASE, outname)
    os.makedirs(out, exist_ok=True)
    url = "https://dumps.wikimedia.org/%s%s/latest/%s%s-latest-pages-articles.xml.bz2" % (lang, wiki, lang, wiki)
    dest = os.path.join(out, os.path.basename(url))
    if not dl(url, dest):
        return
    txt = os.path.join(out, outname + ".txt")
    if os.path.exists(txt) and os.path.getsize(txt) > 1000:
        return
    import re
    print("  extraction du texte (peut prendre plusieurs minutes)...", flush=True)
    with gzip.open(dest, "rb") as f:
        data = f.read().decode("utf-8", "ignore")
    pages = re.findall(r"<page>.*?<title>(.*?)</title>.*?<text.*?>(.*?)</text>.*?</page>", data, re.S)
    with open(txt, "w", encoding="utf-8") as f:
        for t, body in pages:
            body = re.sub(r"\[\[File:[^\]]*\]\]", "", body)
            body = re.sub(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]", r"\1", body)
            body = re.sub(r"<[^>]+>", "", body)
            body = re.sub(r"\{\{[^}]*\}\}", "", body)
            body = re.sub(r"\n{3,}", "\n\n", body).strip()
            if body:
                f.write("%s\n%s\n\n" % (t.strip(), body))
    print("  %d pages extraites" % len(pages), flush=True)

# ---------------- Presse EN (CNN + XSum) ----------------
def news_en():
    out = os.path.join(BASE, "news_en")
    os.makedirs(out, exist_ok=True)
    cnn = ["train-00000-of-00003.parquet", "train-00001-of-00003.parquet", "train-00002-of-00003.parquet",
           "validation-00000-of-00001.parquet", "test-00000-of-00001.parquet"]
    for n in cnn:
        url = "https://hf-mirror.com/datasets/cnn_dailymail/resolve/main/1.0.0/%s?download=true" % n
        dl(url, os.path.join(out, "cnn_" + n))
    for n in ["train-00000-of-00001.parquet", "validation-00000-of-00001.parquet", "test-00000-of-00001.parquet"]:
        url = "https://hf-mirror.com/datasets/EdinburghNLP/xsum/resolve/main/%s?download=true" % n
        dl(url, os.path.join(out, "xsum_" + n))

# ---------------- Code GitHub (html/js/css) ----------------
def code_github():
    out = os.path.join(BASE, "code_github")
    os.makedirs(out, exist_ok=True)
    total = 880
    for i in range(total):
        name = "train-%05d-of-%05d.parquet" % (i, total)
        url = "https://hf-mirror.com/datasets/codeparrot/github-code-clean/resolve/main/data/%s?download=true" % name
        dl(url, os.path.join(out, name))

TASKS = {
    "fr": [("wikipedia_fr (6,8 Go)", lambda: wiki_2022("fr", 15)),
           ("wikipedia_fr_2023 (7,4 Go)", lambda: wiki_2023("fr", 17)),
           ("gutenberg_fr (1,7 Go)", gutenberg_fr),
           ("beq classiques (0,3 Go)", beq),
           ("wikinews_fr", lambda: wikimedia_dump("wikinews", "fr", "wikinews_fr")),
           ("wikiquote_fr", lambda: wikimedia_dump("wikiquote", "fr", "wikiquote_fr"))],
    "en": [("wikipedia_en (7,4 Go)", lambda: wiki_2022("en", 9)),
           ("wikipedia_en_2023 (4,7 Go)", lambda: wiki_2023("en", 41)),
           ("news_en (1,8 Go)", news_en)],
    "code": [("code_github (13,3 Go)", code_github)],
}

if __name__ == "__main__":
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    jobs = {"fr": TASKS["fr"], "en": TASKS["en"], "code": TASKS["code"], "all": TASKS["fr"] + TASKS["en"] + TASKS["code"]}.get(what)
    if not jobs:
        print("Usage: python download_all.py [fr|en|code|all]")
        sys.exit(1)
    for label, fn in jobs:
        print("== %s" % label, flush=True)
        try:
            fn()
        except Exception as e:
            print("  ECHEC: %s" % e, flush=True)
    print("Termine. Dataset dans %s" % BASE)
