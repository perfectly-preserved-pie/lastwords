import json

from lastwords.cli import parse_oauth_verifier
from requests import PreparedRequest, Response, Session

from lastwords.tdcj import (
    EXECUTIONS_URL,
    decode_tdcj_response,
    fetch_executions,
    parse_executions_html,
    parse_statement_html,
)
from lastwords.tumblr import (
    extract_statement_url_from_quote_source,
    fetch_existing_quotes,
    has_suspicious_encoding,
    parse_public_read_json,
    validate_created_post_response,
    validate_tumblr_response,
)

EXECUTIONS_HTML = """
<table class="default" area-label="Table showing list of executed inmates">
  <tr>
    <th>Execution</th>
    <th>Link</th>
    <th>Link</th>
    <th>Last Name</th>
    <th>First Name</th>
    <th>TDCJ Number</th>
    <th>Age</th>
    <th>Date</th>
    <th>Race</th>
    <th>County</th>
  </tr>
  <tr>
    <td>598</td>
    <td><a href="/death_row/dr_info/rickscedric.html">Inmate Information</a></td>
    <td><a href="/death_row/dr_info/rickscedriclast.html">Last Statement</a></td>
    <td>Ricks</td>
    <td>Cedric</td>
    <td>999593</td>
    <td>51</td>
    <td>03/11/2026</td>
    <td>Black</td>
    <td>Tarrant</td>
  </tr>
</table>
"""

MULTI_PARAGRAPH_STATEMENT_HTML = """
<h3>Last Statement</h3>
<p class="bold">Date of Execution:</p>
<p>March 27, 2018</p>
<p class="bold">Inmate:</p>
<p>Rosendo Rodriguez III</p>
<p class="bold">Last Statement:</p>
<p>First paragraph.</p>
<p>Second paragraph.</p>
<p>Third paragraph.</p>
"""

NO_STATEMENT_HTML = """
<p class="bold">Last Statement:</p>
<p>No statement was made.</p>
"""

PUBLIC_READ_JSON = """var tumblr_api_read = {
  "posts-total": 1,
  "posts": [
    {
      "id": "123",
      "tags": ["John Hummel", "Execution 572"],
      "quote-source": "John Hummel. <br/> <small><a href=\\"https://www.tdcj.texas.gov/death_row/dr_info/hummeljohn.html\\">Offender Information</a> <br/> <a href=\\"https://www.tdcj.texas.gov/death_row/dr_info/hummeljohnlast.html\\">Last Statement</a></small>"
    }
  ]
};"""


def test_parse_executions_html() -> None:
    """Verify execution rows become normalized records.

    The check covers identity fields and the statement URL.
    """
    records = parse_executions_html(EXECUTIONS_HTML)

    assert len(records) == 1
    assert records[0].execution == 598
    assert records[0].full_name == "Cedric Ricks"
    assert records[0].statement_url.endswith("rickscedriclast.html")


def test_parse_statement_html_joins_paragraphs() -> None:
    """Verify multi-paragraph statements become one string.

    Paragraph order and boundaries must remain readable.
    """
    statement = parse_statement_html(MULTI_PARAGRAPH_STATEMENT_HTML)
    assert statement == "First paragraph. Second paragraph. Third paragraph."


def test_parse_statement_html_filters_empty_markers() -> None:
    """Verify no-statement markers produce no quote text.

    This prevents placeholder text from being posted.
    """
    assert parse_statement_html(NO_STATEMENT_HTML) is None


def test_decode_tdcj_response_preserves_smart_punctuation() -> None:
    """Verify TDCJ responses are decoded as UTF-8.

    Requests' fallback encoding must not corrupt punctuation.
    """
    response = Response()
    response._content = "I’m sorry, y’all. Don’t hate me.".encode("utf-8")
    response.encoding = "ISO-8859-1"

    assert decode_tdcj_response(response) == "I’m sorry, y’all. Don’t hate me."


def test_parse_public_read_json_and_extract_statement_url() -> None:
    """Verify legacy Tumblr data yields a statement URL.

    The JavaScript wrapper and quote source HTML are both parsed.
    """
    payload = parse_public_read_json(PUBLIC_READ_JSON)
    post = payload["posts"][0]

    assert payload["posts-total"] == 1
    assert (
        extract_statement_url_from_quote_source(post["quote-source"])
        == "https://www.tdcj.texas.gov/death_row/dr_info/hummeljohnlast.html"
    )


class StubSession(Session):
    """Requests session that returns queued responses."""

    def __init__(self, responses: list[Response]) -> None:
        """Initialize the session with queued responses.

        Args:
            responses: Responses to return in request order.
        """
        super().__init__()
        self.responses = responses
        self.requests: list[PreparedRequest] = []

    def send(self, request: PreparedRequest, **kwargs: object) -> Response:
        """Record a request and return the next response.

        Args:
            request: Prepared request sent by the session.
            **kwargs: Additional request options ignored by the stub.

        Returns:
            Next queued response associated with the request.
        """
        self.requests.append(request)
        response = self.responses.pop(0)
        response.request = request
        return response


