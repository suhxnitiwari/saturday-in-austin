// Saturday in Austin ✦ runs the Python planner in this repo
// in the visitor's browser with Pyodide. Python only downloads once the planner is on screen.
(() => {
    const root = document.querySelector('.sat-planner');
    if (!root) return;

    const PYODIDE = 'https://cdn.jsdelivr.net/pyodide/v0.26.4/full/';
    const BASE = 'saturday/';  // served straight from this repo by GitHub Pages
    const FILES = ['__init__.py', '__main__.py', 'city.py', 'planner.py', 'spots.py', 'sass.py', 'web.py', 'data/spots.csv', 'data/shelf.json'];

    const form = root.querySelector('.sat-form');
    const out = root.querySelector('.sat-out');
    const button = form.querySelector('button[type="submit"]');
    const random = form.querySelector('.sat-random');
    const hours = form.elements.hours;
    const hoursOut = form.querySelector('.sat-hours output');

    hours.addEventListener('input', () => { hoursOut.textContent = hours.value; });

    const loadScript = src => new Promise((resolve, reject) => {
        const s = document.createElement('script');
        s.src = src;
        s.onload = resolve;
        s.onerror = reject;
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
            py.runPython('import sys; sys.path.insert(0, "/home/pyodide")\nfrom saturday.web import plan_json');
            return py.globals.get('plan_json');
        })();
        python.catch(() => { python = null; });  // let the next click try again
        return python;
    }

    // start downloading Python as soon as the slide is on screen, so the first click is quick
    new IntersectionObserver((entries, obs) => {
        if (entries.some(e => e.isIntersecting)) { boot().catch(() => {}); obs.disconnect(); }
    }).observe(root);

    const line = (cls, ...parts) => {
        const p = document.createElement('p');
        p.className = cls;
        parts.forEach(([tag, text]) => {
            const el = document.createElement(tag);
            el.textContent = text;
            p.appendChild(el);
        });
        return p;
    };

    function draw(plan) {
        out.replaceChildren();
        for (const note of plan.sass || []) out.appendChild(line('sat-sass', ['span', note]));
        if (!plan.stops.length) {
            out.appendChild(line('sat-status', ['span', 'Nothing fits. Try more hours out, a later bedtime or a different mood.']));
            return;
        }
        out.appendChild(line('sat-head', ['span', 'Your Saturday ✦']));
        for (const s of plan.stops) {
            if (s.free) {
                const h = Math.floor(s.free / 60), m = s.free % 60;
                out.appendChild(line('sat-row sat-free', ['b', s.time], ['span', `free time (${h ? (m ? `${h}h ${m}m` : `${h}h`) : `${m} min`}): nap, journal, wander`]));
            } else {
                const row = line('sat-row', ['b', s.time], ['span', s.name]);
                if (s.note) row.lastChild.appendChild(Object.assign(document.createElement('i'), { textContent: ` (${s.note})` }));
                out.appendChild(row);
            }
        }
        out.appendChild(line('sat-row', ['b', plan.home], ['span', plan.sign_off]));
        const count = plan.stops.filter(s => s.name).length;
        out.appendChild(line('sat-foot', ['span',
            `${count} stop${count === 1 ? '' : 's'} · ${plan.hours_out} hour${plan.hours_out === 1 ? '' : 's'} out · ${plan.driving} min of ${plan.walking ? 'walking' : 'driving'} · Saturday #${plan.seed}`]));
    }

    // can't decide? pick everything at random, then plan it
    random.addEventListener('click', () => {
        const pick = list => list[Math.floor(Math.random() * list.length)];
        const f = form.elements;
        const wake = pick([7, 7.5, 8, 8.5, 9, 9.5, 10, 10.5, 11, 11.5, 12]);
        const sleep = pick([21, 22, 22.5, 23, 23.5, 24, 25]);  // 24 and 25 are midnight and 1 AM
        const free = sleep - wake - 1.25;  // minus getting ready and winding down
        const time = h => `${String(Math.floor(h) % 24).padStart(2, '0')}:${h % 1 ? '30' : '00'}`;
        f.wake.value = time(wake);
        f.sleep.value = time(sleep);
        f.hours.value = pick([3, 4, 5, 6, 7, 8, 9, 10, 11, 12].filter(h => h <= free));
        hoursOut.textContent = f.hours.value;
        f.mood.value = pick([...f.mood.options].map(o => o.value));
        form.requestSubmit(button);
    });

    form.addEventListener('submit', async e => {
        e.preventDefault();
        button.disabled = random.disabled = true;
        const first = !python;
        out.replaceChildren(line('sat-status', ['span', first ? 'Waking up Python in your browser… (first time takes a few seconds)' : 'Planning…']));
        try {
            const plan = await boot();
            const f = form.elements;
            draw(JSON.parse(plan(f.wake.value, f.sleep.value, Number(f.hours.value), f.mood.value, '', f.walk.checked, f.rainy.checked)));
            button.textContent = 'Plan another ✦';
        } catch (err) {
            out.replaceChildren(line('sat-status', ['span', 'Python took a nap. Check your connection and try again ✦']));
        } finally {
            button.disabled = random.disabled = false;
        }
    });
})();
