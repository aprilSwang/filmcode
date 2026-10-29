// Public research shortlist: these movies are not in MKIA's playable source catalog.
const section = document.createElement('section');
section.className = 'panel research-panel';
section.innerHTML = '<h2>Recognizable-film research shortlist · Not yet playable</h2><div class="research-intro">Strong color-barcode candidates. Every title still needs an authorized video source before MKIA can generate a puzzle.</div><div class="research-controls"><input id="research-filter" placeholder="Search movie titles or palettes" aria-label="Search research shortlist"/><select id="research-order" aria-label="Sort research shortlist"><option value="priority">Highest priority</option><option value="year">Newest first</option><option value="title">Title A–Z</option></select></div><div id="research-grid" class="research-grid">Loading…</div>';
document.querySelector('main footer').before(section);
const researchGrid = section.querySelector('#research-grid');
let researchFilms = [];
function renderResearch() {
  const query = section.querySelector('#research-filter').value.trim().toLowerCase();
  const order = section.querySelector('#research-order').value;
  const list = researchFilms.filter(f => (f.title+' '+f.palette+' '+f.year).toLowerCase().includes(query));
  list.sort((a,b) => order==='year' ? b.year-a.year : order==='title' ? a.title.localeCompare(b.title) : b.priority-a.priority || a.title.localeCompare(b.title));
  researchGrid.replaceChildren();
  for (const film of list) {
    const card=document.createElement('article');card.className='research-card';
    const title=document.createElement('strong');title.textContent=film.title+' ('+film.year+')';
    const priority=document.createElement('span');priority.className='pill';priority.textContent='Priority '+film.priority+'/10';
    const palette=document.createElement('p');palette.textContent=film.palette;
    const note=document.createElement('small');note.textContent='Footage: not supplied · Research only';
    card.append(title,priority,palette,note);researchGrid.append(card);
  }
  if (!list.length) researchGrid.textContent='No matching movies.';
}
section.querySelector('#research-filter').addEventListener('input',renderResearch);
section.querySelector('#research-order').addEventListener('change',renderResearch);
fetch('./data.json',{cache:'no-store'}).then(r=>r.json()).then(data=>{researchFilms=data.research||[];renderResearch()}).catch(()=>researchGrid.textContent='Research list unavailable. Check the latest MKIA deployment.');
