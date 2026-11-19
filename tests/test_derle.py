import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import derle  # noqa: E402

KONULAR = derle.yukle_toml("konular.toml")["konu"]

RSS = b"""<?xml version="1.0"?><rss><channel>
<item><title>Russia deploys fiber-optic Molniya drones - 112.ua</title><link>https://a/1</link>
<pubDate>Wed, 19 Nov 2026 08:00:00 GMT</pubDate><description>&lt;p&gt;Immune to jamming&lt;/p&gt;</description>
<source url="https://112.ua">112.ua</source></item>
<item><title>Bake sale raises funds</title><link>https://a/2</link></item>
</channel></rss>"""


def test_rss_ayristirma():
    ogeler = derle.oge_listesi(RSS)
    assert ogeler[0]["ozet"] == "Immune to jamming"
    assert ogeler[0]["yayinci"] == "112.ua"
    assert ogeler[0]["tarih"].startswith("2026-11-19T08:00")


def test_konu_eslesme():
    assert derle.konular_of("fiber-optic FPV drone hits tank", KONULAR)[:2] == ["fiber", "fpv"]
    assert "akustik" in derle.konular_of("Ukraine's Sky Fortress acoustic network", KONULAR)
    assert derle.konular_of("Bake sale raises funds", KONULAR) == []


def test_kirmizi_cizgi_turk_kuvvetleri_ve_sizinti():
    assert derle.kirmizi_cizgi("Turkish troops deploy to the border") == "türk-kuvvetleri"
    assert derle.kirmizi_cizgi("TSK birlikleri bölgeye konuşlandı") == "türk-kuvvetleri"
    assert derle.kirmizi_cizgi("Leaked documents show drone plans") == "sızıntı"
    # Türk savunma sanayiinin ürün haberi bir konum/hareket bilgisi değildir
    assert derle.kirmizi_cizgi("Turkish company unveils electromagnetic drone interceptor") is None


def test_ayni_haber_tek_kayit():
    assert derle.anahtar("Russia deploys fiber-optic drones - 112.ua") == derle.anahtar("Russia deploys fiber-optic drones")


def test_google_konusu_konular_listesinde():
    ids = {k["id"] for k in KONULAR}
    kaynaklar = tomllib.loads((Path(derle.KOK) / "kaynaklar.toml").read_text(encoding="utf-8"))["akis"]
    assert all(a["konu"] in ids for a in kaynaklar if "konu" in a)
