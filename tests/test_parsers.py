from lastwords.tdcj import parse_executions_html, parse_statement_html
from lastwords.tumblr import (
    extract_statement_url_from_quote_source,
    parse_public_read_json,
    validate_created_post_response,
    validate_tumblr_response,
)

EXECUTIONS_HTML = """
<table class="tdcj_table indent">
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
    records = parse_executions_html(EXECUTIONS_HTML)

    assert len(records) == 1
    assert records[0].execution == 598
    assert records[0].full_name == "Cedric Ricks"
    assert records[0].statement_url.endswith("rickscedriclast.html")


def test_parse_statement_html_joins_paragraphs() -> None:
    statement = parse_statement_html(MULTI_PARAGRAPH_STATEMENT_HTML)
    assert statement == "First paragraph. Second paragraph. Third paragraph."


def test_parse_statement_html_filters_empty_markers() -> None:
    assert parse_statement_html(NO_STATEMENT_HTML) is None


def test_parse_public_read_json_and_extract_statement_url() -> None:
    payload = parse_public_read_json(PUBLIC_READ_JSON)
    post = payload["posts"][0]

    assert payload["posts-total"] == 1
    assert (
        extract_statement_url_from_quote_source(post["quote-source"])
        == "https://www.tdcj.texas.gov/death_row/dr_info/hummeljohnlast.html"
    )


def test_validate_created_post_response_accepts_post_id() -> None:
    validate_created_post_response({"id": 1234567890})


def test_validate_created_post_response_rejects_tumblr_error() -> None:
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
    try:
        validate_created_post_response({"state": "published"})
    except ValueError as exc:
        assert "post id" in str(exc)
    else:
        raise AssertionError("Expected a ValueError when no post id is returned.")
