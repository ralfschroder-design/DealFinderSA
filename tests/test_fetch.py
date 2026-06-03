import httpx
import respx

from dealfinder.fetch import Fetcher


@respx.mock
def test_get_json_returns_parsed_body():
    respx.get("https://api.test/stock").mock(
        return_value=httpx.Response(200, json={"results": [1, 2]})
    )
    fetcher = Fetcher(min_interval=0.0, max_retries=1, user_agent="UA", sleep=lambda _: None)
    body = fetcher.get_json("https://api.test/stock")
    assert body == {"results": [1, 2]}


@respx.mock
def test_get_json_retries_then_succeeds():
    route = respx.get("https://api.test/stock")
    route.side_effect = [
        httpx.Response(429),
        httpx.Response(200, json={"ok": True}),
    ]
    fetcher = Fetcher(min_interval=0.0, max_retries=3, user_agent="UA", sleep=lambda _: None)
    body = fetcher.get_json("https://api.test/stock")
    assert body == {"ok": True}
    assert route.call_count == 2


@respx.mock
def test_get_json_sets_user_agent():
    captured = {}

    def handler(request):
        captured["ua"] = request.headers.get("user-agent")
        return httpx.Response(200, json={})

    respx.get("https://api.test/x").mock(side_effect=handler)
    Fetcher(min_interval=0.0, max_retries=1, user_agent="DF/0.1", sleep=lambda _: None).get_json(
        "https://api.test/x"
    )
    assert captured["ua"] == "DF/0.1"
