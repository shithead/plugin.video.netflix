# -*- coding: utf-8 -*-
"""
    Copyright (C) 2026 plugin.video.netflix
    Netflix GraphQL transport

    Netflix answers an unauthenticated GraphQL request with HTTP 200 and an
    'errors' array carrying UNAUTHENTICATED. Every response must therefore be
    inspected before it is parsed, otherwise an expired session looks like an
    empty result.

    `post_safe` hands back the decoded body, never a `requests.Response`, and
    raises for every status that is not a 200. This module therefore translates
    the exceptions of the session layer into the GraphQL taxonomy instead of
    inspecting a status code that never arrives.

    SPDX-License-Identifier: MIT
    See LICENSES/MIT.md for more information.
"""
import copy

import requests.exceptions as req_exceptions

from resources.lib.common.exceptions import (GraphQLAuthError, GraphQLProtocolError,
                                             GraphQLRequestError, HttpError401, HttpError404)
from resources.lib.services.nfsession.graphql.operations import (DEFAULT_VARIABLES, OPERATIONS,
                                                                 PERSISTED_VERSION)
from resources.lib.services.nfsession.session.access import SessionAccess
from resources.lib.services.nfsession.session.http_requests import SessionHTTPRequests
from resources.lib.utils.logging import LOG

GRAPHQL_ENDPOINT = 'https://www.netflix.com/graphql'
"""The absolute address the 'graphql' entry of ENDPOINTS resolves to

The address the request actually goes to is composed by the HTTP layer from
BASE_URL and ENDPOINTS['graphql']['address']. This constant is not that
composition - it is the readable form of it, used in the exception messages
below so a failure names a URL a reader can paste into a browser. A test
asserts it against the composition, so the two cannot drift apart silently.
"""

MAX_LOGGED_ERRORS = 3
"""How many entries of a GraphQL errors array reach an exception message"""

MAX_ERROR_MESSAGE_CHARS = 500
"""Cap on one logged error entry, in characters

An 'errors' array is server-controlled in both length and content: one entry
per requested entity, each with a message of arbitrary size. Interpolating it
whole into an exception message would put unbounded content into the add-on
log. Both caps keep the shape of the failure - how many errors, and what the
first ones said - without copying an arbitrary server document into a file.
"""

UNAUTHENTICATED = 'unauthenticated'
"""Lowercase marker Netflix puts in the message of a rejected session"""


def is_unauthenticated(errors):
    """
    Check whether a GraphQL errors array signals an authentication failure

    The live probe received one {'message': 'UNAUTHENTICATED'} entry per
    requested entity, so the array length carries no information.

    :param errors: the 'errors' array of a GraphQL response, may be None
    :type errors: list
    :return: True when any entry reports an unauthenticated session
    :rtype: bool
    """
    for entry in errors or []:
        message = entry.get('message', '') if isinstance(entry, dict) else entry
        if UNAUTHENTICATED in str(message).lower():
            return True
    return False


def _summarise_errors(errors):
    """
    Render a GraphQL errors array for an exception message, bounded in both directions

    The array is server-controlled: one entry per requested entity, each with
    a message of arbitrary length. This keeps the first MAX_LOGGED_ERRORS
    entries, truncates each of them, and states how many were left out, so
    the log says what failed and how much of it without copying an arbitrary
    server document into a file.

    :param errors: the 'errors' array of a GraphQL response
    :type errors: list
    :return: a one-line rendering of the array
    :rtype: str
    """
    entries = list(errors)[:MAX_LOGGED_ERRORS]
    rendered = []
    for entry in entries:
        message = entry.get('message', '') if isinstance(entry, dict) else entry
        message = str(message)
        if len(message) > MAX_ERROR_MESSAGE_CHARS:
            message = message[:MAX_ERROR_MESSAGE_CHARS] + '...'
        rendered.append(message)
    omitted = len(errors) - len(entries)
    summary = '; '.join(rendered)
    if omitted:
        summary += f'; and {omitted} more error(s) omitted'
    return summary


