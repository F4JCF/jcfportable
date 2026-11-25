import re

from jcfportable import adif, commands, refs
from jcfportable.bands import band_for_freq, fmt_freq
from jcfportable.db import Database
from jcfportable.geo import grid_distance, grid_to_latlon, latlon_to_grid


def test_commands():
    p = commands.parse
    assert p("20m").kind == "band" and p("20m").value == "20m"
    assert p("cw").kind == "mode"
    assert p("14.070").value == 14070
    assert p("14070").value == 14070
    assert p(".247", 14245).value == 14247
    assert p(".7", 14245).value == 14247
    assert p("5W").value == "5"
    assert p("OP/F4JCF").value == "F4JCF"
    assert p("14:30").value == (14, 30, 0)
    assert p("+15m").kind == "offset"
    assert p("05-09").value == (None, 5, 9)
    c = p("QRT")
    assert c.kind == "spot" and c.extra["qrt"]
    assert p("SPME/test sur 40").value == "test sur 40"
    assert p("F4JCF") is None
    assert p("2518") is None  # pas une fréquence radioamateur
    assert commands.split_calls("f4abc, wv3h.ve") == ["F4ABC", "WV3H/VE"]
    assert commands.looks_like_call("F4JCF/P")
    assert not commands.looks_like_call("HELLO")


def test_geo_bands():
    assert latlon_to_grid(43.6, 7.0)[:4] == "JN33"
    lat, lon = grid_to_latlon("JN33lp")
    assert 43 < lat < 44 and 6 < lon < 8
    d, _ = grid_distance("JN33lp", "JN18du")
    assert 650 < d < 750
    assert band_for_freq(7074) == "40m"
    assert fmt_freq(14250) == "14.250"


def sample_db(tmp_path):
    db = Database(tmp_path / "t.db")
    pota_csv = ('"reference","name","active","entityId","locationDesc","latitude","longitude","grid"\n'
                '"FR-0123","Parc test","1","227","FR-PAC","43.6","7.0","JN33lp"\n'
                '"FR-2518","Autre parc","1","227","FR-PAC","43.7","7.1","JN33mq"\n')
    assert db.replace_refs("POTA", refs.parse_rows("POTA", pota_csv)) == 2
    sota_csv = ("SOTA Summits List (Date=01/01/2026)\n"
                "SummitCode,AssociationName,RegionName,SummitName,AltM,AltFt,GridRef1,GridRef2,Longitude,Latitude,"
                "Points,BonusPoints,ValidFrom,ValidTo,ActivationCount,ActivationDate,ActivationCall\n"
                "F/AM-468,France,Alpes-Maritimes,Mont Test,1200,3937,7.0,43.8,7.0,43.8,4,3,01/01/2010,31/12/2099,1,,\n")
    assert db.replace_refs("SOTA", refs.parse_rows("SOTA", sota_csv)) == 1
    return db


def test_refs(tmp_path):
    db = sample_db(tmp_path)
    assert refs.expand_ref(db, "POTA", "2518", "FR")[0] == "FR-2518"
    assert refs.expand_ref(db, "POTA", "123", "FR")[0] == "FR-0123"
    assert refs.expand_ref(db, "POTA", "fr123", "")[0] == "FR-0123"
    assert refs.expand_ref(db, "SOTA", "FAM468", "F")[0] == "F/AM-468"
    assert refs.expand_ref(db, "POTA", "99", "FR")[0] == "FR-0099"  # base sans la référence
    assert db.refs_near("POTA", 43.6, 7.0)[0]["ref"] == "FR-0123"
    assert db.search_refs("POTA", "autre")[0]["ref"] == "FR-2518"


def test_adif_export(tmp_path):
    db = sample_db(tmp_path)
    op_id = db.create_operation("Activation test", "F4JCF/P", "F4JCF", "JN33lp", "10",
                                [{"program": "POTA", "ref": "FR-0123"}, {"program": "POTA", "ref": "FR-2518"},
                                 {"program": "SOTA", "ref": "F/AM-468"}])
    db.add_qso(op_id, call="EA3XYZ", start="2026-11-25T10:00:00Z", freq=14250, band="20m", mode="SSB",
               rst_sent="59", rst_rcvd="57", their_refs=[{"program": "POTA", "ref": "EA-0001"}], notes="privé")
    db.add_qso(op_id, call="DL1ABC", start="2026-11-25T10:01:00Z", freq=7032, band="40m", mode="FT4",
               rst_sent="-10", rst_rcvd="-12")
    gone = db.add_qso(op_id, call="G0AAA", start="2026-11-25T10:02:00Z", freq=7032, band="40m", mode="CW")
    db.update_qso(gone, deleted=1)
    op = db.get_operation(op_id)
    paths = adif.export_operation(op, db.list_qsos(op_id), tmp_path / "out")
    names = sorted(p.name for p in paths)
    assert "F4JCF-P@FR-0123-20261125.adi" in names
    assert "F4JCF-P@F-AM-468-20261125.adi" in names
    assert len(paths) == 4
    pota = (tmp_path / "out" / "F4JCF-P@FR-0123-20261125.adi").read_text()
    assert "<MY_POTA_REF:7>FR-0123" in pota and "<POTA_REF:7>EA-0001" in pota
    assert "<SUBMODE:3>FT4" in pota and "G0AAA" not in pota
    assert "privé" not in pota  # pas de données privées dans les logs envoyés aux programmes
    full = [p for p in paths if p.name.endswith("complet.adi")][0].read_text()
    assert "privé" in full and full.count("<EOR>") == 2
    for rec in re.findall(r"<(\w+):(\d+)>([^<]*)", pota):
        assert len(rec[2].rstrip(" ").encode()) == int(rec[1])
