# -*- coding: utf-8 -*-
"""Tests for the GraphQL transport, in particular the HTTP-200 auth path.

The fake post_safe below mirrors what the real one does after the response has
arrived (http_requests.py:108-119): it returns the decoded body and it raises
for every status that is not a 200. It deliberately does not return a
requests.Response, because that is not what production hands back.
"""
import json

import pytest
import requests.exceptions as req_exceptions

from resources.lib.common.exceptions import (GraphQLAuthError, GraphQLProtocolError,
                                             GraphQLRequestError, HttpError401, HttpError404)
from resources.lib.globals import G
from resources.lib.services.nfsession.graphql import client as gql
from resources.lib.services.nfsession.session.endpoints import BASE_URL, ENDPOINTS


class _FakeLocalDb:
    """Stand-in for the session database the HTTP layer reads auth_url from."""

    def __init__(self):
        """Start with an empty store, as after a fresh login"""
        self.values = {}

    def get_active_profile_guid(self):
        """
        Return the guid of the active profile

        :return: a fixed profile guid
        :rtype: str
        """
        return 'ABCDEF'

    def get_value(self, key, table=None):
        """
        Return the value of a session database entry

        :param key: name of the entry
        :type key: str
        :param table: name of the table the entry is stored in
        :type table: str
        :return: the stored value, an empty string when unknown
        :rtype: str
        """
        del table
        return self.values.get(key, '')

    def set_value(self, key, value, table=None):
        """
        Store a value in the session database

        :param key: name of the entry
        :type key: str
        :param value: the value to store
        :type value: str
        :param table: name of the table the entry is stored in
        :type table: str
        """
        del table
        self.values[key] = value


@pytest.fixture(autouse=True)
def _session_db(monkeypatch):
    """Provide the session database that `_prepare_request_properties` reads.

    The real one only exists after `run_addon`. The transport must go through
    `_prepare_request_properties`, otherwise the endpoint configuration stays
    untested.
    """
    monkeypatch.setattr(G, 'LOCAL_DB', _FakeLocalDb(), raising=False)


def _make_client(outcomes, refreshed=None):
    """
    Build a GraphQLClient whose fake post_safe reproduces the real contract

    Only the network call is replaced: the endpoint lookup, the body
    serialisation and the authURL injection are the production code.

    An outcome is either a dict, which post_safe returns for a JSON body, bytes,
    which it returns for any other content-type, or an exception instance, which
    it raises. That is the full set of behaviours of the real `_request` at
    http_requests.py:108-119: HttpError401 for a 401, HttpError404 for a 404,
    HTTPError for any other error status, JSONDecodeError for a body that
    announced JSON and then failed to parse, and ConnectionError when the socket
    itself failed. The last outcome repeats, so a single-element list models a
    server that keeps answering the same way.

    :param outcomes: what post_safe does, in order, the last one repeating
    :type outcomes: list
    :param refreshed: value returned by the fake try_refresh_session_data
    :type refreshed: bool
    :return: a client instance wired to the fakes
    :rtype: resources.lib.services.nfsession.graphql.client.GraphQLClient
    """
    instance = gql.GraphQLClient.__new__(gql.GraphQLClient)
    instance.auth_url = 'https://example/auth'
    instance.sent = []
    instance.sent_params = []
    instance.sent_bodies = []

    # pylint: disable=unused-argument,protected-access
    def post_safe(endpoint, params=None, data=None, **kwargs):
        del kwargs
        body, _headers, sent_params = instance._prepare_request_properties(
            ENDPOINTS[endpoint], {'params': params or {}, 'data': data})
        instance.sent_params.append(sent_params)
        instance.sent.append(json.loads(body))
        instance.sent_bodies.append(data)
        if len(instance.sent) > 2:
            raise AssertionError('the client sent more than two requests, it is looping')
        outcome = outcomes.pop(0) if len(outcomes) > 1 else outcomes[0]
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    instance.post_safe = post_safe
    instance.try_refresh_session_data = refreshed if refreshed else (lambda: True)
    return instance


