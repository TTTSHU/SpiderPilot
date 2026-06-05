"""Runtime hook script generation for signature tracing MVP."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from spiderpilot.spec import load_spec

HOOK_SCRIPT = r'''
(() => {
  if (window.__SPIDERPILOT_SIGNATURE_HOOKED__) return;
  window.__SPIDERPILOT_SIGNATURE_HOOKED__ = true;
  const nativeDateNow = Date.now.bind(Date);
  const emit = (type, payload) => {
    try { console.log('[SPIDERPILOT_SIGNATURE]', JSON.stringify({type, payload, ts: nativeDateNow(), stack: (new Error()).stack})); } catch (e) {}
  };
  const interesting = /sign|signature|token|bogus|a_bogus|w_rid|anti|nonce|timestamp|x-kpsdk/i;

  const oldFetch = window.fetch;
  if (oldFetch) {
    window.fetch = function(input, init) {
      emit('fetch', {input: String(input), init: init || null});
      return oldFetch.apply(this, arguments);
    };
  }

  const oldOpen = XMLHttpRequest.prototype.open;
  XMLHttpRequest.prototype.open = function(method, url) {
    this.__spiderpilot_method = method;
    this.__spiderpilot_url = url;
    emit('xhr_open', {method, url: String(url)});
    return oldOpen.apply(this, arguments);
  };

  const oldSend = XMLHttpRequest.prototype.send;
  XMLHttpRequest.prototype.send = function(body) {
    emit('xhr_send', {method: this.__spiderpilot_method, url: String(this.__spiderpilot_url), body: body ? String(body).slice(0, 500) : null});
    return oldSend.apply(this, arguments);
  };

  const oldURLSet = URLSearchParams.prototype.set;
  URLSearchParams.prototype.set = function(k, v) {
    if (interesting.test(String(k))) emit('url_param_set', {key: String(k), value: String(v)});
    return oldURLSet.apply(this, arguments);
  };

  if (window.Headers && Headers.prototype.set) {
    const oldHeaderSet = Headers.prototype.set;
    Headers.prototype.set = function(k, v) {
      if (interesting.test(String(k))) emit('header_set', {key: String(k), value: String(v)});
      return oldHeaderSet.apply(this, arguments);
    };
  }

  Date.now = function() {
    const v = nativeDateNow();
    emit('date_now', {value: v});
    return v;
  };
})();
'''


def write_hook_script(spec_path: Path, workspace: Path = Path("workspace")) -> dict[str, Any]:
    spec = load_spec(spec_path)
    out_dir = workspace / "signatures" / spec.name
    out_dir.mkdir(parents=True, exist_ok=True)
    script_path = out_dir / "runtime_hook.js"
    script_path.write_text(HOOK_SCRIPT, encoding="utf-8")
    report = {"version": 1, "task": spec.name, "script_path": str(script_path), "hooks": ["fetch", "xhr", "urlsearchparams.set", "headers.set", "date.now"]}
    (out_dir / "runtime_hook.yaml").write_text(yaml.safe_dump(report, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return report
