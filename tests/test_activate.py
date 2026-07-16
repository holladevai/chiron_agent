from core import activate


def test_default_active(platform):
    assert activate.is_active(platform) is True   # varsayilan otomatik aktif


def test_set_and_read_state(platform):
    activate.set_active(platform, False)
    assert activate.is_active(platform) is False
    activate.set_active(platform, True)
    assert activate.is_active(platform) is True


def test_classify_engage():
    for p in ["ajan devreye gir", "lutfen AJAN aktif et", "/ajan",
              "ajani devreye al", "ajan basla"]:
        assert activate.classify(p) == "engage", p


def test_classify_disengage():
    for p in ["is bitti", "iş bitti tesekkurler", "ajan dur artik",
              "ajan kapat", "ajani devreden cikar"]:
        assert activate.classify(p) == "disengage", p


def test_classify_none():
    for p in ["bana bir fonksiyon yaz", "bu bug'i duzelt", "test ekle"]:
        assert activate.classify(p) is None, p


def test_disengage_priority():
    # ikisi de gecerse disengage oncelikli (guvenli yon)
    assert activate.classify("ajan devreye gir ama sonra is bitti") == "disengage"


def test_protocol_is_compact():
    # standing directive makul kisa olmali (token butcesi)
    assert len(activate.PROTOCOL) < 1400
