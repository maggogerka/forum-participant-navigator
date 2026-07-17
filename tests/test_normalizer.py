from scraper.normalizer import canonicalize_url, clean_text, normalize_organization_name


def test_clean_text_compacts_spaces_and_entities():
    assert clean_text("  Генеральный&nbsp;&nbsp;директор\nАО &laquo;Компания&raquo; ") == "Генеральный директор АО «Компания»"


def test_canonicalize_url_removes_query_and_adds_trailing_slash():
    assert (
        canonicalize_url("https://roscongress.ru/speakers/example-person?from=search")
        == "https://roscongress.ru/speakers/example-person/"
    )


def test_normalize_organization_name_keeps_legal_form_but_normalizes_quotes():
    assert normalize_organization_name("АО «Объединённая энергетическая компания»") == "ао объединенная энергетическая компания"

