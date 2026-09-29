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
        document.querySelector('.seal-it').disabled = false;
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
    const FOOD = new Set(['coffee', 'smoothie', 'brunch', 'lunch', 'dinner', 'treat', 'late night', 'order in', 'snack']);
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
    }

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
                                f.travel.value, f.budget.value, f.start_from.value);
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
    };
    sections.forEach(b => b.addEventListener('click', () => show(b.dataset.screen)));
    document.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => show(b.dataset.go)));

    // our own dropdowns (the browser's datalist popups don't match the page)
    const NOTS = { Workouts: 'workouts', Museums: 'museums', Shopping: 'shopping', 'Anything outdoors': 'outdoors',
                   'Live music': 'live-music', Studying: 'studying', Sweets: 'sweets' };
    const SOURCES = {
        starts: () => ['UT / West Campus', 'Downtown', 'East Austin', 'South Congress', 'Clarksville / West Austin',
                       'Domain / North Austin', 'Zilker', 'South Lamar', 'North Loop / Hyde Park', 'Mueller'].map(v => [v, '']),
        areas: () => ['Anywhere', 'UT / West Campus', 'Downtown', 'East Austin', 'South Congress', 'Clarksville / West Austin',
                      'Domain / North Austin', 'Zilker', 'South Lamar', 'North Loop / Hyde Park', 'Mueller'].map(v => [v, '']),
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
        soco: ['south congress', 'soco', 'bouldin', 'bouldin creek', 'travis heights', 'south 1st', 's 1st'],
        clarksville: ['clarksville / west austin', 'clarksville', 'west austin', 'tarrytown', 'lake austin', 'deep eddy', 'west 6th'],
        domain: ['domain / north austin', 'domain', 'the domain', 'north austin', 'domain northside', 'arboretum'],
        zilker: ['zilker', 'barton springs', 'zilker park'],
        'south-lamar': ['south lamar', 'solamar', 's lamar', 'lamar'],
        'north-loop': ['north loop / hyde park', 'north loop', 'hyde park', 'north campus', 'burnet'],
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
                    soco: 'South Congress', clarksville: 'Clarksville / West Austin', domain: 'Domain / North Austin',
                    zilker: 'Zilker', 'south-lamar': 'South Lamar', 'north-loop': 'North Loop / Hyde Park', mueller: 'Mueller' };
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
                   exercise: 'a class at ', shopping: 'shopping at ', nails: 'nails at ', 'live music': 'a show at ' };
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
    document.querySelector('.seal-it').addEventListener('click', () => {
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
            wx('src', `Open-Meteo weather, updated ${now} CT · Wikidata population`);
            const i = untilSaturday;  // the forecast starts today, so Saturday is this many days in
            const high = Math.round(d.temperature_2m_max[i]), rain = d.precipitation_probability_max[i] ?? 0;
            wx('sat-title', i === 0 ? 'Today is Saturday' : `This Saturday, ${d.time[i].slice(5).replace('-', '/')}`);
            wx('sat-temp', `${high}° / ${Math.round(d.temperature_2m_min[i])}°`);
            wx('sat-rain', `${rain}% chance of rain · ${WEATHER[d.weather_code[i]] || ''}`);
            wx('sat-verdict', verdictFor(high, rain, d.weather_code[i]));
            // rain on Saturday (or right now, if it's Saturday) turns on Rainy day
            const wet = i === 0 ? RAINY.has(c.weather_code) || rain >= 60 : rain >= 60;
            if (wet && !form.dataset.shared && !form.elements.rainy.checked) {
                autoRain = true;
                form.elements.rainy.checked = true;
                run();
            }
        })
        .catch(() => wx('sky', 'weather unavailable'));
    fetch('https://www.wikidata.org/w/api.php?action=wbgetclaims&entity=Q16559&property=P1082&format=json&origin=*')
        .then(r => r.json())
        .then(d => {
            // the newest population figure (each one has a "point in time")
            const figures = d.claims.P1082.map(c => ({
                n: Number(c.mainsnak.datavalue.value.amount),
                year: ((c.qualifiers || {}).P585 || [{}])[0].datavalue?.value.time.slice(1, 5) || '',
            })).sort((a, b) => b.year.localeCompare(a.year));
            wx('pop', figures[0].n.toLocaleString('en-US'));
            wx('pop-year', figures[0].year ? `population, ${figures[0].year} census` : 'people');
        })
        .catch(() => wx('pop', '1M-ish'));

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
    const MAP = {"names": {"1": "Campus", "2": "Downtown", "3": "Clarksville", "4": "South Congress", "5": "East Austin", "6": "South Lamar", "7": "The Domain", "8": "West Campus", "9": "Zilker", "10": "North Loop", "11": "Lake Austin", "12": "Mueller", "13": "Barton Creek", "14": "Northwest", "15": "Southeast", "16": "Southwest", "17": "Hill Country"}, "count": {"1": 19, "2": 29, "3": 7, "4": 28, "5": 30, "6": 14, "7": 14, "8": 7, "9": 13, "10": 12, "11": 6, "12": 3, "13": 5, "14": 2, "15": 1, "16": 1, "17": 5}, "roads": [[1, 8, 4], [1, 10, 8], [1, 2, 7], [1, 5, 8], [8, 3, 6], [8, 2, 8], [3, 2, 6], [3, 11, 7], [10, 7, 14], [2, 5, 6], [2, 4, 7], [2, 9, 8], [9, 4, 6], [11, 9, 9], [9, 13, 10], [6, 9, 5], [6, 4, 7], [13, 17, 30], [2, 15, 18], [4, 15, 15], [11, 14, 12], [7, 14, 15], [13, 16, 12], [6, 16, 15], [1, 12, 10], [10, 12, 8], [5, 12, 8]]};
    const atx = document.querySelector('.atx');
    if (atx) {
        const note = document.querySelector('[data-map-note]'), lines = atx.querySelector('.atx-drives');
        const two = n => String(n).padStart(2, '0');
        let picked = null;
        const pick = n => {
            picked = picked === n ? null : n;
            document.querySelectorAll('.atx-dots g, .map-key li').forEach(e => e.classList.toggle('on', +e.dataset.n === picked));
            lines.classList.toggle('focus', picked !== null);
            lines.querySelectorAll('line').forEach(l => l.classList.toggle('on', picked !== null && (+l.dataset.a === picked || +l.dataset.b === picked)));
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
