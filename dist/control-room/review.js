// Public, read-only review of MKIA's saved 15-shot shortlist.
const reviewObserver = new MutationObserver(() => {
  const detail = document.getElementById('detail');
  const movie = dataset.scheduled.find(entry => entry.id === active);
  if (!movie || !detail.querySelector('.actions') || detail.querySelector('#shot-review')) return;
  const section = document.createElement('section');
  section.id = 'shot-review';
  section.innerHTML = '<div class="sectionlabel">MKIA shot shortlist · 15 candidate frames</div><p id="shot-status">Loading shot review…</p><div id="shot-grid" class="shot-grid"></div>';
  const plot = document.createElement('p');
  plot.textContent = movie.plot_summary
    ? 'Plot context: ' + movie.plot_summary
    : 'Plot context not supplied yet; this movie currently uses visual-only ranking.';
  section.prepend(plot);
  detail.appendChild(section);
  fetch('./reviews/' + encodeURIComponent(movie.id) + '.json', {cache: 'no-store'})
    .then(response => {if (!response.ok) throw Error('No saved shortlist'); return response.json();})
    .then(data => {
      if (active !== movie.id || !section.isConnected) return;
      section.querySelector('#shot-status').textContent = data.selection_mode === 'vision+plot'
        ? 'Plot-aware AI scoring was used. Green frames were selected.'
        : 'Visual-quality and diversity scoring was used. Green frames were selected.';
      const grid = section.querySelector('#shot-grid');
      (data.candidates || []).forEach((candidate, index) => {
        const card = document.createElement('article');
        card.className = 'shot-card' + (candidate.selected ? ' chosen' : '');
        const img = document.createElement('img');
        img.loading = 'lazy'; img.alt = 'Candidate frame ' + (index + 1);
        img.src = '../' + candidate.image;
        const label = document.createElement('strong');
        label.textContent = '#' + (index + 1) + (candidate.selected ? ' · SELECTED' : ' · ALTERNATE');
        const caption = document.createElement('small');
        caption.textContent = candidate.time_seconds + 's · quality ' + candidate.quality
          + (candidate.plot_relevance == null ? '' : ' · plot ' + candidate.plot_relevance + '/10')
          + (candidate.spoiler_risk == null ? '' : ' · spoiler ' + candidate.spoiler_risk + '/10');
        const reason = document.createElement('p'); reason.textContent = candidate.reason;
        card.append(img, label, caption, reason); grid.appendChild(card);
      });
    })
    .catch(() => {
      if (active === movie.id && section.isConnected) {
        section.querySelector('#shot-status').textContent = 'No shortlist saved for this older puzzle. Use Regenerate to create 15 candidates with the improved selector.';
      }
    });
});
reviewObserver.observe(document.getElementById('detail'), {childList: true});
