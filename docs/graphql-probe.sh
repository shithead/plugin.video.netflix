#!/usr/bin/env bash
# Counter-check: does Netflix' GraphQL endpoint answer a non-browser client?
#
# This question decides whether stage C2 of the plan delta holds or is dead.
# A HAR cannot answer it — all 282 recorded calls come from a browser with a
# full header set.
#
# The script reads the cookie and headers from the HAR and sends a
# DetailModal call with curl. It writes the cookies nowhere: they are fed
# from the HAR into a shell variable and never land in the history in clear
# text.
#
# Usage:
#   ./docs/graphql-probe.sh <path-to-har> [videoId]
#
# Examples:
#   ./docs/graphql-probe.sh references/sanitized.har
#   ./docs/graphql-probe.sh references/sanitized.har 82137232

set -uo pipefail

HAR="${1:-}"
VIDEO_ID="${2:-}"

if [[ -z "$HAR" || ! -f "$HAR" ]]; then
  echo "ERROR: HAR not found: ${HAR:-<empty>}" >&2
  echo "Usage: $0 <path-to-har> [videoId]" >&2
  exit 2
fi

command -v jq   >/dev/null || { echo "ERROR: jq missing"   >&2; exit 2; }
command -v curl >/dev/null || { echo "ERROR: curl missing" >&2; exit 2; }

# ---------------------------------------------------------------------------
# 1. Pull the cookie and the authURL out of the HAR
# ---------------------------------------------------------------------------
# 'Cookie' is one concatenated field; the comma-separated pairs inside it must
# not be broken apart by -s / gsub. Hence jq instead of grep.
COOKIE_JAR="$(jq -r '
  [ .log.entries[]
    | select(.request.url | test("/graphql"))
    | .request.headers[]?
    | select((.name | ascii_downcase) == "cookie")
    | .value ][0] // "" ' "$HAR")"

if [[ -z "$COOKIE_JAR" ]]; then
  echo "ERROR: no Cookie header found in the HAR." >&2
  echo "Did you export the capture with 'Save all as HAR with content'?" >&2
  exit 3
fi

