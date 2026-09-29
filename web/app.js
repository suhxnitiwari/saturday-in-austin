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

    // the planner's four tabs, one panel at a time
    const tabs = [...form.querySelectorAll('[role="tab"]')];
    const pick = tab => tabs.forEach(t => {
        const on = t === tab;
        t.setAttribute('aria-selected', on);
        t.tabIndex = on ? 0 : -1;
        document.getElementById(t.getAttribute('aria-controls')).hidden = !on;
    });
    tabs.forEach((t, i) => {
        t.addEventListener('click', () => pick(t));
        t.addEventListener('keydown', e => {
            const step = { ArrowRight: 1, ArrowLeft: -1 }[e.key];
            if (step) { const next = tabs[(i + step + tabs.length) % tabs.length]; pick(next); next.focus(); }
        });
    });
    form.querySelectorAll('.next').forEach(b => b.addEventListener('click', () => pick(document.getElementById(b.dataset.next))));

    // under each tab, what's picked so far
    const label = name => form.querySelector(`input[name="${name}"]:checked + span`)?.textContent || '';
    const time = v => { const [h, m] = v.split(':').map(Number); return `${h % 12 || 12}${m ? ':' + String(m).padStart(2, '0') : ''} ${h < 12 ? 'AM' : 'PM'}`; };
    function summarize() {
        const f = form.elements, set = (k, v) => { form.querySelector(`[data-show="${k}"]`).textContent = v; };
        set('when', f.start.value && f.end.value ? `${time(f.start.value)}–${time(f.end.value)}, ${label('hours').toLowerCase()}` : '');
        set('mood', label('mood'));
        set('where', label('area'));
        const extras = [f.rainy.checked && 'rain', f.walk.checked && 'no car', f.include.value && '+ ' + f.include.value,
                        f.exclude.value && 'no ' + f.exclude.value].filter(Boolean);
        set('extras', extras.join(', ') || 'none');
    }
    form.addEventListener('input', summarize);
    form.addEventListener('change', summarize);
    summarize();

    run();
})();
