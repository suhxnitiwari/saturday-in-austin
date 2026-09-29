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
            py.runPython('import sys; sys.path.insert(0, "/home/pyodide")\nfrom saturday.web import plan_json, names');
            const places = document.getElementById('places');
            for (const name of JSON.parse(py.globals.get('names')())) {
                places.appendChild(Object.assign(document.createElement('option'), { value: name }));
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
        const verb = plan.walking ? 'walk' : 'drive';
        plan.stops.forEach((s, i) => {
            if (s.type !== 'free' && s.travel && i) list.appendChild(el('li', 'travel', `${s.travel} min ${verb}`));
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
        if (plan.back) list.appendChild(el('li', 'travel', `${plan.back} min ${verb} home`));
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
            figure(st.travel, `min ${plan.walking ? 'walking' : 'driving'}`),
            figure(st.neighborhoods, st.neighborhoods === 1 ? 'neighborhood' : 'neighborhoods'),
        );
        stats.hidden = false;
        number.textContent = `xoxo, Saturday #${plan.seed}`;
        verdict(plan);
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
            await new Promise(r => requestAnimationFrame(() => setTimeout(r, 0)));
            if (ticket !== pending) return;  // a newer change is already on its way
            const f = form.elements;
            const result = plan(f.start.value, f.end.value, f.hours.value, f.mood.value, String(seed),
                                f.walk.checked, f.rainy.checked, f.area.value, f.include.value, f.exclude.value);
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
    areaText.addEventListener('focus', () => areaText.select());

    run();
})();
