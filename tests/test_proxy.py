from app.utils.proxy import ProxyRouter


def test_no_proxy_for_zakupki_mos() -> None:
    router = ProxyRouter(
        use_proxy=True,
        http_proxy="http://proxy.example:8080",
        https_proxy="http://proxy.example:8080",
        no_proxy_hosts=[
            "localhost",
            "127.0.0.1",
            "agregatoreat.ru",
            ".agregatoreat.ru",
            "zakupki.mos.ru",
            ".zakupki.mos.ru",
            "api.zakupki.mos.ru",
        ],
    )

    assert router.should_bypass_proxy("https://zakupki.mos.ru/auction") is True
    assert router.decide("https://zakupki.mos.ru/auction").use_proxy is False


def test_no_proxy_for_agregatoreat() -> None:
    router = ProxyRouter(
        use_proxy=True,
        http_proxy="http://proxy.example:8080",
        https_proxy="http://proxy.example:8080",
        no_proxy_hosts=["agregatoreat.ru", ".agregatoreat.ru"],
    )

    assert router.should_bypass_proxy("https://agregatoreat.ru/purchases") is True
    assert router.should_bypass_proxy("https://login.agregatoreat.ru/") is True


def test_forced_no_proxy_hosts_bypass_even_without_no_proxy_rules() -> None:
    router = ProxyRouter(
        use_proxy=True,
        http_proxy="http://proxy.example:8080",
        https_proxy="http://proxy.example:8080",
        no_proxy_hosts=[],
    )

    assert router.should_bypass_proxy("https://zakupki.mos.ru/auction") is True
    assert router.decide("https://zakupki.mos.ru/auction").use_proxy is False
    assert router.should_bypass_proxy("https://api.zakupki.mos.ru/purchases") is True


def test_external_domain_can_use_proxy() -> None:
    router = ProxyRouter(
        use_proxy=True,
        http_proxy="http://proxy.example:8080",
        https_proxy="http://proxy.example:8080",
        no_proxy_hosts=["zakupki.mos.ru"],
    )

    decision = router.decide("https://marketplace.example.com/catalog")
    assert decision.use_proxy is True
    assert decision.proxy_url == "http://proxy.example:8080"
