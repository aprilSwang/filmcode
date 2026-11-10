/* Privacy-conscious Filmcode telemetry: Cloudflare only; no identifiers. */
(() => {
  const config = window.FILMCODE_ANALYTICS || {};
  if (config.webAnalyticsToken && /^[a-f0-9]{32}$/i.test(config.webAnalyticsToken)) {
    const script = document.createElement('script');
    script.defer = true;
    script.src = 'https://static.cloudflareinsights.com/beacon.min.js';
    script.setAttribute('data-cf-beacon', JSON.stringify({ token: config.webAnalyticsToken }));
    document.head.appendChild(script);
  }

  const endpoint = config.eventsEndpoint;
  if (!endpoint || !/^https:\/\/events\.playfilmcode\.com\/event$/.test(endpoint)) return;
  const allowed = new Set(['challenge_started', 'guess_submitted', 'challenge_completed', 'result_shared', 'challenge_returned']);
  window.filmcodeTrack = (name, data = {}) => {
    if (!allowed.has(name)) return;
    const clean = { event: name };
    if (typeof data.puzzle === 'string' && /^[a-z0-9-]{1,60}$/.test(data.puzzle)) clean.puzzle = data.puzzle;
    if (['daily', 'preview', 'pilot'].includes(data.mode)) clean.mode = data.mode;
    if (Number.isInteger(data.choice) && data.choice >= 0 && data.choice <= 3) clean.choice = data.choice;
    if (typeof data.correct === 'boolean') clean.correct = data.correct;
    try {
      fetch(endpoint, { method: 'POST', mode: 'cors', credentials: 'omit', keepalive: true,
        headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(clean) }).catch(() => {});
    } catch {}
  };
})();