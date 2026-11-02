/* Filmcode event telemetry. Set websiteId in analytics-config.js to enable Umami.
   Anonymous aggregate events only: no IP, email, title or raw answer. */
(() => {
  const id = window.FILMCODE_ANALYTICS?.websiteId;
  if (!id || !/^[0-9a-f-]{32,36}$/i.test(id)) return;
  const pending = [];
  let ready = false;
  window.filmcodeTrack = (name, data = {}) => {
    if (!['challenge_started','guess_submitted','challenge_completed','result_shared','challenge_returned'].includes(name)) return;
    const clean = {};
    for (const key of ['puzzle','correct','choice','mode']) {
      if (Object.prototype.hasOwnProperty.call(data, key)) clean[key] = String(data[key]).slice(0, 60);
    }
    if (ready && window.umami?.track) window.umami.track(name, clean);
    else if (pending.length < 30) pending.push([name, clean]);
  };
  const tag = document.createElement('script');
  tag.async = true;
  tag.src = 'https://cloud.umami.is/script.js';
  tag.dataset.websiteId = id;
  tag.onload = () => {
    ready = true;
    while (pending.length && window.umami?.track) {
      const [name, data] = pending.shift();
      window.umami.track(name, data);
    }
  };
  document.head.appendChild(tag);
})();