AUTH_URL="$(jq -r '
  [ .log.entries[]
    | select(.request.url | test("pathEvaluator"))
    | (.request.postData.text // "")
    | capture("authURL=(?<v>[^&]+)")?.v ][0] // "" ' "$HAR" 2>/dev/null || true)"

if [[ -z "$AUTH_URL" ]]; then
  echo "NOTE: no authURL in the HAR — the capture was presumably already"
  echo "      sanitised. The call runs without authURL; a 401 would then be a"
  echo "      finding about the auth, not about the client type."
fi

# Keep only the three session cookies. The rest (consent, GSID, feature
# flags) is irrelevant for the counter-check and would only send needless
# identifiers.
SESSION_COOKIE="$(printf '%s' "$COOKIE_JAR" \
  | tr ';' '\n' \
  | grep -E '^[[:space:]]*(NetflixId|SecureNetflixId|nfvdid)=' \
  | sed 's/^[[:space:]]*//' \
  | paste -sd';' -)"

echo "Session cookies found:"
printf '  %s\n' "$SESSION_COOKIE" | sed 's/=.\{0,12\}.*/=<truncated>/' | sed 's/^/  /'

# ---------------------------------------------------------------------------
# 2. The call, exactly as the browser sends it
# ---------------------------------------------------------------------------
DETAIL_MODAL_ID="e5748389-c3b9-496e-bcea-64883cff1e87"
PERSISTED_VERSION=102

if [[ -z "$VIDEO_ID" ]]; then
  # Take an ID from the HAR so the call is guaranteed to hit a real video.
  VIDEO_ID="$(jq -r '
    [ .log.entries[]
      | select(.request.url | test("/graphql"))
      | (.request.postData.text // "")
      | capture("\"videoId\":(?<v>[0-9]+)")?.v ][0] // empty' "$HAR")"
  echo "No videoId given — taken from the HAR: ${VIDEO_ID:-<none>}"
fi

if [[ -z "$VIDEO_ID" ]]; then
  echo "ERROR: no videoId could be determined. Pass it explicitly as the 2nd argument." >&2
  exit 4
fi

BODY="$(jq -nc --arg v "$VIDEO_ID" --arg id "$DETAIL_MODAL_ID" --argjson ver "$PERSISTED_VERSION" '{
  operationName: "DetailModal",
  variables: {
    opaqueImageFormat: "JPG", transparentImageFormat: "PNG",
    videoMerchEnabled: true, fetchPromoVideoOverride: false,
    hasPromoVideoOverride: true, promoVideoId: 0,
    videoMerchContext: "BROWSE", isLiveEpisodic: false,
    includeCroppedLogo: false, artworkContext: {},
    textEvidenceUiContext: "ODP",
    unifiedEntityId: ("Video:" + $v), videoId: ($v | tonumber),
    checkLinearChannel: true
  },
  extensions: { persistedQuery: { id: $id, version: $ver } }
}')"

if [[ -n "$AUTH_URL" ]]; then
  BODY="$(jq -nc --argjson b "$BODY" --arg a "$AUTH_URL" '$b + {authURL: $a}')"
fi

ENDPOINT="https://www.netflix.com/graphql"

echo
echo "POST $ENDPOINT"
echo "  operationName   DetailModal"
echo "  videoId         $VIDEO_ID"
echo "  persistedQuery  $DETAIL_MODAL_ID v$PERSISTED_VERSION"
echo "  User-Agent      Kodi/20.0 (not the browser UA)"
echo
echo "=================================================================="
echo

# Unauthenticated control call: the same request entirely without cookies.
# Separates "client type is rejected" from "session is invalid".
echo "--- Control call: no cookies ---"
CTRL_STATUS="$(curl -sS -o /tmp/nf_graphql_noauth.json -w '%{http_code}' \
  --compressed \
  -X POST "$ENDPOINT" \
  -H 'content-type: application/json' \
  -H 'x-netflix.context.operation-name: DetailModal' \
  -H 'x-netflix.context.ui-flavor: akira' \
  -H 'User-Agent: Kodi/20.0' \
  --data "$BODY" 2>&1 || echo "000")"
echo "HTTP $CTRL_STATUS"
jq -r '(if .errors then (.errors | map(.message // .) | join(" | ")) else "(no errors object)" end)' \
   /tmp/nf_graphql_noauth.json 2>/dev/null | head -5 || head -c 300 /tmp/nf_graphql_noauth.json
echo
echo

echo "--- Main run: with session cookies, Kodi User-Agent ---"
STATUS="$(curl -sS -o /tmp/nf_graphql_kodi.json -w '%{http_code}' \
  --compressed \
  -X POST "$ENDPOINT" \
  -H 'content-type: application/json' \
  -H 'x-netflix.context.operation-name: DetailModal' \
  -H 'x-netflix.context.ui-flavor: akira' \
  -H 'x-netflix.context.hawkins-version: 5.30.0' \
  -H 'x-netflix.context.app-version: v7e4a1fe8' \
  -H 'x-netflix.context.locales: de-DE' \
  -H "Cookie: $SESSION_COOKIE" \
  -H 'User-Agent: Kodi/20.0' \
  --data "$BODY" 2>&1 || echo "000")"
echo "HTTP $STATUS"

rm -f /tmp/nf_graphql_noauth.json

if [[ "$STATUS" == "200" ]]; then
  echo
  echo ">>> IT ANSWERED. The GraphQL path is open."
  echo
  echo "Image nodes:"
  jq -r '
    [ .. | objects | select(.__typename? == "Image")
      | "\(.key)  \(.width)x\(.height)  " + ((.url // "")[0:80])
    ] | unique | .[] ' /tmp/nf_graphql_kodi.json 2>/dev/null | head -20 \
    || echo "  (no Image nodes in the response body)"
  echo
  echo "Top-level keys:"
  jq -r '.data | keys | join(", ")' /tmp/nf_graphql_kodi.json 2>/dev/null || echo "  (no data)"
  echo
  echo "What counts now is not existence but completeness:"
  echo "  1. Do StoryArt and LOGO_BRANDED_HORIZONTAL appear?"
  echo "  2. Do the dimensions (848x477 / 625x250) match the capture?"
  echo "  3. Is the response structurally the same, not just status 200?"
else
  echo
  echo ">>> REJECTED (HTTP $STATUS)."
  case "$STATUS" in
    401|403) echo "    Session or client fingerprint is being checked." ;;
    400)     echo "    Body or persisted query rejected — check the instrumentation." ;;
    429)     echo "    Rate limit." ;;
    5??)     echo "    Service side." ;;
  esac
  echo
  echo "Counter-check with the browser User-Agent, to separate client type from header:"
  echo "  apply sed 's|Kodi/20.0|Mozilla/5.0|' to the curl command."
  echo "If the browser UA returns 200 and Kodi/20.0 does not, the User-Agent is the deciding factor."
fi

rm -f /tmp/nf_graphql_kodi.json
echo
echo "Note: response bodies were deleted after evaluation."
