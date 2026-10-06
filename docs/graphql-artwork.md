# Moving artwork from Falcor to GraphQL

Netflix retired the artwork nodes from its Falcor schema. This document
describes the GraphQL client that replaces them, what was measured rather
than assumed, and what is deliberately left open.

**State:** implementation complete, landed as a foundation. 143 tests,
`pylint resources/lib/ tests/` clean.

---

## 1. The finding this rests on

**Netflix' GraphQL endpoint serves non-browser clients.**

`docs/graphql-probe.sh` sends a persisted-query POST to
`https://www.netflix.com/graphql` with `User-Agent: Kodi/20.0`, three session
cookies and no browser fingerprint headers. It receives complete artwork, at
exactly the dimensions seen in the recorded captures.

This was measured on 2026-10-03, not inferred. The script is committed and
re-runnable against a HAR capture, so the claim is reproducible rather than
asserted. Before that probe the approach was a hypothesis; afterwards it is a
measurement anyone can repeat in two minutes.

## 1a. The underlying fault, and its scope

The artwork removal is one symptom of a wider Falcor contraction, reported in
issues #1781 and #1792. The cleanest single demonstration is two adjacent path
requests against the same video:

```
["videos",81605886,"summary"]                  -> 200
["videos",81605886,"boxarts",["_665x375"],"jpg","value"]  -> 404
```

The summary path is served; the artwork path beneath it is gone. That is the
whole fault in two lines — no batch-level analysis needed to see it.

Two further endpoints are also retired:

```
/api/shakti/mre/profiles/switch   -> 404
/api/shakti/mre/profiles/profileLock -> 404
```

Profile switching and the PIN prompt are therefore broken independently of
artwork. **This matters for PR #1796**, which rolls the profile switch back to
`/SwitchProfile`: if the Shakti path is dead, the rollback target is a
different question worth settling before that PR is relied on. The `graphql`
`useProfilesSummaryQuery` operation in this branch is a candidate replacement,
but unlike the artwork work it has not been proven end to end here.

## 2. What the recorded traffic establishes

Derived from seven captures (773 MB) covering three days of activity:

| Fact | Value | Why it matters |
|---|---|---|
| Operation IDs | 21 persisted-query UUIDs | Not guessable. A wrong UUID returns an error, not silently wrong artwork. |
| Persisted version | `102` in all 601 recorded requests | Consistent across three days. |
| Artwork source | `Image` nodes | `itemSummary.assets` **does not exist** — zero occurrences across all seven captures. |
| Image key format | `<ArtType>\|<uuid>\|<locale>[\|variant]` | The uuid segment is not reliably a UUID. Never validate it as one. |
| Auth failure shape | **HTTP 200** with `errors: [UNAUTHENTICATED]` | See §5. This drives the whole transport design. |

## 3. What it replaces

The Falcor artwork nodes are gone from the schema. Concretely:

- `ART_PARTIAL_PATHS` is now empty — the add-on requests no retired artwork
  nodes at all.
- `ArtType`-keyed `Image` nodes supply artwork instead.
- A **halving layer** (`resources/lib/services/nfsession/session/path_blacklist.py`)
  tolerates retired Falcor paths in general. `pathEvaluator` is all-or-nothing
  per batch, so a single dead path failed the whole request; on a 404 the batch
  is now halved and the rejected paths are blacklisted for the session.

## 4. Deliberate divergence from PR #1796

Three fields that PR #1796 removes are actively read by this codebase:

| Field | Consumer |
|---|---|
| `dpSupplementalMessage` | `resources/lib/kodi/infolabels.py:94` |
| `sequiturEvidence` | `resources/lib/services/nfsession/directorybuilder/dir_builder_utils.py:62` |
| `requestId` | `resources/lib/utils/api_paths.py:87`, `dir_builder_utils.py:65` |

Removing them as #1796 does would break four features. Only `requestId` and
`evidence` are removed here, and both removals are pinned by tests.

## 5. The transport, and why it is shaped this way

Netflix signals an expired session as **HTTP 200 with an `errors` array**, not
as a 401. A client that trusts the status code returns empty artwork silently —
no exception, no log entry. That is worse than having no client at all, because
it hides the failure.

