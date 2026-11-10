"""Contrato estático da aba Capture Manager e do padrão de evidências.

Verifica a integração na página monolítica sem exigir browser.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "backend" / "static" / "index.html"
DOC = ROOT / "docs" / "PADRAO_NOMENCLATURA_CAPTURAS.md"


def test_capture_manager_tab_and_events():
    html = PAGE.read_text(encoding="utf-8")
    assert 'data-tab="namer"' in html
    assert "if(active==='namer'){renderCaptureNamer();return;}" in html
    assert "function renderCaptureNamer()" in html
    assert "addEventListener('input',build)" in html
    assert "navigator.clipboard.writeText(info.filename)" in html


def test_capture_generator_provides_required_inputs_and_exports():
    html = PAGE.read_text(encoding="utf-8")
    for element in ("cnver", "cnexp", "cnstage", "cncharacter",
                    "cnkind", "cnpc", "cnstateext", "cnsha"):
        assert 'id="'+element+'"' in html
    assert "umk3dx_'+ver+'_exp'+exp" in html
    assert "pc_at_capture" in html
    assert "steps_exact" in html
    assert "JSON.stringify(obj,null,2)" in html
    assert "Corrija os campos acima" in html


def test_capture_naming_documented():
    markdown = DOC.read_text(encoding="utf-8")
    for expected in ("umk3dx_<versao>_exp<NNN>", "dbp01", "dmid01",
                     "dstep096", "wram", "vram", "oam", "cgram",
                     "spcram", "cpumem", "sha256", "meta.json"):
        assert expected in markdown
