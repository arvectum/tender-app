from scripts.mos_portal_extract_attachments import _extract_candidates, _file_id, _is_likely_tz_name


def test_extract_candidates_only_purchase_scoped_filestorage_links() -> None:
    hrefs = [
        "https://zakupki.mos.ru/cms/Media/docs/Регистрация_с_ЭП_и_без_ЭП.pdf",
        "https://zakupki.mos.ru/newapi/api/FileStorage/Download?id=275336647",
        "https://zakupki.mos.ru/newapi/api/FileStorage/Download?id=275336647",  # duplicate
        "https://mos.ditokc.ru/chat/widgetloader/PortPost/img/attach.svg",
    ]
    candidates = _extract_candidates(hrefs)
    assert len(candidates) == 1
    assert _file_id(candidates[0].url) == "275336647"


def test_is_likely_tz_name_filters_generic_docs() -> None:
    assert _is_likely_tz_name("Техническое_задание.pdf") is True
    assert _is_likely_tz_name("specification.docx") is True
    assert _is_likely_tz_name("Регистрация_с_ЭП_и_без_ЭП.pdf") is False