Every response is therefore checked for `errors` before `data` is parsed, with
one bounded retry after `try_refresh_session_data()`. The three failure classes
are siblings with no subclassing, so `except GraphQLRequestError` cannot swallow
an expired session.

Two details that the recorded traffic and the existing session layer forced:

- `post_safe` returns the **decoded body** (a dict for JSON, bytes otherwise),
  not a `requests.Response` — see `session/http_requests.py:114-119`. Every
  caller treats it as a dict. A 401 also never reaches the caller as a 401:
  the session layer raises `HttpError401` first, so the client translates it.
- `requests.exceptions.JSONDecodeError` inherits from **both**
  `RequestException` and `ValueError`. The `ValueError` clause is matched first,
  or a malformed body is misreported as a transport failure instead of a
  protocol failure.

Session composition — one `requests.Session`, not two:

```python
class SessionPathRequests(SessionGraphQLRequests, GraphQLClient):
```

`SessionGraphQLRequests` supplies `post_safe` via `SessionAccess`;
`GraphQLClient` supplies the request machinery. Both derive from
`SessionHTTPRequests`, so client and request path share one session.

The `'graphql'` endpoint is registered with `is_api_call: False`. The GraphQL
host is always `www.netflix.com` and must not follow the runtime
`build_identifier` — that is the failure mode of issue #1428.

## 6. Artwork extraction

```
sdp                     -> thumb, landscape
StoryArt                -> fanart
LOGO_BRANDED_HORIZONTAL -> clearlogo  (LOGO_UNBRANDED_HORIZONTAL as fallback)
```

Two refinements the captures forced:

- **Size cutoff.** `sdp` arrives twice, at 342×192 and 665×375. A cutoff keeps
  the preview card. The consequence is documented in code rather than glossed
  over: if Netflix ever serves only 342-wide cards, `thumb` is empty rather than
  a degraded image.
- **Entity scoping.** The request enables `videoMerchEnabled`,
  `hasPromoVideoOverride` and `checkLinearChannel`, and merch entries carry
  **their own** `unifiedEntityId`. A document-wide walk would let a promo video's
  still outrank the requested title's on width. Extraction is scoped to the
  requested entity instead.

The Falcor `itemSummary` card survives as the `poster` fallback. See §8 for why
that booking is not settled.

## 7. Tests

143 tests in 13 files, runnable with `pytest tests/unit`:

| Area | Tests |
|---|---|
| GraphQL artwork mapping | 37 |
| GraphQL transport | 24 |
| Artwork sources | 10 |
| API paths | 9 |
| GraphQL wiring | 9 |
| Path blacklist and resilience | 16 |
| Directory builder, data types, pruning, import surface | 30 |

The suite is validated by mutation testing: known-broken variants were
introduced deliberately and each is caught by a named test. Several tests exist
because mutants survived an earlier round — the ranking in `_pick` was entirely
unpinned until a follow-up round added the tests that kill it, and one
transport test was passing vacuously against a fake that did not mirror what
`post_safe` actually returns.

CI runs `pylint resources/lib/ tests/` and exits non-zero on any message. The
branch is clean.

## 8. What is deliberately not done

**`get_video_art` has no production caller yet.** The client is reachable from
the session hierarchy and tested, but connecting it to a consumer is a separate
change. It is not mechanical: `get_videoid_info` is the only in-session caller
of `get_art` and holds `self`, while `add_info_list_item` runs in the add-on
process and would need a new IPC slot. It also has to be weighed against
`get_art`'s cache, which persists art per video and language. This is a call
for maintainers, not something to guess at.

**The `poster` vs `landscape` booking is open.** The surviving `itemSummary`
card is 342×192 — landscape, not a poster — and the spec says it belongs in
`landscape`. It is currently booked to `poster`, because the slot must not stay
empty while the GraphQL source is unavailable. The code states this rather than
claiming the question is settled.

**Tests run against fixtures, not against Netflix.** Whether `version: 102` is
still accepted cannot be shown by any test in this repository.

## 9. Also not attempted

- `SearchPageQueryResults` — three-level result tree with its own types,
  needs its own abstraction.
- `PreviewModal*` episode queries — cursor paging, different data model.
- `SetEntityThumbRating` — a mutation that changes account state. That decision
  belongs to the user, not to a client library.
- `CarouselPage` — the existing Falcor `lists` path carries the same data.