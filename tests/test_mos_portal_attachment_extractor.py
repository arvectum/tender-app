from install.mos_portal_extract_attachments import _is_likely_tz_name


def test_is_likely_tz_name_filters_generic_docs() -> None:
    assert _is_likely_tz_name("Техническое_задание.pdf") is True
    assert _is_likely_tz_name("specification.docx") is True
    assert _is_likely_tz_name("Регистрация_с_ЭП_и_без_ЭП.pdf") is False
