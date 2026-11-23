"""Harp teknolojisi derleyicisi: açık RSS akışlarından sahadaki teknoloji haberlerini toplar,
konulara ayırır, kırmızı çizgilerden geçirir ve günlük rapor yazar. Yalnızca standart kütüphane.

    python derle.py            # akışları çek, veri/ ve raporlar/ altına yaz
    python derle.py --kuru     # ağ yok: yalnızca mevcut veriden raporu yeniden yaz
"""
from __future__ import annotations

import argparse
import datetime as dt
import email.utils
import hashlib
import html
import json
import re
import sys
import tomllib
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

KOK = Path(__file__).resolve().parent
VERI = KOK / "veri"
RAPOR = KOK / "raporlar" / "gunluk"
UA = "harp-teknolojisi/1.0 (+https://github.com/Greater-Turkiye/harp-teknolojisi)"

# Kırmızı çizgiler (handbook/tr/02-red-lines.md): Türk kuvvetlerinin konum/hareket/konuşlanma/zafiyet
# bilgisi ve gizli/sızdırılmış materyal derlenmez. Bu bir kapıdır: şüpheli öğe hiç kaydedilmez.
TURK = re.compile(r"\b(turkish|türk|tsk|turkey'?s|türkiye'?nin|mehmetçik|jandarma|mit)\b", re.I)
HAREKET = re.compile(r"\b(deploy|troops? (move|movement)|convoy|base in|stationed|positions?|konuşlan|sevkiyat|konvoy|mevzi|birlik(ler)?i? (bölgeye|sınıra))", re.I)
SIZINTI = re.compile(r"\b(leak(ed|s)?|classified documents?|sızdırıl|gizli belge)", re.I)


def kirmizi_cizgi(metin: str) -> str | None:
    if SIZINTI.search(metin):
        return "sızıntı"
    if TURK.search(metin) and HAREKET.search(metin):
        return "türk-kuvvetleri"
    return None


def yukle_toml(ad: str) -> dict:
    return tomllib.loads((KOK / ad).read_text(encoding="utf-8"))


def temiz(s: str | None, n: int = 0) -> str:
    s = html.unescape(re.sub(r"<[^>]+>", " ", s or ""))
    s = re.sub(r"\s+", " ", s).strip()
    return (s[: n - 1].rsplit(" ", 1)[0] + "…") if n and len(s) > n else s


def tarih(s: str | None) -> str:
    if not s:
        return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


def oge_listesi(xml: bytes) -> list[dict]:
    kok = ET.fromstring(xml)
    atom = "{http://www.w3.org/2005/Atom}"
    cikti = []
    for it in kok.iter("item"):
        cikti.append({
            "baslik": temiz(it.findtext("title")),
            "baglanti": (it.findtext("link") or "").strip(),
            "tarih": tarih(it.findtext("pubDate") or it.findtext("{http://purl.org/dc/elements/1.1/}date")),
            "ozet": temiz(it.findtext("description"), 320),
            "yayinci": temiz(it.findtext("source")),
        })
    for it in kok.iter(f"{atom}entry"):
        link = it.find(f"{atom}link")
        cikti.append({
            "baslik": temiz(it.findtext(f"{atom}title")),
            "baglanti": link.get("href", "") if link is not None else "",
            "tarih": tarih(it.findtext(f"{atom}updated") or it.findtext(f"{atom}published")),
            "ozet": temiz(it.findtext(f"{atom}summary"), 320),
            "yayinci": "",
        })
    return cikti


def anahtar(baslik: str) -> str:
    """Aynı haber farklı akışlardan gelirse tek kayıt: başlığın sade hali."""
    b = re.sub(r"\s+-\s+[^-]{2,60}$", "", baslik)  # Google News'in "… - Yayıncı" eki
    b = re.sub(r"[^\w]+", " ", b.lower()).strip()
    return hashlib.sha1(b.encode()).hexdigest()[:16]


def konular_of(metin: str, konular: list[dict]) -> list[str]:
    return [k["id"] for k in konular if any(re.search(d, metin, re.I) for d in k["desen"])]


# Alaka kapısı: hiçbir konu desenine uymayan öğe ancak dron/savunma ile açıkça ilgiliyse "diger"e girer.
# Google News aramasının konusu artık zorla eklenmez; arama, başlığı alakasız haberler de döndürüyordu
# ("Israel's economy…" otonomi, "hybrid propulsion" akustik görünüyordu).
ALAKA = re.compile(r"\b(drones?|dron(lar)?|uavs?|uas|ucavs?|unmanned|uncrewed|insansız|iha|counter[- ]?(uas|drone)|loitering"
                   r"|munitions?|missiles?|füze|air defen[cs]e|hava savunma|military|army|navy|ordu|defen[cs]e|savunma"
                   r"|warfare|harp|battlefield|front ?lines?|cephe|jamm\w*|radar|interceptors?)\b", re.I)