def test_request_body_carries_operation_persisted_query_and_version():
    """The wire format is operationName plus variables plus persistedQuery, no query string."""
    client = _make_client([{'data': {}}])
    client.graphql_request('DetailModal', {'videoId': 1, 'unifiedEntityId': 'Video:1'})
    sent = client.sent[0]
    assert sent['operationName'] == 'DetailModal'
    assert sent['extensions']['persistedQuery'] == {
        'id': 'e5748389-c3b9-496e-bcea-64883cff1e87', 'version': 102}
    assert 'query' not in sent
    # The persisted-query form sends the id and nothing else: no query string
    # and no hash. An implementation that sent both the id and a sha256Hash
    # would still satisfy the assertion above, and Netflix would answer
    # PersistedQueryNotFound.
    assert 'sha256Hash' not in json.dumps(sent)
    assert sent['variables']['videoId'] == 1
    assert sent['variables']['opaqueImageFormat'] == 'JPG'


def test_caller_variables_override_defaults():
    """A caller may set a field that also exists in DEFAULT_VARIABLES."""
    client = _make_client([{'data': {}}])
    client.graphql_request('DetailModal', {'videoId': 1, 'promoVideoId': 42})
    assert client.sent[0]['variables']['promoVideoId'] == 42


def test_returns_data_on_success():
    """A 200 without errors yields the data object unchanged."""
    payload = {'data': {'playbackEntities': [], 'unifiedEntities': []}}
    client = _make_client([payload])
    assert client.graphql_request('DetailModal', {'videoId': 1}) == payload['data']


def test_unknown_operation_raises_protocol_error():
    """An operation absent from the catalogue is refused before any request."""
    client = _make_client([{'data': {}}])
    with pytest.raises(GraphQLProtocolError):
        client.graphql_request('NoSuchOperation', {})
    assert not client.sent, 'no request must have been sent'


def test_server_error_raises_request_error():
    """Mirrors a Netflix 500: `raise_for_status` raises HTTPError in the HTTP layer.

    The status never reaches the client, so the client can only translate the
    exception - it cannot read a status code off the return value.
    """
    client = _make_client([req_exceptions.HTTPError('500 Server Error')])
    with pytest.raises(GraphQLRequestError):
        client.graphql_request('DetailModal', {'videoId': 1})


def test_transport_failure_raises_request_error():
    """Mirrors a timeout or a dropped connection: requests raises ConnectionError."""
    client = _make_client([req_exceptions.ConnectionError('connection refused')])
    with pytest.raises(GraphQLRequestError):
        client.graphql_request('DetailModal', {'videoId': 1})


def test_malformed_json_body_raises_protocol_error():
    """Mirrors a 200 whose content-type says JSON but whose body does not parse.

    requests raises JSONDecodeError from the decoding inside the HTTP layer.
    That class is both a RequestException and a ValueError, so this assertion
    also pins the clause order in `_post`: with the RequestException clause
    first this would be reported as a transport failure instead.
    """
    client = _make_client([req_exceptions.JSONDecodeError('Expecting value', '', 0)])
    with pytest.raises(GraphQLProtocolError):
        client.graphql_request('DetailModal', {'videoId': 1})


def test_non_json_body_raises_protocol_error():
    """Mirrors a WAF or captcha interstitial: HTTP 200, content-type text/html.

    The HTTP layer returns the raw bytes for any non-JSON content-type, so this
    body really does arrive as bytes and must not be read as an empty result.
    """
    html = b'<!DOCTYPE html><html><head><title>Access Denied</title></head></html>'
    client = _make_client([html])
    with pytest.raises(GraphQLProtocolError) as raised:
        client.graphql_request('DetailModal', {'videoId': 1})
    # The message must name the raw content, so the diagnostic says what
    # actually arrived instead of only "not a JSON object".
    assert f'{len(html)} bytes' in str(raised.value)


def test_http_200_with_unauthenticated_errors_raises_auth_error():
    """The live probe's unauthenticated control call: 200 plus UNAUTHENTICATED.

    This is the case the whole task exists for. Asserting on a 401 here
    would miss the entire failure mode.
    """
    body = {'data': None, 'errors': [{'message': 'UNAUTHENTICATED'}] * 4}
    client = _make_client([body], refreshed=lambda: True)
    with pytest.raises(GraphQLAuthError):
        client.graphql_request('DetailModal', {'videoId': 1})