class GraphQLClient(SessionHTTPRequests):
    """Perform persisted-query GraphQL requests against the Netflix endpoint

    This class is not usable on its own. `post_safe` - the login-guarded entry
    point it posts through - is defined on SessionAccess, while this class
    inherits only the session and endpoint machinery of SessionHTTPRequests. A
    consumer must compose both halves into one session class, the way Task 4
    does it in path_requests.py:

        class SessionPathRequests(SessionGraphQLRequests, GraphQLClient):
            '''Manages the PATH requests'''

    Composed, the MRO resolves `post_safe` to SessionAccess and both halves
    share one `requests.Session`. Instantiating GraphQLClient alone instead
    raises an AttributeError on the first `graphql_request`, because nothing in
    its own MRO defines `post_safe`.
    """

    def graphql_request(self, operation_name, variables=None):
        """
        Execute a persisted-query operation and return its 'data' object

        :param operation_name: key of the persisted-query catalogue
        :type operation_name: str
        :param variables: per-request variables, merged over the defaults
        :type variables: dict
        :return: the parsed 'data' object
        :rtype: dict
        :raises GraphQLProtocolError: unknown operation, non-auth GraphQL error,
                                      or a 200 response carrying neither data nor errors
        :raises GraphQLRequestError: the request itself failed
        :raises GraphQLAuthError: the session was rejected and could not be renewed
        """
        if operation_name not in OPERATIONS:
            raise GraphQLProtocolError(f'Unknown GraphQL operation: {operation_name}')
        payload = self._build_payload(operation_name, variables)
        try:
            decoded = self._post(payload)
        except GraphQLAuthError:
            # Netflix signals a rejected session in two ways: UNAUTHENTICATED in
            # the body of an HTTP 200 (the form the live probe recorded) and an
            # HTTP 401. Both mean the same thing, so both must reach the refresh.
            return self._recover_auth(operation_name, payload)
        body = self._parse(operation_name, decoded)
        if is_unauthenticated(body.get('errors')):
            return self._recover_auth(operation_name, payload)
        return self._data(operation_name, body)

    def _build_payload(self, operation_name, variables):
        """
        Assemble the request body: merged variables plus the persisted query

        The defaults are deep-copied, because DEFAULT_VARIABLES holds mutable
        values (an empty 'artworkContext' dict) that are shared by every
        request of the session.

        authURL is not set here. The 'graphql' entry in ENDPOINTS declares
        add_auth_url 'to_data', so the HTTP layer appends it to the body -
        the same path the live probe used.

        :param operation_name: key of the persisted-query catalogue
        :type operation_name: str
        :param variables: per-request variables, merged over the defaults
        :type variables: dict
        :return: the body of the GraphQL request
        :rtype: dict
        """
        merged = copy.deepcopy(DEFAULT_VARIABLES.get(operation_name, {}))
        merged.update(variables or {})
        return {
            'operationName': operation_name,
            'variables': merged,
            'extensions': {'persistedQuery': {'id': OPERATIONS[operation_name],
                                              'version': PERSISTED_VERSION}},
        }

    def _post(self, payload):
        """
        Send the body to the GraphQL endpoint and return the decoded response

        `post_safe` never returns a `requests.Response`. The HTTP layer decodes
        the body itself and raises for every status that is not a 200
        (http_requests.py:108-119), so there is no status code to inspect here
        and this method translates exceptions instead.

        The payload is passed as a dict on purpose: with a pre-serialized
        string the authURL handling of _prepare_request_properties appends
        '&authURL=...' to the JSON and produces an unparsable body.

        NotLoggedInError and NotConnected are deliberately not caught: they are
        the signals the session layer raises to drive the login flow, and
        nfsession_ops.py already handles them.

        :param payload: the body of the GraphQL request
        :type payload: dict
        :return: the decoded body, a dict for JSON, the raw bytes otherwise
        :rtype: dict|bytes
        :raises GraphQLAuthError: the endpoint rejected the session with HTTP 401
        :raises GraphQLRequestError: the request failed or the endpoint answered HTTP 404
        :raises GraphQLProtocolError: the body announced JSON but could not be decoded
        """
        try:
            # post_safe is supplied by SessionAccess, which this class does not inherit;
            # the composed session class provides both. See the class docstring.
            return self.post_safe(endpoint='graphql', params={}, data=payload)  # pylint: disable=no-member
        except HttpError401 as exc:
            raise GraphQLAuthError(f'GraphQL request to {GRAPHQL_ENDPOINT} was rejected with HTTP 401') from exc
        except HttpError404 as exc:
            # Not a retired path. The HTTP layer already attempted a session
            # refresh before raising this, and a GraphQL operation addresses no
            # per-item path, so a 404 here means the endpoint address itself is
            # wrong - retrying it cannot succeed.
            raise GraphQLRequestError(f'GraphQL endpoint {GRAPHQL_ENDPOINT} answered HTTP 404') from exc
        except ValueError as exc:
            # This clause must stay above the RequestException one, and the order
            # is deliberate, not arbitrary. requests.exceptions.JSONDecodeError
            # inherits from RequestException AND from ValueError
            # (InvalidJSONError -> RequestException -> OSError -> JSONDecodeError
            # -> ValueError), so with RequestException first a malformed body
            # would be misreported as a transport failure.
            raise GraphQLProtocolError('GraphQL response announced JSON but could not be decoded') from exc
        except req_exceptions.RequestException as exc:
            raise GraphQLRequestError(f'GraphQL request to {GRAPHQL_ENDPOINT} failed: {exc}') from exc

    @staticmethod
    def _data(operation_name, body):
        """
        Extract the data object of a GraphQL response

        :param operation_name: key of the persisted-query catalogue
        :type operation_name: str
        :param body: the decoded response body
        :type body: dict
        :return: the data object of the response
        :rtype: dict
        :raises GraphQLProtocolError: the body carries GraphQL errors or no data at all
        """
        if body.get('errors'):
            raise GraphQLProtocolError(
                f'GraphQL returned errors for {operation_name}: {_summarise_errors(body["errors"])}')
        if body.get('data') is None:
            raise GraphQLProtocolError(f'GraphQL response for {operation_name} carried no data')
        return body['data']

    @staticmethod
    def _parse(operation_name, decoded):
        """
        Validate the body that post_safe handed back

        The HTTP layer returns the raw bytes whenever the content-type is not
        JSON, which is what an HTML WAF or captcha page arrives with. Such a
        body is not a GraphQL response and must never be read as an empty one.

        :param operation_name: key of the persisted-query catalogue
        :type operation_name: str
        :param decoded: the value post_safe returned, a dict or raw bytes
        :type decoded: dict|bytes
        :return: the decoded body of the response
        :rtype: dict
        :raises GraphQLProtocolError: the body is not a JSON object
        """
        if isinstance(decoded, (bytes, bytearray)):
            raise GraphQLProtocolError(
                f'GraphQL response for {operation_name} was not JSON: '
                f'{len(decoded)} bytes of non-JSON content, e.g. a WAF or captcha page')
        if not isinstance(decoded, dict):
            raise GraphQLProtocolError(f'GraphQL response for {operation_name} was not a JSON object')
        return decoded

    def _recover_auth(self, operation_name, payload):
        """
        Renew the session and retry the request exactly once

        The retry reuses the same payload, but the endpoint configuration
        appends the renewed auth_url to it again. A second rejection is final,
        in either of the two forms: a renewed UNAUTHENTICATED answer raises
        below, and a renewed HTTP 401 arrives from _post already translated to
        GraphQLAuthError. This never loops.

        :param operation_name: key of the persisted-query catalogue
        :type operation_name: str
        :param payload: the body of the rejected GraphQL request
        :type payload: dict
        :return: the parsed 'data' object of the retry
        :rtype: dict
        :raises GraphQLAuthError: the renewed session was rejected as well
        :raises GraphQLRequestError: the retry itself failed
        :raises GraphQLProtocolError: the retry answered GraphQL errors or no data
        """
        LOG.warn('GraphQL rejected the session for {}, attempting a session refresh', operation_name)
        if not self.try_refresh_session_data():
            raise GraphQLAuthError('GraphQL session rejected and could not be refreshed')
        try:
            decoded = self._post(payload)
        except GraphQLRequestError as exc:
            raise GraphQLAuthError('GraphQL retry after session refresh failed') from exc
        body = self._parse(operation_name, decoded)
        if is_unauthenticated(body.get('errors')):
            raise GraphQLAuthError('GraphQL session still rejected after refresh')
        return self._data(operation_name, body)


class SessionGraphQLRequests(SessionAccess):
    """Expose the GraphQL client through the session hierarchy"""
