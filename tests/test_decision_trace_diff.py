"""Testes da comparação de decisões (dados sintéticos, não evidência do jogo)."""
import pytest
from backend.decision_trace_diff import compare_traces


P = "nvmxdIzc"


def line(pc, asm, *, a=0, mem=None, ea=None, d=0x0C00, p=P):
    extra = (f" [${ea:06X}]" if ea is not None else "")
    extra += (f" = ${mem:04X}" if mem is not None else "")
    return f"{pc:06X} {asm}{extra} A:{a:04X} X:0000 Y:0000 S:01FF D:{d:04X} DB:7E P:{p}"


def trace(selected, previous=3, decision=1):
    return ("\n".join([
        line(0x86A780, "lda $0e", a=0, mem=selected, ea=0x7E0C0E),
        line(0x86A783, "cmp #$000a", a=selected),
        line(0x86A786, "bne $86a790", a=selected),
        line(0x86A790, "lda $0e", a=selected, mem=selected, ea=0x7E0C0E),
        line(0x86A7A6, "lda $0e", a=selected, mem=selected, ea=0x7E0C0E),
        line(0x86A7A8, "sta ($94)", a=selected, mem=previous, ea=0x7E3A50),
    ]) + "\n").encode()


def test_jax_to_ermac_versus_hidden_slot():
    diff = compare_traces(trace(0x10), trace(0x0A))
    assert diff["a"]["value_after_derived"] == 0x10
    assert diff["b"]["value_after_derived"] == 0x0A
    assert diff["summary"]["same_target"] is False
    assert diff["summary"]["a_destination"] == "Ermac"
    assert diff["summary"]["b_destination"] == "slot oculto"
    assert any(d["type"] == "memory_value" for d in diff["differences"])
    assert diff["a"]["confidence"] == "DERIVADO"


def test_spc_lines_ignored_but_counted():
    a = b"0200 mov a,#$20\n" + trace(0x10)
    b = trace(0x0A)
    result = compare_traces(a, b)
    assert result["meta"]["a"]["spc"] == 1
    assert result["a"]["found"]


def test_no_anchor_is_not_a_false_success():
    result = compare_traces(b"86A7A6 lda $0e\n", trace(0x0A))
    assert result["a"]["found"] is False
    assert not result["differences"]


def test_missing_effective_address_does_not_confirm_write():
    a = trace(0x10).decode().replace(" [\u00247E3A50]", "")
    result = compare_traces(a.encode(), trace(0x0A))
    assert result["a"]["found"]
    assert result["a"]["address_confirmed"] is False
    assert result["a"]["confidence"] == "NÃO VERIFICADO"


def test_unknown_width_does_not_claim_written_value():
    a = trace(0x10).decode().replace(" P:" + P, "")
    result = compare_traces(a.encode(), trace(0x0A))
    assert result["a"]["value_after_derived"] is None


def test_bad_ordinal_and_window():
    with pytest.raises(ValueError):
        compare_traces(trace(0x10), trace(0x0A), ordinal_a=2)
    with pytest.raises(ValueError):
        compare_traces(trace(0x10), trace(0x0A), lookback=0)


def test_two_identical_traces_have_no_differences():
    a = trace(0x0A)
    result = compare_traces(a, a)
    assert result["summary"]["same_target"]
    assert result["differences"] == []


def test_real_trace_is_optional_not_claimed():
    result = compare_traces(trace(0x10), trace(0x0A))
    assert "nenhuma causa foi demonstrada" in result["summary"]["interpretation"]


def test_repeated_register_differences_are_grouped():
    a = ("\n".join([
        line(0x86A780+i, "nop", a=0x0010) for i in range(90)
    ] + [line(0x86A7A8, "sta ($94)", a=0x0010, mem=3, ea=0x7E3A50)]) + "\n").encode()
    b = ("\n".join([
        line(0x86A780+i, "nop", a=0x000A) for i in range(90)
    ] + [line(0x86A7A8, "sta ($94)", a=0x000A, mem=3, ea=0x7E3A50)]) + "\n").encode()
    result = compare_traces(a, b)
    assert result["difference_counts"]["register_occurrences"] >= 90
    assert result["difference_counts"]["register_groups"] == 1
    assert result["differences"][0]["type"] == "register_group"
    assert result["differences"][0]["count"] >= 90
    assert any("Sem desvio de fluxo" in note for note in result["diagnostics"])


def test_decision_window_truncation_is_reported():
    result = compare_traces(trace(0x10), trace(0x0A), lookback=160)
    assert result["a"]["truncated_before"] is True
    assert any("ampliar lookback" in note for note in result["diagnostics"])
