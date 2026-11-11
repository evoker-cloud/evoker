# SPDX-License-Identifier: AGPL-3.0-only
"""Per-assessment supervisor. Runs inside a network-blocked gVisor sandbox.

The loopback mailbox carries untrusted harness requests over the runtime's exec
channel. The trusted Evoker controller validates and meters every operation.
No provider, customer, Cloudflare or application-database credential enters it.
"""
import json
import ctypes
import os
import pathlib
import resource
import signal
import subprocess
import threading
import time
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

ROOT = pathlib.Path('/work')
MAX_REQUEST = 450_000
MAX_EVENTS = 5000
MAX_SCRATCH = 256 * 1024 * 1024
lock = threading.RLock()
configured = False
deadline = time.time() + 30
state = 'starting'
events = []
pending = {}
child = None
database = None
activated = False
shutdown = threading.Event()


def record(value):
    global state
    with lock:
        if len(events) >= MAX_EVENTS:
            raise ValueError('event_limit')
        if value.get('state') in ('ready', 'running', 'completed', 'failed'):
            state = value['state']
        # Keep only the reviewed headless event shape. Never emit stderr,
        # transcripts, raw activity details, or model reasoning.
        entry = {k: value[k] for k in ('kind', 'role', 'summary', 'phase', 'finding') if k in value}
        if len(json.dumps(entry).encode()) > 40_000:
            raise ValueError('event_size')
        events.append({'cursor': len(events) + 1, **entry})


def configure(plan):
    global configured, deadline
    if not isinstance(plan, dict) or set(plan) != {'objective', 'context', 'hosts', 'deadline'}:
        raise ValueError('invalid_plan')
    if not isinstance(plan['objective'], str) or not 1 <= len(plan['objective']) <= 8000:
        raise ValueError('invalid_plan')
    if not isinstance(plan['context'], list) or len(plan['context']) > 20 or any(not isinstance(x, str) or len(x) > 4000 for x in plan['context']):
        raise ValueError('invalid_plan')
    if not isinstance(plan['hosts'], list) or not 1 <= len(plan['hosts']) <= 3 or any(not isinstance(x, str) or len(x) > 253 for x in plan['hosts']):
        raise ValueError('invalid_plan')
    if type(plan['deadline']) is not int or not time.time() < plan['deadline'] / 1000 <= time.time() + 900:
        raise ValueError('invalid_deadline')
    with lock:
        if configured:
            # Never replace an active run's objective, scope or deadline.
            if json.loads((ROOT / 'plan.json').read_text()) != plan:
                raise ValueError('plan_conflict')
            return
        ROOT.mkdir(mode=0o700, exist_ok=True)
        (ROOT / 'plan.json').write_text(json.dumps(plan))
        deadline = plan['deadline'] / 1000
        configured = True
    threading.Thread(target=start_harness, daemon=True).start()


