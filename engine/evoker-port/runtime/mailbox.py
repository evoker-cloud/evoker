# SPDX-License-Identifier: AGPL-3.0-only
"""Fixed loopback client invoked through the provider's authenticated exec API."""
import json
import sys
import urllib.request

if len(sys.argv) != 2 or sys.argv[1] not in ('configure', 'activate', 'poll', 'reply'):
    raise SystemExit(2)
body = sys.stdin.buffer.read(700_001)
if len(body) > 700_000:
    raise SystemExit(2)
json.loads(body)
request = urllib.request.Request('http://127.0.0.1:8798/control/'+sys.argv[1], data=body,
                                 headers={'Content-Type': 'application/json'})
opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
with opener.open(request, timeout=4) as response:
    output = response.read(700_001)
    if len(output) > 700_000:
        raise SystemExit(2)
    sys.stdout.buffer.write(output)