def test_unauthenticated_retries_once_after_session_refresh():
    """A refresh that succeeds buys exactly one more attempt."""
    body = {'data': None, 'errors': [{'message': 'UNAUTHENTICATED'}]}
    calls = []

    def refreshed():
        calls.append(1)
        return True

    client = _make_client([body], refreshed=refreshed)
    with pytest.raises(GraphQLAuthError):
        client.graphql_request('DetailModal', {'videoId': 1})
    assert len(client.sent) == 2, 'expected exactly one retry, not a loop'
    assert len(calls) == 1, 'session refresh must be attempted exactly once'


def test_unauthenticated_does_not_retry_when_refresh_fails():
    """A refresh that fails short-circuits instead of retrying blindly."""
    body = {'data': None, 'errors': [{'message': 'UNAUTHENTICATED'}]}
    client = _make_client([body], refreshed=lambda: False)
    with pytest.raises(GraphQLAuthError):
        client.graphql_request('DetailModal', {'videoId': 1})
    assert len(client.sent) == 1


def test_retry_recovers_when_the_second_attempt_succeeds():
    """The retry is not merely defensive: it can deliver the data."""
    unauth = {'data': None, 'errors': [{'message': 'UNAUTHENTICATED'}]}
    good = {'data': {'unifiedEntities': [{'videoId': 1}]}}
    client = _make_client([unauth, good], refreshed=lambda: True)
    assert client.graphql_request('DetailModal', {'videoId': 1}) == {
        'unifiedEntities': [{'videoId': 1}]}


def test_http_401_raises_auth_error_and_refreshes_the_session():
    """Mirrors Netflix answering 401 for an expired session.

    The probe only ever saw the 200-with-UNAUTHENTICATED form, so the status
    form needs its own coverage: an untranslated HttpError401 would escape the
    GraphQL taxonomy and skip the refresh this task exists to provide.
    """
    calls = []

    def refreshed():
        calls.append(1)
        return True

    client = _make_client([HttpError401()], refreshed=refreshed)
    with pytest.raises(GraphQLAuthError):
        client.graphql_request('DetailModal', {'videoId': 1})
    assert len(calls) == 1, 'a 401 must reach the refresh path, exactly once'
    assert len(client.sent) == 2, 'expected exactly one retry, not a loop'


def test_http_401_recovers_when_the_retry_succeeds():
    """A 401 followed by a good answer proves the 401 took the refresh path.

    Without this, the test above would also pass if the 401 were merely
    re-labelled instead of being recovered from.
    """
    good = {'data': {'unifiedEntities': [{'videoId': 1}]}}
    calls = []

    def refreshed():
        calls.append(1)
        return True

    client = _make_client([HttpError401(), good], refreshed=refreshed)
    assert client.graphql_request('DetailModal', {'videoId': 1}) == {
        'unifiedEntities': [{'videoId': 1}]}
    assert len(calls) == 1
    assert len(client.sent) == 2


def test_http_404_raises_request_error():
    """Mirrors a wrong endpoint address: the session layer raises HttpError404.

    A GraphQL operation addresses no per-item path, so - unlike a retired
    Falcor path - there is nothing to skip and retry. It is a request error,
    not an auth error, and must not spend the session refresh.
    """
    calls = []

    def refreshed():
        calls.append(1)
        return True

    client = _make_client([HttpError404()], refreshed=refreshed)
    with pytest.raises(GraphQLRequestError):
        client.graphql_request('DetailModal', {'videoId': 1})
    assert len(client.sent) == 1, 'a 404 must not be retried'
    assert not calls, 'a 404 must not spend the session refresh'


def test_non_auth_errors_do_not_trigger_a_retry():
    """A GraphQL-level error that is not auth must not consume the session refresh."""
    body = {'data': None, 'errors': [{'message': 'PersistedQueryNotFound'}]}
    client = _make_client([body], refreshed=lambda: True)
    with pytest.raises(GraphQLProtocolError):
        client.graphql_request('DetailModal', {'videoId': 1})
    assert len(client.sent) == 1


