"""Tiny stand-ins for requests, so client tests never touch the network."""

import io
import zipfile


class FakeResp:
    def __init__(self, status=200, content=b"", payload=None, headers=None):
        self.status_code, self.content, self._payload = status, content, payload
        self.text = content.decode("latin1") if isinstance(content, bytes) else str(content)
        self.closed = False
        self.headers = headers or {}

    def json(self):
        return self._payload

    def iter_content(self, n):
        yield self.content

    def close(self):
        self.closed = True


class FakeSession:
    """Returns queued responses in order (the last one repeats); records every call."""

    def __init__(self, *responses, raises=None):
        self.responses, self.raises = list(responses), raises
        self.headers, self.auth, self.calls = {}, None, []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        if self.raises:
            raise self.raises
        r = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(r, Exception):
            raise r
        return r


def zip_bytes(members):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        for name, data in members.items():
            z.writestr(name, data)
    return buf.getvalue()


class RoutedSession:
    """Routes by (method, url suffix). Each route is a list of responses consumed in order (last repeats)."""

    def __init__(self, routes):
        self.routes = {k: list(v) for k, v in routes.items()}
        self.headers, self.auth, self.calls = {}, None, []

    def request(self, method, url, **kw):
        self.calls.append((method, url, kw))
        for (m, suffix), queue in self.routes.items():
            if m == method and url.endswith(suffix):
                return queue.pop(0) if len(queue) > 1 else queue[0]
        raise AssertionError(f"unrouted {method} {url}")