def json_response(payload: dict[str, object]) -> Response:
    """Build a successful JSON response for a test.

    Args:
        payload: JSON-compatible response body.

    Returns:
        Response containing the serialized payload.
    """
    response = Response()
    response.status_code = 200
    response._content = json.dumps(payload).encode()
    response.headers["Content-Type"] = "application/json"
    return response


def html_response(payload: str) -> Response:
    """Build a successful HTML response for a test.

    Args:
        payload: HTML response body.

    Returns:
        UTF-8 response containing the HTML.
    """
    response = Response()
    response.status_code = 200
    response._content = payload.encode("utf-8")
    response.headers["Content-Type"] = "text/html; charset=utf-8"
    return response


def test_fetch_executions_uses_new_tdcj_url() -> None:
    """Verify execution fetching uses the replacement URL.

    The returned HTML must also pass through the table parser.
    """
    session = StubSession([html_response(EXECUTIONS_HTML)])

    records = fetch_executions(session, timeout=30)

    assert len(records) == 1
    assert session.requests[0].url == EXECUTIONS_URL
    assert EXECUTIONS_URL.endswith("/death_row/executed_inmates.html")


def test_fetch_existing_quotes_uses_v2_api_when_key_is_available() -> None:
    """Verify credentials select Tumblr's v2 read API.

    The request and returned quote reference are both checked.
    """
    session = StubSession(
        [
            json_response(
                {
                    "meta": {"status": 200, "msg": "OK"},
                    "response": {
                        "total_posts": 1,
                        "posts": [
                            {
                                "id": 123,
                                "tags": ["John Hummel", "Execution 572"],
                                "text": "I’m ready, Warden.",
                                "source": (
                                    '<a href="https://www.tdcj.texas.gov/death_row/'
                                    'dr_info/hummeljohnlast.html">Last Statement</a>'
                                ),
                            }
                        ],
                    },
                }
            )
        ]
    )

    references = fetch_existing_quotes(
        session,
        blog_hostname="lastwords.fyi",
        blog_name="goodbyewarden",
        api_key="consumer-key",
        timeout=30,
    )

    assert len(references) == 1
    assert references[0].execution == 572
    assert references[0].post_id == "123"
    assert references[0].quote_text == "I’m ready, Warden."
    assert session.requests[0].url.startswith(
        "https://api.tumblr.com/v2/blog/goodbyewarden.tumblr.com/posts/quote?"
    )
    assert "api_key=consumer-key" in session.requests[0].url


def test_has_suspicious_encoding_detects_mojibake() -> None:
    """Verify mojibake is distinguished from valid Unicode.

    Common corruption patterns should be marked suspicious.
    """
    assert has_suspicious_encoding("Iâ\x80\x99m sorry.")
    assert has_suspicious_encoding("I did.Â I regret it.")
    assert not has_suspicious_encoding("I’m sorry. Señor García, forgive me.")


def test_validate_created_post_response_accepts_post_id() -> None:
    """Verify a created post identifier signals success.

    A numeric Tumblr identifier is a valid response.
    """
    validate_created_post_response({"id": 1234567890})


def test_validate_created_post_response_rejects_tumblr_error() -> None:
    """Verify Tumblr create errors raise a useful exception.

    The message should identify the failed posting action.
    """
    try:
        validate_created_post_response(
            {
                "meta": {"status": 401, "msg": "Unauthorized"},
                "response": {"errors": ["Not Authorized"]},
            }
        )
    except ValueError as exc:
        assert "Tumblr could not create a post" in str(exc)
    else:
        raise AssertionError("Expected a ValueError for a Tumblr error response.")


def test_validate_tumblr_response_includes_recovery_hint() -> None:
    """Verify Tumblr errors include supplied recovery guidance.

    Both the failed action and hint should reach the caller.
    """
    try:
        validate_tumblr_response(
            {
                "meta": {"status": 401, "msg": "Unauthorized"},
                "response": [{"code": 1016, "detail": "Unable to authorize"}],
            },
            action="authenticate with Tumblr",
            hint="Regenerate the OAuth token and secret.",
        )
    except ValueError as exc:
        assert "Tumblr could not authenticate with Tumblr" in str(exc)
        assert "Regenerate the OAuth token and secret" in str(exc)
    else:
        raise AssertionError("Expected a ValueError for a Tumblr auth error.")


def test_validate_created_post_response_requires_post_id() -> None:
    """Verify create responses require a post identifier.

    A state value alone does not confirm post creation.
    """
    try:
        validate_created_post_response({"state": "published"})
    except ValueError as exc:
        assert "post id" in str(exc)
    else:
        raise AssertionError("Expected a ValueError when no post id is returned.")


def test_parse_oauth_verifier_from_callback_url() -> None:
    """Verify OAuth verifiers parse from URLs or raw text.

    Both supported user input forms should return the verifier.
    """
    assert (
        parse_oauth_verifier(
            "https://lastwords.fyi/?oauth_token=request-token&oauth_verifier=abc123"
        )
        == "abc123"
    )
    assert parse_oauth_verifier("abc123") == "abc123"