def start_harness():
    global child, database, state
    try:
        pg_bin = pathlib.Path('/usr/lib/postgresql/17/bin')
        pg_dir = ROOT / 'pg'
        subprocess.run([str(pg_bin / 'initdb'), '-D', str(pg_dir), '-U', 'artex', '--auth=trust', '--no-locale'],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=25)
        # Unix socket only, private to this ephemeral sandbox. There is no
        # connection to Evoker's database and no network PostgreSQL listener.
        database = subprocess.Popen([str(pg_bin / 'postgres'), '-D', str(pg_dir), '-k', str(ROOT), '-h', '',
                                     '-c', 'max_connections=8', '-c', 'shared_buffers=32MB', '-c', 'max_wal_size=64MB'],
                                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, start_new_session=True)
        for _ in range(100):
            if subprocess.run([str(pg_bin / 'pg_isready'), '-h', str(ROOT), '-U', 'artex'],
                              stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0:
                break
            if shutdown.wait(.1):
                return
        else:
            raise RuntimeError('database_start_failed')
        env = {'PATH': '/usr/bin:/bin', 'HOME': str(ROOT), 'TMPDIR': str(ROOT), 'ARTEX_LANG': 'en',
               'EVOKER_HOSTED': 'true', 'EVOKER_MODEL_BASE_URL': 'http://127.0.0.1:8798/v1',
               'EVOKER_RUN_CREDENTIAL': 'evrun_loopback_mailbox', 'GOMAXPROCS': '1', 'GOMEMLIMIT': '512MiB',
               'ARTEX_PG_DSN': 'postgresql://artex@localhost/postgres?host=/work&sslmode=disable'}
        child = subprocess.Popen(['/opt/evoker/evoker-artex', str(ROOT / 'plan.json'), str(ROOT / 'data')],
                                 env=env, cwd=ROOT, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                 stderr=subprocess.DEVNULL, start_new_session=True)
        while not shutdown.is_set():
            line = child.stdout.readline(40_001)
            if not line:
                break
            if len(line) > 40_000 or not line.endswith(b'\n'):
                raise ValueError('event_size')
            record(json.loads(line))
        code = child.wait(timeout=5)
        with lock:
            if state != 'completed' or code:
                state = 'failed'
    except Exception:
        with lock:
            state = 'failed'
        terminate_children()


def terminate_children():
    for process in (child, database):
        if process and process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
                process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.0'

    def log_message(self, *args):
        pass

    def send_json(self, status, value):
        body = json.dumps(value).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        global activated
        try:
            self.connection.settimeout(5)
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= MAX_REQUEST:
                raise ValueError('request_size')
            value = json.loads(self.rfile.read(length))
            if self.path == '/control/configure':
                configure(value)
                return self.send_json(200, {'ok': True})
            if self.path == '/control/activate':
                with lock:
                    if not activated:
                        if state != 'ready' or child is None:
                            raise ValueError('not_ready')
                        child.stdin.write(b'activate\n')
                        child.stdin.flush()
                        activated = True
                return self.send_json(200, {'ok': True})
            if self.path == '/control/poll':
                after = value.get('after', 0)
                with lock:
                    if type(after) is not int or not 0 <= after <= len(events):
                        raise ValueError('invalid_cursor')
                    batch, size = [], 0
                    for event in events[after:after+50]:
                        size += len(json.dumps(event).encode())
                        if size > 220_000:
                            break
                        batch.append(event)
                    cursor = batch[-1]['cursor'] if batch else after
                    # Do not announce completion before all findings/events have
                    # been drained by the durable controller.
                    public_state = state if cursor == len(events) else 'running'
                    request = next((r['request'] for r in pending.values() if not r['ready'].is_set()), None) if state == 'running' else None
                    result = {'state': public_state, 'cursor': cursor, 'records': batch, 'request': request}
                return self.send_json(200, result)
            if self.path == '/control/reply':
                if set(value) != {'id', 'status', 'body'} or type(value['status']) is not int or not 200 <= value['status'] <= 599:
                    raise ValueError('invalid_reply')
                with lock:
                    item = pending.get(value['id'])
                    if item and not item['ready'].is_set():
                        item['response'] = value
                        item['ready'].set()
                return self.send_json(200, {'ok': True})
            if self.path not in ('/v1/chat/completions', '/v1/security/inspect'):
                return self.send_json(404, {'error': {'message': 'Not found'}})
            if not activated or state != 'running' or time.time() >= deadline:
                return self.send_json(409, {'error': {'message': 'Assessment inactive'}})
            key = str(uuid.uuid4())
            request = {'id': key, 'path': self.path, 'role': self.headers.get('X-Evoker-Agent-Role', 'worker'), 'body': value}
            item = {'request': request, 'ready': threading.Event()}
            with lock:
                if len(pending) >= 4:
                    return self.send_json(429, {'error': {'message': 'Assessment busy'}})
                pending[key] = item
            try:
                while not item['ready'].wait(.25):
                    if shutdown.is_set() or time.time() >= deadline:
                        return self.send_json(503, {'error': {'message': 'Assessment stopped'}})
                response = item['response']
                # The controller returns an OpenAI completion. Convert its
                # already-validated result to the stream expected by Norma.
                if self.path == '/v1/chat/completions' and value.get('stream') and response['status'] == 200:
                    result = response['body']
                    choice = result['choices'][0]
                    delta = dict(choice['message'])
                    if delta.get('tool_calls'):
                        delta['tool_calls'] = [dict(x, index=i) for i, x in enumerate(delta['tool_calls'])]
                    common = {k: result[k] for k in ('id', 'created', 'model')}
                    common['object'] = 'chat.completion.chunk'
                    chunks = [dict(common, choices=[{'index': 0, 'delta': delta, 'finish_reason': None}]),
                              dict(common, choices=[{'index': 0, 'delta': {}, 'finish_reason': choice['finish_reason']}]),
                              dict(common, choices=[], usage=result['usage'])]
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/event-stream')
                    self.end_headers()
                    for chunk in chunks:
                        self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
                    self.wfile.write(b'data: [DONE]\n\n')
                    return
                return self.send_json(response['status'], response['body'])
            finally:
                with lock:
                    pending.pop(key, None)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self.send_json(400, {'error': {'message': 'Invalid runtime request'}})


def watch():
    while not shutdown.wait(1):
        try:
            usage = sum(p.stat().st_size for p in ROOT.rglob('*') if p.is_file() and not p.is_symlink())
            if time.time() >= deadline or usage > MAX_SCRATCH:
                break
        except OSError:
            break
    shutdown.set()
    terminate_children()
    os._exit(0)


def main():
    os.umask(0o077)
    # Required with either provider, including when Kubernetes starts UID 1000.
    if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
        raise RuntimeError('cannot_disable_privilege_gain')
    # Modal ignores Docker USER instructions. Drop all real/effective/saved
    # credentials before parsing the plan, starting PostgreSQL or ARTEX.
    if os.geteuid() == 0:
        for directory in ('/tmp', '/var/tmp', '/home/evoker'):
            if pathlib.Path(directory).exists():
                os.chmod(directory, 0o555)
        os.setgroups([])
        if ctypes.CDLL(None, use_errno=True).prctl(38, 1, 0, 0, 0) != 0:
            raise RuntimeError('cannot_disable_privilege_gain')
        os.setresgid(1000, 1000, 1000)
        os.setresuid(1000, 1000, 1000)
    if os.getresuid() != (1000, 1000, 1000) or os.getresgid() != (1000, 1000, 1000):
        raise RuntimeError('unprivileged_runtime_required')
    resource.setrlimit(resource.RLIMIT_NOFILE, (256, 256))
    resource.setrlimit(resource.RLIMIT_NPROC, (128, 128))
    resource.setrlimit(resource.RLIMIT_FSIZE, (64 * 1024 * 1024, 64 * 1024 * 1024))
    ROOT.mkdir(mode=0o700, exist_ok=True)
    for sig in (signal.SIGTERM, signal.SIGINT):
        signal.signal(sig, lambda *_: shutdown.set())
    initial_plan = os.environ.pop('EVOKER_HOSTED_PLAN', None)
    if initial_plan:
        configure(json.loads(initial_plan))
    threading.Thread(target=watch, daemon=True).start()
    ThreadingHTTPServer(('127.0.0.1', 8798), Handler).serve_forever()


if __name__ == '__main__':
    main()