def etiketle(metin: str, konular: list[dict]) -> list[str]:
    ks = konular_of(metin, konular)
    if ks:
        return ks
    return ["diger"] if ALAKA.search(metin) and any(k["id"] == "diger" for k in konular) else []


def cek(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read()


def mevcut() -> dict[str, dict]:
    kayit: dict[str, dict] = {}
    for f in sorted(VERI.glob("*/*.jsonl")):
        for satir in f.read_text(encoding="utf-8").splitlines():
            if satir.strip():
                o = json.loads(satir)
                kayit[o["id"]] = o
    return kayit


def topla(kaynaklar: dict, konular: list[dict], gorulen: dict[str, dict]) -> tuple[list[dict], dict]:
    yeni, durum = [], {"akis": 0, "hata": [], "reddedilen": {}}
    for akis in kaynaklar["akis"]:
        try:
            ogeler = oge_listesi(cek(akis["url"]))
            durum["akis"] += 1
        except Exception as e:  # bir akışın düşmesi raporu durdurmaz
            durum["hata"].append(f"{akis['ad']}: {type(e).__name__}")
            continue
        for o in ogeler:
            if not o["baslik"] or not o["baglanti"]:
                continue
            metin = f"{o['baslik']} {o['ozet']}"
            neden = kirmizi_cizgi(metin)
            if neden:
                durum["reddedilen"][neden] = durum["reddedilen"].get(neden, 0) + 1
                continue
            ks = etiketle(metin, konular)
            if not ks:
                continue
            kid = anahtar(o["baslik"])
            yayinci = o["yayinci"] or akis["ad"]
            if kid in gorulen:
                k = gorulen[kid]
                if yayinci not in k["kaynaklar"]:
                    k["kaynaklar"].append(yayinci)
                    k["_degisti"] = True
                k["konular"] = sorted(set(k["konular"]) | set(ks), key=[x["id"] for x in konular].index)
                continue
            k = {"id": kid, "baslik": o["baslik"], "baglanti": o["baglanti"], "tarih": o["tarih"],
                 "ozet": o["ozet"], "konular": ks, "kaynaklar": [yayinci],
                 "alindi": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
            gorulen[kid] = k
            yeni.append(k)
    return yeni, durum


def kaydet(gorulen: dict[str, dict]) -> None:
    aylar: dict[str, list[dict]] = {}
    for k in gorulen.values():
        k.pop("_degisti", None)
        aylar.setdefault(k["alindi"][:7], []).append(k)
    for ay, liste in aylar.items():
        f = VERI / ay[:4] / f"{ay[5:7]}.jsonl"
        f.parent.mkdir(parents=True, exist_ok=True)
        liste.sort(key=lambda k: (k["alindi"], k["id"]))
        f.write_text("".join(json.dumps(k, ensure_ascii=False) + "\n" for k in liste), encoding="utf-8")


def yalin(baslik: str) -> str:
    """Google News başlığındaki "… - Yayıncı" eki: yayıncı zaten satırın sonunda yazılı."""
    return re.sub(r"\s+-\s+[^-]{2,60}$", "", baslik)


def puan(k: dict) -> tuple:
    # birden çok yayıncının aynı haberi vermesi ve birden çok konuya değmesi önem işaretidir
    return (len(k["kaynaklar"]), len(k["konular"]), k["tarih"])


def rapor(gorulen: dict[str, dict], konular: list[dict], gun: dt.date, durum: dict | None) -> Path:
    # o gün derlenen ve en çok 3 gün önce yayımlanmış haberler: ilk çalıştırmada eski arşiv rapora dolmaz
    gunbas = dt.datetime.combine(gun, dt.time(), dt.timezone.utc).isoformat()
    eski = dt.datetime.combine(gun - dt.timedelta(days=3), dt.time(), dt.timezone.utc).isoformat()
    son = [k for k in gorulen.values() if k["alindi"] >= gunbas and k["tarih"] >= eski]
    satirlar = [f"# Harp teknolojisi — {gun.isoformat()}", "",
                f"Bugün derlenen **{len(son)}** haber, konuya göre. "
                "Başlıklar kaynağın kendi dilindedir; her satır kaynağa bağlanır. "
                "Bu bir derlemedir, doğrulama değildir: bir iddia ancak birden çok bağımsız kaynakla güç kazanır.", ""]
    one = sorted(son, key=puan, reverse=True)[:5]
    if one:
        satirlar += ["## Öne çıkanlar", ""]
        satirlar += [f"- [{yalin(k['baslik'])}]({k['baglanti']}) — {', '.join(k['kaynaklar'][:4])}" for k in one]
        satirlar.append("")
    for kon in konular:
        grup = sorted([k for k in son if k["konular"][0] == kon["id"]], key=puan, reverse=True)
        if not grup:
            continue
        satirlar += [f"## {kon['ad']}", f"_{kon['neden']}_", ""]
        for k in grup[:12]:
            satirlar.append(f"- [{yalin(k['baslik'])}]({k['baglanti']}) — {', '.join(k['kaynaklar'][:3])} · {k['tarih'][:10]}")
        if len(grup) > 12:
            satirlar.append(f"- … ve {len(grup) - 12} haber daha (`veri/`)")
        satirlar.append("")
    if durum:
        red = ", ".join(f"{n} {a}" for a, n in durum["reddedilen"].items()) or "yok"
        satirlar += ["---", f"Akış: {durum['akis']} çalıştı"
                     + (f", {len(durum['hata'])} düştü ({'; '.join(durum['hata'])})" if durum["hata"] else "")
                     + f". Kırmızı çizgi kapısında elenen: {red}."]
    RAPOR.mkdir(parents=True, exist_ok=True)
    f = RAPOR / f"{gun.isoformat()}.md"
    f.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    (KOK / "SON.md").write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return f


def evrim(gorulen: dict[str, dict], konular: list[dict]) -> Path:
    """Teknolojinin hızı: her konunun haftalık haber sayısı (yayın tarihine göre) ve ilk görüldüğü gün.
    Bir konunun sayısı haftalar içinde artıyorsa, o teknoloji sahada yayılıyor demektir."""
    hafta = lambda t: "{}-H{:02d}".format(*dt.date.fromisoformat(t[:10]).isocalendar()[:2])
    sayim: dict[str, dict[str, int]] = {}
    ilk: dict[str, dict] = {}
    for k in gorulen.values():
        for kid in k["konular"]:
            h = hafta(k["tarih"])
            sayim.setdefault(kid, {})[h] = sayim.setdefault(kid, {}).get(h, 0) + 1
            if kid not in ilk or k["tarih"] < ilk[kid]["tarih"]:
                ilk[kid] = k
    haftalar = sorted({h for d in sayim.values() for h in d})[-12:]
    satirlar = ["# Evrim: hangi teknoloji ne hızla konuşuluyor", "",
                "Her konunun haftalık haber sayısı (yayın tarihine göre, son 12 hafta). Sayı haftadan haftaya "
                "artıyorsa o teknoloji sahada yayılıyor ya da yeni bir aşamaya geçiyor demektir. "
                "Veri derlemenin başladığı günden itibaren birikir; ilk haftalar eksiktir.", "",
                "| Konu | " + " | ".join(h[5:] for h in haftalar) + " | Toplam |",
                "|---|" + "---:|" * (len(haftalar) + 1)]
    for kon in konular:
        d = sayim.get(kon["id"], {})
        satirlar.append(f"| {kon['ad']} | " + " | ".join(str(d.get(h, "")) for h in haftalar) + f" | {sum(d.values())} |")
    satirlar += ["", "## Her konunun arşivdeki en eski haberi", ""]
    for kon in konular:
        if kon["id"] in ilk:
            k = ilk[kon["id"]]
            satirlar.append(f"- **{kon['ad']}** — {k['tarih'][:10]}: [{yalin(k['baslik'])}]({k['baglanti']})")
    f = KOK / "EVRIM.md"
    f.write_text("\n".join(satirlar) + "\n", encoding="utf-8")
    return f


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kuru", action="store_true", help="ağa çıkma, yalnızca raporu yeniden yaz")
    ap.add_argument("--yeniden-etiketle", action="store_true",
                    help="kayıtlı tüm haberlerin konularını güncel desenlerle yeniden hesapla; alakasızları sil")
    a = ap.parse_args(argv)
    konular = yukle_toml("konular.toml")["konu"]
    gorulen = mevcut()
    durum = None
    if a.yeniden_etiketle:
        once = len(gorulen)
        for kid in list(gorulen):
            k = gorulen[kid]
            ks = etiketle(f"{k['baslik']} {k['ozet']}", konular)
            if ks:
                k["konular"] = ks
            else:
                del gorulen[kid]
        for f in VERI.glob("*/*.jsonl"):
            f.unlink()
        kaydet(gorulen)
        print(f"yeniden etiketlendi: {len(gorulen)} kaldı, {once - len(gorulen)} alakasız silindi")
    if not a.kuru:
        yeni, durum = topla(yukle_toml("kaynaklar.toml"), konular, gorulen)
        kaydet(gorulen)
        print(f"{len(yeni)} yeni haber; {durum['akis']} akış; düşen: {durum['hata'] or 'yok'}; elenen: {durum['reddedilen'] or 'yok'}")
    f = rapor(gorulen, konular, dt.datetime.now(dt.timezone.utc).date(), durum)
    evrim(gorulen, konular)
    print(f"rapor: {f.relative_to(KOK)}; evrim: EVRIM.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