def test_the_errors_array_is_truncated_in_the_message():
    """An errors array is server-controlled in length and content.

    The live probe already produced one entry per requested entity, and every
    message is arbitrary text from the server. Interpolating the whole array
    would put unbounded content into the add-on log, so the message keeps the
    first entries, truncates each one, and says how many it left out - which
    is the part that says whether the failure was one title or the whole page.
    """
    errors = [{'message': f'error {index} ' + 'x' * 4000} for index in range(50)]
    client = _make_client([{'data': None, 'errors': errors}])
    with pytest.raises(GraphQLProtocolError) as raised:
        client.graphql_request('DetailModal', {'videoId': 1})
    message = str(raised.value)
    assert 'error 0' in message, 'the message must name what the server said'
    assert 'error 1' in message
    assert 'error 2' in message
    assert 'error 3' not in message, 'the array must be capped'
    assert '47 more error(s) omitted' in message, 'the message must say how much was dropped'
    assert len(message) < 4 * gql.MAX_ERROR_MESSAGE_CHARS, 'each entry must be truncated'


def test_a_single_huge_error_message_is_truncated():
    """One entry can be arbitrarily long on its own, without a long array."""
    errors = [{'message': 'y' * 100000}]
    client = _make_client([{'data': None, 'errors': errors}])
    with pytest.raises(GraphQLProtocolError) as raised:
        client.graphql_request('DetailModal', {'videoId': 1})
    message = str(raised.value)
    assert len(message) < 1000
    assert message.endswith('...'), 'a truncated message must say that it was cut'


def test_200_with_neither_data_nor_errors_raises_protocol_error():
    """An empty 200 body must not be mistaken for success."""
    client = _make_client([{}])
    with pytest.raises(GraphQLProtocolError):
        client.graphql_request('DetailModal', {'videoId': 1})


def test_defaults_are_deep_copied_into_the_payload():
    """A caller writing into the payload must not corrupt the module catalogue.

    DEFAULT_VARIABLES['DetailModal']['artworkContext'] is one empty dict shared
    by every request of the whole session. A shallow copy would leave it
    reachable from the returned payload.
    """
    client = _make_client([{'data': {}}])
    client.graphql_request('DetailModal', {'videoId': 1})
    client.sent_bodies[0]['variables']['artworkContext']['artworkType'] = 'HERO'
    client.graphql_request('DetailModal', {'videoId': 2})
    assert not client.sent_bodies[1]['variables']['artworkContext'], 'the second payload inherited the mutation'
    assert not gql.DEFAULT_VARIABLES['DetailModal']['artworkContext'], 'the catalogue was corrupted'


def test_post_safe_comes_from_the_session_access_half():
    """GraphQLClient itself has no post_safe: that lives on SessionAccess.

    The client is only usable composed into the session hierarchy, and the
    real composed class is SessionPathRequests, asserted in
    test_graphql_wiring.py. Asserting against a class this test builds itself
    proves nothing about the codebase: it would keep passing if the module
    never composed anything. What is load-bearing here is the negative half -
    the transport class must not define post_safe, or the composition
    requirement documented on it is a lie and a reader would instantiate
    GraphQLClient alone and get a different object than the one that works.
    """
    assert not hasattr(gql.GraphQLClient, 'post_safe'), (
        'post_safe must come from SessionAccess, not from the transport class itself')


def test_endpoint_constant_is_the_url_actually_requested():
    """The constant and the composition the HTTP layer performs must agree.

    GRAPHQL_ENDPOINT is only read for the exception messages; the request
    itself goes to BASE_URL + ENDPOINTS['graphql']['address']. Asserting the
    constant against a literal gave false assurance - it could drift from the
    endpoint table and stay green. Composing the real URL and comparing it to
    the constant pins the thing that is actually requested.
    """
    assert BASE_URL + ENDPOINTS['graphql']['address'] == gql.GRAPHQL_ENDPOINT


def test_endpoint_entry_is_registered():
    """post_safe resolves the endpoint through ENDPOINTS, so the key must exist.

    The fake above replaces post_safe and would hide a missing entry; only
    this test sees the real lookup table.
    """
    assert 'graphql' in ENDPOINTS
    conf = ENDPOINTS['graphql']
    assert conf['address'] == '/graphql'
    assert conf['is_api_call'] is False
    assert conf['use_default_params'] is False
    assert conf['add_auth_url'] == 'to_data'
    assert conf['content_type'] == 'application/json'


def test_auth_url_is_carried_in_the_body_not_the_query():
    """The probe sent authURL inside the JSON body."""
    client = _make_client([{'data': {}}])
    client.graphql_request('DetailModal', {'videoId': 1})
    assert client.sent[0]['authURL'] == 'https://example/auth'
    assert client.sent_params[0] == {}, 'no query parameters were sent'
