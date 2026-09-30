// Saturday in Austin ✦ runs the Python planner in this repo in the visitor's browser with Pyodide.
// Every control replans right away with the same Saturday number; "another Saturday" draws a new one.
(() => {
    const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
    const BASE = 'saturday/';  // served straight from this repo by GitHub Pages
    const FILES = ['__init__.py', '__main__.py', 'city.py', 'planner.py', 'rules.py', 'spots.py', 'sass.py', 'web.py',
                   'data/spots.csv', 'data/shelf.json', 'data/places.json'];

    const form = document.getElementById('prefs');
    const day = document.querySelector('.day');
    const sassBox = day.querySelector('.sass');
    const list = day.querySelector('.timeline');
    const status = day.querySelector('.status');
    const stats = day.querySelector('.stats');
    const again = day.querySelector('.again');
    const number = day.querySelector('.number');

    let seed = 1000 + Math.floor(Math.random() * 9000);
    let lastPlan = null;   // the day on screen, for the letter
    let autoRain = false;  // true when live weather turned on Rainy day
    const PLACES = [];  // every spot, filled in once Python has loaded

    const el = (tag, cls, text) => {
        const e = document.createElement(tag);
        if (cls) e.className = cls;
        if (text != null) e.textContent = text;
        return e;
    };
    const loadScript = src => new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src; s.onload = resolve; s.onerror = reject;
        document.head.appendChild(s);
    });

    let python = null;
    function boot() {
        if (python) return python;
        python = (async () => {
            await loadScript(PYODIDE + 'pyodide.js');
            const py = await loadPyodide({ indexURL: PYODIDE });
            py.FS.mkdirTree('/home/pyodide/saturday/data');
            await Promise.all(FILES.map(async f => {
                const r = await fetch(BASE + f, { cache: 'no-cache' });  // never mix old and new files after an update
                if (!r.ok) throw new Error(`couldn't load ${f}`);
                py.FS.writeFile('/home/pyodide/saturday/' + f, await r.text());
            }));
            py.runPython('import sys; sys.path.insert(0, "/home/pyodide")\nfrom saturday.web import plan_json, names, stats');
            PLACES.push(...JSON.parse(py.globals.get('names')()));
            // this planner's numbers, counted from the data (so they grow with the list)
            for (const [key, value] of Object.entries(JSON.parse(py.globals.get('stats')()))) {
                document.querySelectorAll(`[data-app="${key}"]`).forEach(e => { e.textContent = value; });
            }
            return py.globals.get('plan_json');
        })();
        python.catch(() => { python = null; });  // let the next change try again
        return python;
    }

    const duration = m => {
        const h = Math.floor(m / 60), r = m % 60;
        return h ? (r ? `${h}h ${r}m` : `${h}h`) : `${r} min`;
    };

    function draw(plan) {
        sassBox.replaceChildren(...plan.sass.map(n => el('p', null, n)));
        sassBox.hidden = !plan.sass.length;
        list.replaceChildren();
        if (!plan.stops.length) {
            form.querySelector('.verdict').hidden = true;
            status.textContent = 'Nothing fits. Try a longer day, a later “home by,” or a different mood.';
            status.hidden = false;
            stats.hidden = true;
            number.textContent = '';
            return;
        }
        status.hidden = true;
        const hop = (via, minutes, fare) => via === 'uber' ? `Uber · ${minutes} min · ≈ $${fare}`
            : `${minutes} min ${via === 'bus' ? 'bus' : via === 'walk' ? 'walk' : 'drive'}`;
        plan.stops.forEach((s, i) => {
            if (s.type !== 'free' && s.travel && i) list.appendChild(el('li', 'travel', hop(s.via, s.travel, s.fare)));
            if (s.type === 'free') {
                list.appendChild(el('li', 'free', `free time · ${duration(s.free)} to wander`));
                return;
            }
            const li = el('li', s.type);
            li.appendChild(el('span', 't', s.time));
            if (s.type === 'reset') {
                li.appendChild(el('p', 'name', 'HOME'));
                li.appendChild(el('p', 'meta', `${s.note} · ${s.minutes} min`));
            } else {
                const where = s.where === 'home' ? 'at home' : s.where;
                li.appendChild(el('p', 'name', s.name));
                li.appendChild(el('p', 'meta', `${s.note || where} · ${duration(s.minutes)}`));
                li.appendChild(el('p', 'tag', s.note ? `${s.label} · ${where}` : s.label));
            }
            if (s.why) li.appendChild(el('p', 'why', s.why));
            list.appendChild(li);
        });
        if (plan.back) list.appendChild(el('li', 'travel', `${hop(plan.back_via, plan.back, plan.back_fare)} home`));
        const home = el('li', 'home');
        home.appendChild(el('span', 't', plan.home));
        home.appendChild(el('p', 'meta', plan.sign_off));
        list.appendChild(home);

        const st = plan.stats;
        const figure = (value, label) => {
            const d = el('div');
            d.appendChild(el('b', null, value));
            d.appendChild(el('span', null, label));
            return d;
        };
        stats.replaceChildren(
            figure(st.stops, st.stops === 1 ? 'stop' : 'stops'),
            figure(st.hours_out, 'hours out'),
            figure(st.travel, { walk: 'min walking', transit: 'min bus + walk', uber: 'min in Ubers' }[plan.mode] || 'min driving'),
            figure(`$${st.spend}`, st.fares ? `about, $${st.fares} Uber` : 'about, all in'),
        );
        stats.hidden = false;
        number.textContent = `xoxo, Saturday #${plan.seed}`;
        verdict(plan);
        lastPlan = plan;
        document.querySelectorAll('.seal-it, .save-it').forEach(b => { b.disabled = false; });
        if (autoRain && form.elements.rainy.checked) {
            sassBox.prepend(el('p', null, 'Rain in the Saturday forecast, so I turned on Rainy day.'));
            sassBox.hidden = false;
        }
    }

    // bottom left: the day's best line, and the day as one bar
    const verdictBox = form.querySelector('.verdict');
    const minutes = label => {
        const [t, ampm] = label.split(' ');
        const [h, m] = t.split(':').map(Number);
        return (h % 12 + (ampm === 'PM' ? 12 : 0)) * 60 + m;
    };
    const FOOD = new Set(['coffee', 'smoothie', 'tea', 'brunch', 'lunch', 'dinner', 'treat', 'late night', 'order in', 'snack']);
    // on a short screen the verdict steps aside so nothing spills past the page
    function fitVerdict() {
        verdictBox.classList.remove('squeezed');
        if (innerWidth > 1000 && form.scrollHeight > form.clientHeight + 1) verdictBox.classList.add('squeezed');
    }
    new ResizeObserver(() => { if (!verdictBox.hidden) fitVerdict(); }).observe(form);
    function verdict(plan) {
        const why = plan.stops.map(s => s.why).filter(Boolean);
        verdictBox.querySelector('blockquote').textContent = why[0] || plan.sass[0] || plan.sign_off;
        const bar = verdictBox.querySelector('.glance');
        const start = minutes(plan.leave);
        let end = minutes(plan.home);
        if (end < start) end += 24 * 60;
        bar.replaceChildren(...plan.stops.filter(s => s.type !== 'free').map(s => {
            let at = minutes(s.time);
            if (at < start) at += 24 * 60;
            const i = document.createElement('i');
            i.className = s.type === 'reset' ? 'home' : FOOD.has(s.category) ? 'food' : '';
            i.style.left = `${(at - start) / (end - start) * 100}%`;
            i.style.width = `${s.minutes / (end - start) * 100}%`;
            i.title = s.name;
            return i;
        }));
        const [a, b] = verdictBox.querySelectorAll('.glance-times span');
        a.textContent = `Out ${plan.leave}`;
        b.textContent = `Home ${plan.home}`;
        verdictBox.hidden = false;
        fitVerdict();
    }

    let hotSaturday = false;  // set from the forecast: 90° and up means a swim
    let pending = 0;
    async function run() {
        const ticket = ++pending;
        day.classList.add('thinking');
        try {
            const plan = await boot();
            // let the "thinking" style paint before Python takes the main thread
            await new Promise(r => setTimeout(r, 30));  // (a timer, not an animation frame: those pause in background tabs)
            if (ticket !== pending) return;  // a newer change is already on its way
            const f = form.elements;
            const result = plan(f.start.value, f.end.value, f.hours.value, f.mood.value, String(seed),
                                false, f.rainy.checked, f.area.value, f.include.value, f.exclude.value,
                                f.travel.value, f.budget.value, f.start_from.value, hotSaturday);
            draw(JSON.parse(result));
            again.disabled = false;
        } catch (err) {
            status.textContent = 'Python took a nap. Check your connection and refresh ✦';
            status.hidden = false;
        } finally {
            if (ticket === pending) day.classList.remove('thinking');
        }
    }

    let timer;
    const soon = () => { clearTimeout(timer); timer = setTimeout(run, 250); };
    form.addEventListener('input', soon);
    form.addEventListener('change', soon);
    form.addEventListener('submit', e => { e.preventDefault(); run(); });
    again.addEventListener('click', () => { seed = 1000 + Math.floor(Math.random() * 9000); run(); });

    // magazine sections: Plan, The Editor, The Method (one screen each)
    const sections = [...document.querySelectorAll('.sections button')];
    const show = name => {
        sections.forEach(b => b.setAttribute('aria-selected', b.dataset.screen === name));
        document.querySelectorAll('.screen').forEach(sc => { sc.hidden = sc.id !== 'screen-' + name; });
        if (name === 'method') setTimeout(() => document.getElementById('screen-method').dispatchEvent(new Event('refit')), 0);
    };
    sections.forEach(b => b.addEventListener('click', () => { show(b.dataset.screen); menu(false); }));
    // on a phone the nav is three lines
    const head = document.querySelector('header'), burger = document.querySelector('.burger');
    const menu = open => { head.classList.toggle('open', open); burger.setAttribute('aria-expanded', open); };
    burger.addEventListener('click', () => menu(!head.classList.contains('open')));
    document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => show(b.dataset.go)));

    // our own dropdowns (the browser's datalist popups don't match the page)
    const NOTS = { Workouts: 'workouts', Museums: 'museums', Shopping: 'shopping', 'Anything outdoors': 'outdoors',
                   'Live music': 'live-music', 'Bars and nightlife': 'nightlife', Studying: 'studying', Sweets: 'sweets' };
    const SOURCES = {
        starts: () => ['UT / West Campus', 'Downtown', 'East Austin', 'South Congress / South First', 'Clarksville / West Austin',
                       'The Domain / Rock Rose', 'Zilker / Barton Springs', 'South Lamar', 'Hyde Park / North Loop', 'Burnet Road', 'Mueller'].map(v => [v, '']),
        areas: () => ['Anywhere', 'UT / West Campus', 'Downtown', 'East Austin', 'South Congress / South First', 'Clarksville / West Austin',
                       'The Domain / Rock Rose', 'Zilker / Barton Springs', 'South Lamar', 'Hyde Park / North Loop', 'Burnet Road', 'Mueller'].map(v => [v, '']),
        places: () => PLACES.map(v => [v, '']),
        nots: () => [...Object.keys(NOTS).map(v => [v, 'kind']), ...PLACES.map(v => [v, ''])],
    };
    form.querySelectorAll('[data-combo]').forEach((input, n) => {
        const list = Object.assign(document.createElement('ul'), { id: `combo-${n}`, hidden: true });
        list.setAttribute('role', 'listbox');
        input.after(list);
        input.setAttribute('role', 'combobox');
        input.setAttribute('aria-expanded', 'false');
        input.setAttribute('aria-controls', list.id);
        let items = [], at = -1;
        const close = () => { list.hidden = true; input.setAttribute('aria-expanded', 'false'); at = -1; };
        const choose = value => { input.value = value; close(); input.dispatchEvent(new Event('input', { bubbles: true })); };
        const mark = () => [...list.children].forEach((li, i) => {
            li.classList.toggle('on', i === at);
            if (i === at) { li.scrollIntoView({ block: 'nearest' }); input.setAttribute('aria-activedescendant', li.id); }
        });
        function open() {
            const q = input.value.trim().toLowerCase();
            const all = SOURCES[input.dataset.combo]();
            const exact = all.some(([v]) => v.toLowerCase() === q);
            items = all.filter(([v]) => !q || exact || v.toLowerCase().includes(q)).slice(0, 40);
            list.replaceChildren(...(items.length ? items.map(([v, tag], i) => {
                const li = Object.assign(document.createElement('li'), { id: `${list.id}-${i}` });
                li.setAttribute('role', 'option');
                li.append(v);
                if (tag) li.appendChild(Object.assign(document.createElement('small'), { textContent: tag }));
                li.addEventListener('mousedown', e => { e.preventDefault(); choose(v); });
                return li;
            }) : [Object.assign(document.createElement('li'), { className: 'empty', textContent: PLACES.length ? 'Nothing by that name. Yet.' : 'Still loading the places…' })]));
            at = -1;
            list.hidden = false;
            input.setAttribute('aria-expanded', 'true');
        }
        input.addEventListener('focus', open);
        input.addEventListener('click', open);
        input.addEventListener('input', e => { if (e.isTrusted) open(); });
        input.addEventListener('blur', close);
        input.addEventListener('keydown', e => {
            if (e.key === 'ArrowDown' || e.key === 'ArrowUp') {
                if (list.hidden) open();
                at = Math.max(0, Math.min(items.length - 1, at + (e.key === 'ArrowDown' ? 1 : -1)));
                mark(); e.preventDefault();
            } else if (e.key === 'Enter') {
                if (!list.hidden && at >= 0 && items[at]) choose(items[at][0]);
                e.preventDefault();
            } else if (e.key === 'Escape') close();
        });
    });

    // "absolutely not": the friendly names become what the planner understands
    const excludeText = document.getElementById('exclude-text');
    excludeText.addEventListener('input', () => {
        const v = excludeText.value.trim();
        form.elements.exclude.value = NOTS[v] || v;
    });

    // "where": type a neighborhood (or pick one); nicknames welcome
    const AREAS = {
        anywhere: ['anywhere', 'anywhere in austin', 'all of austin', 'austin', ''],
        ut: ['ut / west campus', 'ut', 'ut austin', 'campus', 'west campus', 'the drag', 'drag', 'university'],
        downtown: ['downtown', 'dt', 'rainey', 'rainey street', '2nd street', 'second street', 'warehouse district', 'congress ave'],
        east: ['east austin', 'east', 'east side', 'eastside', 'east 6th', 'e 6th', 'holly', 'cherrywood'],
        soco: ['south congress / south first', 'south congress', 'soco', 'bouldin', 'bouldin creek', 'travis heights', 'south 1st', 's 1st', 'south first'],
        clarksville: ['clarksville / west austin', 'clarksville', 'west austin', 'tarrytown', 'lake austin', 'deep eddy', 'west 6th'],
        domain: ['the domain / rock rose', 'domain', 'the domain', 'rock rose', 'north austin', 'domain northside', 'arboretum'],
        zilker: ['zilker / barton springs', 'zilker', 'barton springs', 'zilker park', 'greenbelt', 'barton hills'],
        'south-lamar': ['south lamar', 'solamar', 's lamar', 'lamar'],
        'north-loop': ['hyde park / north loop', 'north loop', 'hyde park', 'north campus'],
        burnet: ['burnet road', 'burnet', 'mid-north', 'allandale', 'rosedale', 'crestview'],
        mueller: ['mueller'],
    };
    const areaText = document.getElementById('area-text');
    const areaHint = form.querySelector('[data-area-hint]');
    function readArea() {
        const typed = areaText.value.trim().toLowerCase();
        const key = Object.keys(AREAS).find(k => AREAS[k].includes(typed));
        form.elements.area.value = key || 'anywhere';
        areaHint.textContent = key || !typed ? '' : `I don’t know “${areaText.value.trim()}” yet, so anywhere it is.`;
    }
    areaText.addEventListener('input', readArea);

    // "starting from": same neighborhood names, no "anywhere" (you have to start somewhere)
    const fromText = document.getElementById('from-text');
    fromText.addEventListener('input', () => {
        const typed = fromText.value.trim().toLowerCase();
        const key = Object.keys(AREAS).find(k => k !== 'anywhere' && AREAS[k].includes(typed));
        if (key) form.elements.start_from.value = key;
    });

    // ------------------------------------------------------------ share links: the same Saturday, for a friend
    const LABEL = { anywhere: 'Anywhere', ut: 'UT / West Campus', downtown: 'Downtown', east: 'East Austin',
                    soco: 'South Congress / South First', clarksville: 'Clarksville / West Austin', domain: 'The Domain / Rock Rose',
                    zilker: 'Zilker / Barton Springs', 'south-lamar': 'South Lamar', 'north-loop': 'Hyde Park / North Loop', burnet: 'Burnet Road', mueller: 'Mueller' };
    function shareLink() {
        const f = form.elements, q = new URLSearchParams({
            s: seed, start: f.start.value, end: f.end.value, hours: f.hours.value, mood: f.mood.value,
            from: f.start_from.value, area: f.area.value, travel: f.travel.value, budget: f.budget.value,
        });
        if (f.rainy.checked) q.set('rain', '1');
        if (f.include.value) q.set('in', f.include.value);
        if (f.exclude.value) q.set('not', f.exclude.value);
        return `${location.origin}${location.pathname}?${q}`;
    }
    (function openShared() {
        const q = new URLSearchParams(location.search);
        if (!q.has('s')) return;
        const f = form.elements, radio = (name, v) => { const r = form.querySelector(`input[name="${name}"][value="${v}"]`); if (r) r.checked = true; };
        seed = Number(q.get('s')) || seed;
        if (q.get('start')) f.start.value = q.get('start');
        if (q.get('end')) f.end.value = q.get('end');
        ['hours', 'mood', 'travel', 'budget'].forEach(n => q.get(n) && radio(n, q.get(n)));
        if (LABEL[q.get('from')]) { f.start_from.value = q.get('from'); document.getElementById('from-text').value = LABEL[q.get('from')]; }
        if (LABEL[q.get('area')]) { f.area.value = q.get('area'); document.getElementById('area-text').value = q.get('area') === 'anywhere' ? '' : LABEL[q.get('area')]; }
        f.rainy.checked = q.get('rain') === '1';
        if (q.get('in')) f.include.value = q.get('in');
        if (q.get('not')) { f.exclude.value = q.get('not'); document.getElementById('exclude-text').value = q.get('not'); }
        form.dataset.shared = '1';  // don't let live weather overrule a shared plan
    })();

    // ------------------------------------------------------------ the love letter
    const letterBox = document.getElementById('letter');
    const letterBody = document.getElementById('letter-body');
    const toInput = document.getElementById('letter-to'), fromInput = document.getElementById('letter-from');
    const letterNote = letterBox.querySelector('.letter-note');
    const VERB = { coffee: 'coffee at ', smoothie: 'a smoothie at ', brunch: 'brunch at ', lunch: 'lunch at ',
                   dinner: 'dinner at ', treat: 'something sweet at ', 'late night': 'one last stop at ',
                   exercise: 'a class at ', shopping: 'shopping at ', nails: 'nails at ', 'live music': 'a show at ',
                   nightlife: 'drinks at ', karaoke: 'karaoke at ', comedy: 'a show at ',
                   tea: 'boba at ', 'escape room': 'an escape room at ', boat: 'a sunset boat at ' };
    function composeLetter(plan) {
        const to = toInput.value.trim() || 'reader', from = fromInput.value.trim();
        const lines = [`Dearest ${to},`, '', 'Your Saturday has been decided. Do not argue.', ''];
        const stops = plan.stops.filter(s => s.type !== 'free');
        stops.forEach((s, i) => {
            const what = s.type === 'reset' ? `home, to ${s.note}`
                : `${VERB[s.category] || ''}${s.name}${s.note ? ` (${s.note})` : ''}`;
            lines.push(i === 0 ? `We begin at ${s.time} at ${what}.` : `At ${s.time}, ${what}.`);
            if (s.why) lines.push(s.why);
        });
        lines.push(`Home by ${plan.home}.`, '', 'Yours, until brunch,', from || '', '',
                   `P.S. It’s Saturday #${plan.seed}. See it here: ${shareLink()}`);
        return lines.join('\n').replace(/\n{3,}/g, '\n\n');
    }
    const refreshLetter = () => { if (lastPlan) letterBody.textContent = composeLetter(lastPlan); };
    document.querySelector('.seal-it:not(.save-it)').addEventListener('click', () => {
        letterNote.textContent = '';
        refreshLetter();
        letterBox.showModal();
    });
    [toInput, fromInput].forEach(i => i.addEventListener('input', refreshLetter));
    letterBox.querySelector('.close-letter').addEventListener('click', () => letterBox.close());
    // a long day scrolls inside the card: say so, until you reach the end
    const dayScroll = document.querySelector('.day .scroll'), more = document.querySelector('.day .more');
    const moreCue = () => { more.hidden = dayScroll.scrollHeight - dayScroll.scrollTop - dayScroll.clientHeight < 8; };
    dayScroll.addEventListener('scroll', moreCue, { passive: true });
    window.addEventListener('resize', moreCue);
    new MutationObserver(moreCue).observe(dayScroll, { childList: true, subtree: true });
    more.addEventListener('click', () => dayScroll.scrollBy({ top: dayScroll.clientHeight * 0.8, behavior: 'smooth' }));
    // on a phone the day is below the form
    document.querySelector('.see-day').addEventListener('click', () => document.querySelector('.day').scrollIntoView({ behavior: 'smooth' }));

    // The Method: the first three cards fill the screen down to the bottom line; scroll for the next three
    const method = document.getElementById('screen-method'), cards = method.querySelector('.cards');
    function fillCards() {
        cards.classList.remove('fill');
        cards.style.gridTemplateRows = '';
        if (method.hidden || innerWidth <= 1000) return;
        cards.classList.add('fill');
        const tracks = getComputedStyle(cards).gridTemplateRows.split(' ').map(parseFloat);
        const card = [...cards.children], per = 4;
        if (tracks.length < per * 2 || tracks.some(isNaN)) return;
        const top = cards.getBoundingClientRect().top - method.getBoundingClientRect().top + method.scrollTop;
        const pad = parseFloat(getComputedStyle(method).paddingBottom) || 0;
        const fit = method.clientHeight - top - pad - 4;  // row 1 ends at the bottom line
        const natural = Math.max(...[0, 3].map(i => card[i] ? card[i].getBoundingClientRect().height : 0));
        const room = [Math.max(fit, natural), Math.max(fit, natural)];  // and both rows are the same size
        for (let r = 0; r * 3 < card.length && r < 2; r++) {
            const extra = room[r] - card[r * 3].getBoundingClientRect().height;
            if (extra > 0) tracks[r * per] += extra;
        }
        cards.style.gridTemplateRows = tracks.map((x, i) => i % per === 0 ? x + 'px' : 'auto').join(' ');  // only the picture rows are pinned
    }
    const refit = new ResizeObserver(() => fillCards());
    [method, method.querySelector('.method-intro'), method.querySelector('.numbers')].forEach(e => e && refit.observe(e));
    window.addEventListener('resize', fillCards);
    method.addEventListener('refit', fillCards);
    document.fonts?.ready.then(fillCards);

    // the editor's own ideal Saturday
    const ideal = document.getElementById('ideal');
    document.querySelector('.ideal-open').addEventListener('click', () => ideal.showModal());
    ideal.querySelector('.close-ideal').addEventListener('click', () => ideal.close());
    ideal.addEventListener('click', e => { if (e.target === ideal) ideal.close(); });
    letterBox.addEventListener('click', e => { if (e.target === letterBox) letterBox.close(); });
    letterBox.querySelector('.copy').addEventListener('click', async () => {
        try {
            await navigator.clipboard.writeText(letterBody.textContent);
            letterNote.textContent = 'Copied. Now go send it.';
        } catch {
            letterNote.textContent = 'Your browser said no. Select the letter and copy it by hand.';
        }
    });
    letterBox.querySelector('.share').addEventListener('click', async () => {
        if (navigator.share) {
            try { await navigator.share({ title: 'Saturday in Austin', text: letterBody.textContent }); } catch { /* they changed their mind */ }
        } else {
            letterNote.textContent = 'Sharing works on your phone; on a laptop, copy it instead.';
        }
    });

    // ------------------------------------------------------------ Austin, right now (free, no key)
    const WEATHER = { 0: 'clear', 1: 'mostly clear', 2: 'partly cloudy', 3: 'cloudy', 45: 'foggy', 48: 'foggy',
                      51: 'drizzle', 53: 'drizzle', 55: 'drizzle', 61: 'rain', 63: 'rain', 65: 'heavy rain',
                      80: 'showers', 81: 'showers', 82: 'heavy showers', 95: 'thunderstorms', 96: 'thunderstorms', 99: 'thunderstorms' };
    const RAINY = new Set([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]);
    const wx = (key, text) => document.querySelectorAll(`[data-wx="${key}"]`).forEach(e => { e.textContent = text; });
    const clockOf = iso => { const [h, m] = iso.split('T')[1].split(':').map(Number); return `${h % 12 || 12}:${String(m).padStart(2, '0')}`; };
    const untilSaturday = (6 - new Date().getDay() + 7) % 7;
    wx('days-n', untilSaturday === 0 ? 'Today' : String(untilSaturday));
    wx('days-label', untilSaturday === 0 ? 'is Saturday' : untilSaturday === 1 ? 'day until Saturday' : 'days until Saturday');
    function verdictFor(high, rain, code) {
        if (rain >= 60 || RAINY.has(code)) return 'Rainy day plan, obviously. Museums, bookstores, a long lunch.';
        if (high >= 98) return 'Barton Springs is calling. Everything else can wait until sunset.';
        if (high >= 90) return 'Hot, but make it patio. Outside before noon, inside after.';
        if (high <= 55) return 'Sweater weather. Latte first, then everything.';
        return 'Perfect patio weather. You have no excuse.';
    }
    fetch('https://api.open-meteo.com/v1/forecast?latitude=30.2672&longitude=-97.7431' +
          '&current=temperature_2m,apparent_temperature,relative_humidity_2m,weather_code' +
          '&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code,sunset' +
          '&temperature_unit=fahrenheit&timezone=America%2FChicago&forecast_days=8')
        .then(r => r.json())
        .then(w => {
            const c = w.current, d = w.daily;
            wx('temp', `${Math.round(c.temperature_2m)}°`);
            wx('sky', WEATHER[c.weather_code] || 'the weather');
            wx('feels', `feels like ${Math.round(c.apparent_temperature)}°`);
            wx('hilo', `${Math.round(d.temperature_2m_max[0])}° / ${Math.round(d.temperature_2m_min[0])}°`);
            wx('feels', `feels like ${Math.round(c.apparent_temperature)}°, ${c.relative_humidity_2m}% humidity`);
            wx('sunset', clockOf(d.sunset[0]));
            const now = new Date().toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago' });
            wx('src', `Open-Meteo weather, updated ${now} CT · Census 2025 population`);
            const i = untilSaturday;  // the forecast starts today, so Saturday is this many days in
            const high = Math.round(d.temperature_2m_max[i]), rain = d.precipitation_probability_max[i] ?? 0;
            wx('sat-title', i === 0 ? 'Today is Saturday' : `This Saturday, ${d.time[i].slice(5).replace('-', '/')}`);
            wx('sat-temp', `${high}° / ${Math.round(d.temperature_2m_min[i])}°`);
            wx('sat-rain', `${rain}% chance of rain · ${WEATHER[d.weather_code[i]] || ''}`);
            wx('sat-verdict', verdictFor(high, rain, d.weather_code[i]));
            // rain on Saturday (or right now, if it's Saturday) turns on Rainy day
            if (high >= 90 && !hotSaturday) { hotSaturday = true; run(); }
            const wet = i === 0 ? RAINY.has(c.weather_code) || rain >= 60 : rain >= 60;
            if (wet && !form.dataset.shared && !form.elements.rainy.checked) {
                autoRain = true;
                form.elements.rainy.checked = true;
                run();
            }
        })
        .catch(() => wx('sky', 'weather unavailable'));

    // The great debate: big small city or small big city. Tallies live in a free public counter
    // (no names, no data, just two numbers); your own vote is remembered in this browser.
    const vote = document.querySelector('[data-vote]');
    if (vote) {
        const COUNTER = 'https://abacus.jasoncameron.dev';
        const PICKS = ['big-small', 'small-big'];
        const LINES = {
            'big-small': 'Big small city. Everyone knows everyone, and still no parking.',
            'small-big': 'Small big city. The skyline got tall, the vibe stayed barefoot.',
        };
        const note = vote.querySelector('[data-vote-note]');
        const mine = (() => { try { return localStorage.getItem('austin-vote'); } catch { return null; } })();
        const count = (pick, hit) => fetch(`${COUNTER}/${hit ? 'hit' : 'get'}/saturday-in-austin/${pick}`)
            .then(r => r.ok ? r.json() : { value: 0 }).then(d => d.value || 0).catch(() => null);

        const show = (pick, tallies) => {
            vote.classList.add('voted');
            vote.querySelectorAll('[data-pick]').forEach(b => b.setAttribute('aria-pressed', b.dataset.pick === pick));
            if (tallies.some(n => n === null)) { note.textContent = `${LINES[pick]} (The tally is shy right now.)`; return; }
            const total = tallies[0] + tallies[1] || 1;
            PICKS.forEach((p, i) => {
                const b = vote.querySelector(`[data-pick="${p}"]`), pct = Math.round(100 * tallies[i] / total);
                b.querySelector('.vote-bar i').style.width = pct + '%';
                b.querySelector('.vote-pct').textContent = `${pct}% · ${tallies[i].toLocaleString()} vote${tallies[i] === 1 ? '' : 's'}`;
            });
            const lead = tallies[0] === tallies[1] ? null : PICKS[tallies[0] > tallies[1] ? 0 : 1];
            note.textContent = LINES[pick] + (lead === null ? ' And Austin is split, obviously.' : lead === pick ? ' Austin agrees.' : ' Bold. Austin disagrees.');
        };

        if (PICKS.includes(mine)) Promise.all(PICKS.map(p => count(p))).then(t => show(mine, t));
        vote.querySelectorAll('[data-pick]').forEach(b => b.addEventListener('click', async () => {
            if (vote.classList.contains('voted')) return;  // one vote each
            const pick = b.dataset.pick;
            try { localStorage.setItem('austin-vote', pick); } catch {}
            vote.classList.add('voted');
            show(pick, await Promise.all(PICKS.map(p => count(p, p === pick))));
        }));
    }

    // Austin by the numbers ‹ › Saturday in Austin by the numbers
    const flip = document.querySelector('[data-flip]');
    if (flip) {
        const pages = [...flip.querySelectorAll('[data-flip-page]')], title = flip.querySelector('[data-flip-title]');
        let on = 0;
        flip.querySelectorAll('[data-flip-go]').forEach(b => b.addEventListener('click', () => {
            on = (on + +b.dataset.flipGo + pages.length) % pages.length;
            pages.forEach((p, i) => { p.hidden = i !== on; });
            title.textContent = pages[on].dataset.title;
            flip.querySelector('[data-flip-count]').textContent = `${on + 1} / ${pages.length}`;
        }));
    }

    // The map: tap a neighborhood to see the drives the planner knows from there
    const MAP = {"names": {"1": "Campus / UT Corridor", "2": "Downtown", "3": "Clarksville / West Austin", "4": "South Congress", "5": "East Austin", "6": "South Lamar", "7": "The Domain / Rock Rose", "8": "West Campus", "9": "Zilker / Barton Springs", "10": "Hyde Park / North Loop", "11": "Lake Austin / West Austin", "12": "Mueller", "13": "South First", "14": "Burnet Road / Mid-North"}, "count": {"1": 11, "2": 60, "3": 12, "4": 23, "5": 37, "6": 19, "7": 22, "8": 14, "9": 15, "10": 12, "11": 9, "12": 5, "13": 4, "14": 8}, "roads": [[8, 1, 4], [1, 2, 7], [8, 2, 8], [8, 3, 6], [3, 2, 6], [3, 11, 7], [1, 10, 7], [10, 14, 6], [14, 7, 12], [10, 12, 8], [1, 12, 10], [5, 12, 8], [1, 5, 8], [2, 5, 6], [2, 4, 7], [2, 13, 7], [4, 13, 3], [13, 6, 5], [6, 9, 5], [2, 9, 8], [9, 4, 6], [11, 9, 9], [11, 7, 20], [11, 14, 12]]};
    const atx = document.querySelector('.atx');
    if (atx) {
        const note = document.querySelector('[data-map-note]'), lines = atx.querySelector('.atx-drives');
        const two = n => String(n).padStart(2, '0');
        let picked = null;
        const pick = n => {
            picked = picked === n ? null : n;
            document.querySelectorAll('.atx-dots g, .map-key li').forEach(e => e.classList.toggle('on', +e.dataset.n === picked));
            lines.classList.toggle('focus', picked !== null);
            lines.querySelectorAll('[data-a]').forEach(l => l.classList.toggle('on', picked !== null && (+l.dataset.a === picked || +l.dataset.b === picked)));
            const [kicker, name, body] = note.children;
            if (picked === null) {
                kicker.textContent = 'Tap a number'; name.textContent = 'Pick a neighborhood.';
                body.textContent = 'See how many places it has, and every drive the planner knows from there.';
                return;
            }
            const near = MAP.roads.filter(r => r[0] === picked || r[1] === picked)
                .map(([a, b, m]) => [a === picked ? b : a, m]).sort((x, y) => x[1] - y[1]);
            const count = MAP.count[picked];
            kicker.textContent = `${two(picked)} · ${count} place${count === 1 ? '' : 's'} in the planner`;
            name.textContent = MAP.names[picked];
            body.textContent = 'Drives: ' + near.map(([n, m]) => `${m} min to ${MAP.names[n]}`).join(' · ') + '.';
        };
        const hover = (n, on) => document.querySelectorAll(`.atx-dots g[data-n="${n}"], .map-key li[data-n="${n}"]`).forEach(x => x.classList.toggle('hov', on));
        document.querySelectorAll('.atx-dots g, .map-key li').forEach(e => {
            e.addEventListener('mouseenter', () => hover(e.dataset.n, true));
            e.addEventListener('mouseleave', () => hover(e.dataset.n, false));
            e.addEventListener('click', () => pick(+e.dataset.n));
            e.addEventListener('keydown', k => { if (k.key === 'Enter' || k.key === ' ') { k.preventDefault(); pick(+e.dataset.n); } });
        });
    }

    // Longhorns football, live from ESPN: record, SEC standing, last score, next game
    const tx = (key, text) => document.querySelectorAll(`[data-tx="${key}"]`).forEach(e => { e.textContent = text; });
    const ESPN = 'https://site.api.espn.com/apis/site/v2/sports/football/college-football/teams/251';
    // ESPN doesn't flag conference games, so the SEC record is counted against the other fifteen SEC schools
    const SEC = new Set(['333', '8', '2', '57', '61', '96', '99', '145', '344', '142', '201', '2579', '2633', '245', '238']);
    Promise.all([fetch(ESPN).then(r => r.json()), fetch(ESPN + '/schedule').then(r => r.json())])
        .then(([team, sched]) => {
            tx('standing', (team.team.standingSummary || '').replace(' in SEC', '') || '–');
            const games = sched.events.map(e => {
                const c = e.competitions[0], us = c.competitors.find(x => x.team.id === '251'), them = c.competitors.find(x => x.team.id !== '251');
                return { done: c.status.type.completed, date: new Date(e.date), home: us.homeAway === 'home', them: them.team.shortDisplayName,
                         us: us.score?.displayValue, they: them.score?.displayValue, won: us.winner,
                         sec: SEC.has(them.team.id) && e.seasonType?.type === 2 };
            });
            const sec = games.filter(g => g.done && g.sec);
            tx('record', `${sec.filter(g => g.won).length}–${sec.filter(g => !g.won).length}`);
            const last = games.filter(g => g.done).pop(), next = games.find(g => !g.done);
            if (last) {
                tx('last', `${last.won ? 'W' : 'L'} ${last.us}–${last.they}`);
                tx('last-label', `last game, ${last.home ? 'vs' : 'at'} ${last.them}`);
            }
            if (next) {
                tx('next', next.date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', timeZone: 'America/Chicago' }));
                tx('next-label', `next game, ${next.home ? 'vs' : 'at'} ${next.them}`);
            } else { tx('next', '–'); tx('next-label', 'season’s over'); }
        })
        .catch(() => { tx('record', '–'); tx('standing', '–'); tx('last', '–'); tx('next', '–'); tx('next-label', 'scores are shy right now'); });

    // The Column: tap a cover to read it
    const storyBox = document.getElementById('story'), storyBody = storyBox.querySelector('.story-body');
    const openStory = key => {
        const tpl = document.getElementById('story-' + key);
        if (!tpl) return;
        storyBody.replaceChildren(tpl.content.cloneNode(true));
        storyBox.showModal();
        storyBox.querySelector('.story-paper').scrollTop = 0;
    };
    document.querySelectorAll('.story[data-story]').forEach(c => {
        c.addEventListener('click', () => openStory(c.dataset.story));
        c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openStory(c.dataset.story); } });
    });
    storyBox.querySelector('.close-story').addEventListener('click', () => storyBox.close());
    // shareable links: #four-days opens the four-day plan (and the header link does the same)
    const HASHES = { 'four-days': 'four', 'make-something': 'make', 'nightlife': 'bars', 'live-music': 'music', 'austin-decoded': 'symbols',
                     'vegan-edit': 'vegan', 'neighborhoods': 'hoods', 'college-town': 'college', 'worth-a-follow': 'follow' };
    document.querySelectorAll('[data-open-story]').forEach(a => a.addEventListener('click', e => {
        e.preventDefault();
        history.replaceState(null, '', '#' + Object.keys(HASHES).find(k => HASHES[k] === a.dataset.openStory));
        openStory(a.dataset.openStory);
    }));
    storyBox.addEventListener('close', () => { if (location.hash) history.replaceState(null, '', location.pathname + location.search); });
    if (HASHES[location.hash.slice(1)]) openStory(HASHES[location.hash.slice(1)]);
    storyBox.addEventListener('click', e => {
        if (e.target === storyBox) storyBox.close();
        const plan = e.target.closest('[data-plan-mood]');
        if (plan) {  // from the article straight to a matching Saturday
            storyBox.close();
            form.elements.mood.value = plan.dataset.planMood;
            show('plan');
            form.dispatchEvent(new Event('change'));
        }
        const save = e.target.closest('[data-download]');
        if (save) downloadStory(save.dataset.download, save);
    });

    // PDFs, set like the page: gold kicker, Bodoni-ish headline, typewriter dek, pink italic heads
    let jspdf;
    async function savePdf(name, blocks, button) {
        const label = button.textContent;
        if (button.dataset.download) button.textContent = 'One moment…';
        try {
            jspdf ??= await new Promise((ok, fail) => {
                const tag = Object.assign(document.createElement('script'), { src: 'https://cdnjs.cloudflare.com/ajax/libs/jspdf/2.5.1/jspdf.umd.min.js' });
                tag.onload = () => ok(window.jspdf); tag.onerror = fail;
                document.head.append(tag);
            });
            const doc = new jspdf.jsPDF({ unit: 'pt', format: 'letter' });
            const W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight(), M = 64;
            let y = M;
            const write = (text, font, style, size, color, gap, lead = 1.45) => {
                doc.setFont(font, style).setFontSize(size).setTextColor(...color);
                for (const line of doc.splitTextToSize(text.replace(/\s+/g, ' ').trim(), W - 2 * M)) {
                    if (y + size > H - M) { doc.addPage(); y = M; }
                    doc.text(line, M, y + size); y += size * lead;
                }
                y += gap;
            };
            const INK = [17, 17, 17], PINK = [184, 13, 98], GOLD = [184, 151, 90], GREY = [110, 110, 110];
            for (const [kind, text] of blocks) {
                if (kind === 'kicker') write(text.toUpperCase(), 'helvetica', 'bold', 8, GOLD, 6);
                else if (kind === 'h2') write(text, 'times', 'normal', 34, INK, 4, 1.1);
                else if (kind === 'dek') { write(text, 'courier', 'normal', 10.5, INK, 6);
                    doc.setDrawColor(...INK).setLineWidth(0.6).line(M, y, W - M, y).line(M, y + 3, W - M, y + 3); y += 18; }
                else if (kind === 'h3') write(text, 'times', 'italic', 16, PINK, 2);
                else if (kind === 'tip') write(text, 'times', 'italic', 10.5, GREY, 8);
                else if (kind === 'small') write(text, 'helvetica', 'normal', 8.5, GREY, 8);
                else write(text, 'helvetica', 'normal', 10, INK, 8);
            }
            doc.setFont('helvetica', 'normal').setFontSize(8).setTextColor(...GREY)
               .text('Saturday in Austin · suhxnitiwari.github.io/saturday-in-austin', M, H - 36);
            doc.save(name + '.pdf');
        } catch { alert('The download didn’t load. Try again in a moment.'); }
        button.textContent = label;
    }
    const downloadStory = (name, button) => savePdf(name, [...storyBody.children].flatMap(el =>
        el.matches('.st-kicker') ? [['kicker', el.textContent]] : el.matches('h2') ? [['h2', el.textContent]]
        : el.matches('.st-dek') ? [['dek', el.textContent]] : el.matches('h3') ? [['h3', el.textContent]]
        : el.matches('.st-tip') ? [['tip', el.textContent]] : el.matches('p') ? [['p', el.textContent]]
        : el.matches('ul') ? [...el.children].map(li => ['p', li.textContent]) : []), button);

    // Download the Saturday on screen: every stop, the trips between, and the link back
    document.querySelector('.save-it').addEventListener('click', e => {
        const plan = lastPlan, st = plan.stats, blocks = [
            ['kicker', `Saturday in Austin · Saturday #${plan.seed}`],
            ['h2', 'Your Saturday.'],
            ['dek', `${st.stops} ${st.stops === 1 ? 'stop' : 'stops'} · ${st.hours_out} hours out · about $${st.spend} · home by ${plan.home}`]];
        const hop = (via, minutes, fare) => via === 'uber' ? `Uber, ${minutes} min, about $${fare}`
            : `${minutes} min ${via === 'bus' ? 'bus' : via === 'walk' ? 'walk' : 'drive'}`;
        plan.stops.forEach((s, i) => {
            if (s.type === 'free') { blocks.push(['small', `Free time · ${duration(s.free)} to wander`]); return; }
            if (s.travel && i) blocks.push(['small', hop(s.via, s.travel, s.fare)]);
            if (s.type === 'reset') { blocks.push(['h3', `${s.time} · Home`], ['p', `${s.note} · ${s.minutes} min`]); return; }
            const where = s.where === 'home' ? 'at home' : s.where;
            blocks.push(['h3', `${s.time} · ${s.name}`], ['p', `${s.label} · ${s.note || where} · ${duration(s.minutes)}`]);
            if (s.why) blocks.push(['tip', s.why]);
        });
        if (plan.back) blocks.push(['small', `${hop(plan.back_via, plan.back, plan.back_fare)} home`]);
        blocks.push(['h3', `${plan.home} · Home`], ['p', plan.sign_off], ['small', `See it again: ${shareLink()}`]);
        savePdf(`saturday-${plan.seed}`, blocks, e.currentTarget);
    });

    // The editor's photos: arrows, arrow keys, or a swipe
    const slides = document.querySelector('[data-slides]');
    if (slides) {
        const pics = [...slides.querySelectorAll('img')], count = document.querySelector('[data-slide-count]');
        const pad = n => String(n).padStart(2, '0');
        let at = 0;
        const go = d => {
            at = (at + d + pics.length) % pics.length;
            pics.forEach((p, i) => { p.hidden = i !== at; });
            count.textContent = `${pad(at + 1)} / ${pad(pics.length)}`;
        };
        document.querySelectorAll('[data-slide]').forEach(b => b.addEventListener('click', () => go(+b.dataset.slide)));
        slides.addEventListener('keydown', e => { if (e.key === 'ArrowLeft') go(-1); if (e.key === 'ArrowRight') go(1); });
        let x0 = null;
        slides.addEventListener('touchstart', e => { x0 = e.touches[0].clientX; }, { passive: true });
        slides.addEventListener('touchend', e => {
            const dx = e.changedTouches[0].clientX - (x0 ?? e.changedTouches[0].clientX);
            if (Math.abs(dx) > 40) go(dx < 0 ? 1 : -1);
            x0 = null;
        });
    }

    run();
})();
