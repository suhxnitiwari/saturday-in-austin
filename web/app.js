// Saturday in Austin ✦ runs the Python planner in this repo in the visitor's browser with Pyodide.
// Every control replans right away with the same Saturday number; "another Saturday" draws a new one.
(() => {
    // installable: works offline and opens fast after the first visit
    if ('serviceWorker' in navigator && window.isSecureContext) navigator.serviceWorker.register('sw.js').catch(() => {});

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
    let lastPlan = null;   // the day on screen, for the calendar file and the PDF
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

    let python = null, deckFn = null;
    let swiped = { likes: [], nopes: [] };  // from Swipe to plan: the planner builds around the yeses
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
            py.runPython('import sys; sys.path.insert(0, "/home/pyodide")\nfrom saturday.web import plan_json, deck_json, names, stats');
            deckFn = py.globals.get('deck_json');
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

    // every stop opens in Google Maps, with directions the way you're getting around
    const TRAVELMODE = { transit: 'transit', walk: 'walking', car: 'driving', uber: 'driving' };
    const directions = (place, mode) => 'https://www.google.com/maps/dir/?api=1&destination='
        + encodeURIComponent(`${place.replace(/[()]/g, '')}, Austin, TX`) + `&travelmode=${TRAVELMODE[mode] || 'transit'}`;

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
        const hop = (via, minutes, fare) => via === 'uber' ? `Uber · ${minutes} min · ≈ $${fare}`
            : `${minutes} min ${via === 'bus' ? 'bus' : via === 'walk' ? 'walk' : 'drive'}`;
        plan.stops.forEach((s, i) => {
            if (s.type !== 'free' && s.travel && i) list.appendChild(el('li', 'travel', hop(s.via, s.travel, s.fare)));
            if (s.type === 'free') {
                list.appendChild(el('li', 'free', `free time · ${duration(s.free)} to wander`));
                return;
            }
            const li = el('li', s.type);
            // magazine order: time and category as the kicker, the name, then where and how long
            const kicker = el('span', 't', s.time);
            li.appendChild(kicker);
            if (s.type === 'reset') {
                li.appendChild(el('p', 'name', 'HOME'));
                li.appendChild(el('p', 'meta', `${s.note} · ${s.minutes} min`));
            } else {
                const where = s.where === 'home' ? 'at home' : s.where;
                kicker.appendChild(el('span', 'tag', ` · ${s.label}`));
                const name = el('p', 'name');
                name.appendChild(Object.assign(el('a', null, s.name), { href: directions(s.name, plan.mode), target: '_blank', rel: 'noopener' }));
                li.appendChild(name);
                li.appendChild(el('p', 'meta', [where, s.note, duration(s.minutes)].filter(Boolean).join(' · ')));
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
        lastPlan = plan;
        document.querySelectorAll('.save-it, .cal-it').forEach(b => { b.disabled = false; });
        document.querySelector('.see-day').textContent = `Your Saturday · ${st.stops} ${st.stops === 1 ? 'stop' : 'stops'} · $${st.spend} ↑`;
        thisSaturday().filter(e => e.heads).reverse().forEach(e => {  // the city's plans for this Saturday
            const banner = el('div', 'happening'), text = el('p');
            text.append(el('b', null, `This Saturday: ${e.name}.`), e.heads);
            const see = el('button', null, 'What’s on');
            see.type = 'button';
            see.addEventListener('click', () => show('calendar'));
            banner.append(text, see);
            sassBox.prepend(banner);
            sassBox.hidden = false;
        });
        if (awayDay && !gameDay) {  // an away game: watch it by campus
            const banner = el('div', 'gameday'), text = el('p');
            text.append(el('b', null, 'Saturdays are for the boys.'), `Texas plays at ${awayDay.them} today. Watch it at Victory Lap on 24th.`);
            const go = el('button', null, 'Plan a watch party');
            go.type = 'button';
            go.addEventListener('click', () => { form.elements.include.value = 'Victory Lap'; form.elements.mood.value = 'social'; run(); });
            banner.append(text, go);
            sassBox.prepend(banner);
            sassBox.hidden = false;
        }
        if (gameDay) {  // home game this Saturday
            const banner = el('div', 'gameday'), text = el('p');
            text.append(el('b', null, 'Saturdays are for the boys.'), `Game day: Texas vs. ${gameDay.them} at DKR${gameDay.time ? `, ${gameDay.time}` : ''}.`);
            const go = el('button', null, 'Build my game day');
            go.type = 'button';
            go.addEventListener('click', () => { form.elements.include.value = 'Texas Longhorns at DKR'; form.elements.mood.value = 'social'; run(); });
            banner.append(text, go);
            sassBox.prepend(banner);
            sassBox.hidden = false;
        }
        if (autoRain && form.elements.rainy.checked) {
            sassBox.prepend(el('p', null, 'Rain in the Saturday forecast, so I turned on Rainy day.'));
            sassBox.hidden = false;
        }
    }

    let hotSaturday = false;  // set from the forecast: 90° and up means a swim
    let gameDay = null;  // set from ESPN: the Longhorns are home this Saturday
    let awayDay = null;  // or they're playing somewhere else, and Victory Lap has the TVs
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
                                f.travel.value, f.budget.value, f.start_from.value, hotSaturday,
                                swiped.likes.join(','), swiped.nopes.join(','), !!swiped.group, !!gameDay,
                                thisSaturday().flatMap(e => e.closes || []).join(','));
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
    form.addEventListener('change', e => {  // a new mood, place or forecast means a new deck: old yeses step aside
        if (['mood', 'area', 'start_from', 'rainy'].includes(e.target.name)) swiped = { likes: [], nopes: [] };
        soon();
    });
    form.addEventListener('submit', e => { e.preventDefault(); run(); });
    again.addEventListener('click', () => { seed = 1000 + Math.floor(Math.random() * 9000); run(); });  // same yeses, new day

    // Swipe to plan: a hand of places for this mood and these hours; right is yes, left is no
    const swipeBox = document.getElementById('swipe'), deckEl = swipeBox.querySelector('.deck');
    const countEl = swipeBox.querySelector('.swipe-count'), doneBtn = swipeBox.querySelector('.swipe-done');
    const yesBtn = swipeBox.querySelector('.swipe-yes'), noBtn = swipeBox.querySelector('.swipe-no');
    const shareBtn = swipeBox.querySelector('.swipe-share'), groupEl = swipeBox.querySelector('.swipe-group'), noteEl = swipeBox.querySelector('.swipe-note');
    const mine = () => hand.reduce((m, c, i) => picks.likes.includes(c.name) ? m | 1 << i : m, 0);
    // the group's day: a place is in if at least half of everyone said yes, out if nobody did
    function tally() {
        if (!group.length) return picks;  // group: true tells the planner to say "the group's yeses"
        const votes = [...group, mine()], likes = [], nopes = [];
        hand.forEach((c, i) => {
            const yes = votes.filter(m => m >> i & 1).length;
            if (yes * 2 >= votes.length) likes.push(c.name);
            else if (!yes) nopes.push(c.name);
        });
        return { likes, nopes, group: true };
    }
    const groupLink = () => `${shareLink()}&deck=1&v=${[...group, mine()].map(m => m.toString(16).padStart(3, '0')).join('.')}`;
    let hand = [], at = 0, picks = { likes: [], nopes: [] }, drag = null;
    const cardFor = (c, i) => {
        const card = el('article', 'swipe-card');
        card.dataset.i = i;
        card.append(el('div', 'sc-img', c.label), el('p', 'sc-kicker', `${c.label} · ${c.where}`), el('h3', null, c.name),
                    el('p', 'sc-note', [c.note, c.price ? `about $${c.price}` : 'free'].filter(Boolean).join(' · ')),
                    el('span', 'stamp yes', 'Yes'), el('span', 'stamp no', 'Nope'));
        return card;
    };
    const topCard = () => deckEl.querySelector(`.swipe-card[data-i="${at}"]`);
    function stack() {
        deckEl.querySelectorAll('.swipe-card').forEach(card => {
            const d = card.dataset.i - at;
            card.hidden = d > 2;
            card.style.zIndex = 10 - d;
            if (!card.classList.contains('gone')) card.style.transform = d ? `translateY(${d * 12}px) scale(${1 - d * 0.04})` : '';
        });
        const n = picks.likes.length, left = hand.length - at;
        countEl.textContent = left ? `${at + 1} / ${hand.length}` : 'done';
        yesBtn.disabled = noBtn.disabled = !left;
        doneBtn.disabled = group.length ? left > 0 : !at;
        doneBtn.textContent = group.length ? 'Plan our Saturday →'
            : n ? `Plan my Saturday with ${n} ${n === 1 ? 'yes' : 'yeses'} →` : 'Plan my Saturday →';
        shareBtn.hidden = !hand.length || left > 0;
        if (hand.length && !left) {
            const agreed = tally().likes.length;
            deckEl.replaceChildren(el('p', 'deck-note', group.length
                ? `The group agrees on ${agreed} ${agreed === 1 ? 'place' : 'places'}. Plan it, or pass it on.`
                : n ? `${n} ${n === 1 ? 'yes' : 'yeses'}. Plan it, or send it to the group chat.` : 'Nothing? Tough crowd. I’ll pick for you.'));
        }
    }
    function decide(yes) {
        const card = topCard();
        if (!card) return;
        (yes ? picks.likes : picks.nopes).push(hand[at].name);
        card.classList.add('gone');
        card.style.setProperty(yes ? '--yes' : '--no', 1);
        card.style.transform = `translateX(${yes ? 140 : -140}%) rotate(${yes ? 18 : -18}deg)`;
        card.style.opacity = 0;
        at++;
        setTimeout(() => card.remove(), 260);
        stack();
    }
    async function openSwipe() {
        hand = []; at = 0; picks = { likes: [], nopes: [] };
        noteEl.textContent = '';
        shareBtn.hidden = true;
        groupEl.hidden = !group.length;
        groupEl.textContent = group.length === 1 ? 'A friend already swiped this deck. Your turn.' : `${group.length} friends already swiped this deck. Your turn.`;
        deckEl.replaceChildren(el('p', 'deck-note', 'Shuffling the deck…'));
        countEl.textContent = '';
        yesBtn.disabled = noBtn.disabled = doneBtn.disabled = true;
        swipeBox.showModal();
        try { await boot(); } catch { deckEl.replaceChildren(el('p', 'deck-note', 'Python took a nap. Try again in a second.')); return; }
        const f = form.elements;
        hand = JSON.parse(deckFn(f.mood.value, f.rainy.checked, f.area.value, f.start_from.value, String(seed), f.start.value, f.end.value, 12, !!gameDay,
            thisSaturday().flatMap(e => e.closes || []).join(',')));
        if (hand.length < 3) {
            deckEl.replaceChildren(el('p', 'deck-note', f.mood.value === 'day-in' ? 'A day in doesn’t need swiping. Stay home, it’s allowed.' : 'Not much open in those hours. Try a longer day.'));
            return;
        }
        deckEl.replaceChildren(...hand.map(cardFor));
        stack();
    }
    deckEl.addEventListener('pointerdown', e => {
        const card = topCard();
        if (!card || !card.contains(e.target)) return;
        drag = { x: e.clientX, dx: 0, card };
        card.setPointerCapture(e.pointerId);
        card.style.transition = 'none';
    });
    deckEl.addEventListener('pointermove', e => {
        if (!drag) return;
        const dx = drag.dx = e.clientX - drag.x;
        drag.card.style.transform = `translateX(${dx}px) rotate(${dx / 18}deg)`;
        drag.card.style.setProperty('--yes', Math.max(0, Math.min(1, dx / 90)));
        drag.card.style.setProperty('--no', Math.max(0, Math.min(1, -dx / 90)));
    });
    const letGo = () => {
        if (!drag) return;
        const { card, dx } = drag;
        drag = null;
        card.style.transition = '';
        if (Math.abs(dx) > 90) return decide(dx > 0);
        card.style.transform = '';
        card.style.setProperty('--yes', 0);
        card.style.setProperty('--no', 0);
    };
    deckEl.addEventListener('pointerup', letGo);
    deckEl.addEventListener('pointercancel', letGo);
    yesBtn.addEventListener('click', () => decide(true));
    noBtn.addEventListener('click', () => decide(false));
    swipeBox.addEventListener('keydown', e => {
        if (e.key === 'ArrowRight') { e.preventDefault(); decide(true); }
        if (e.key === 'ArrowLeft') { e.preventDefault(); decide(false); }
    });
    swipeBox.addEventListener('click', e => { if (e.target === swipeBox) swipeBox.close(); });
    swipeBox.querySelector('.close-swipe').addEventListener('click', () => swipeBox.close());
    document.querySelector('.swipe-open').addEventListener('click', openSwipe);
    shareBtn.addEventListener('click', async () => {
        const url = groupLink();
        try {
            if (navigator.share) await navigator.share({ title: 'Saturday in Austin', text: 'Swipe on our Saturday. Right for yes, left for no.', url });
            else { await navigator.clipboard.writeText(url); noteEl.textContent = 'Link copied. Paste it in the group chat.'; }
        } catch { /* closing the share sheet is fine */ }
    });
    doneBtn.addEventListener('click', () => {
        swiped = tally();
        swipeBox.close();
        show('plan');
        run();
        if (innerWidth <= 1000) day.scrollIntoView({ behavior: 'smooth' });
    });

    // magazine sections: Plan, Austin, What's on, The Column, and About (The Editor, The Method, Code)
    const sections = [...document.querySelectorAll('.sections button, .subnav button')];
    const ABOUT = ['editor', 'method'];
    let lastAbout = 'editor';
    const show = name => {
        if (name === 'about') name = lastAbout;
        const about = ABOUT.includes(name);
        if (about) lastAbout = name;
        sections.forEach(b => b.setAttribute('aria-selected', String(b.dataset.screen === name || (about && b.dataset.screen === 'about'))));
        document.querySelector('.subnav').hidden = !about;
        document.querySelectorAll('.screen').forEach(sc => { sc.hidden = sc.id !== 'screen-' + name; });
        document.querySelector('header').classList.toggle('slim', name !== 'plan');
        if (name !== 'plan') document.querySelector('.see-day').classList.remove('show');
        if (name === 'method') setTimeout(() => document.getElementById('screen-method').dispatchEvent(new Event('refit')), 0);
        squeeze();
    };
    // short windows: the Editor and Austin pages tighten a notch at a time until they fit (no words cut)
    const NOTCHES = ['sq1', 'sq2', 'sq3'];
    function squeeze() {
        ['screen-editor', 'screen-austin'].forEach(id => {
            const sc = document.getElementById(id);
            sc.classList.remove(...NOTCHES);
            if (sc.hidden || innerWidth <= 1000) return;
            for (const n of NOTCHES) {
                if (sc.scrollHeight <= sc.clientHeight + 1) break;
                sc.classList.add(n);
            }
        });
    }
    window.addEventListener('resize', squeeze);
    document.fonts?.ready.then(squeeze);
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
            items = all.filter(([v]) => !q || exact || v.toLowerCase().includes(q));
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
            fit();
        }
        // the list stays inside the form: shorter when space is tight, flipped upward when there's more room above
        function fit() {
            const box = input.getBoundingClientRect(), frame = form.getBoundingClientRect();
            const floor = Math.min(frame.bottom, innerHeight), ceiling = Math.max(frame.top, 0);
            const below = floor - box.bottom - 8, above = box.top - ceiling - 8;
            const up = below < 180 && above > below;
            list.classList.toggle('up', up);
            list.style.maxHeight = `${Math.max(120, Math.min(264, up ? above : below))}px`;
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
    let group = [], openDeckOnLoad = false;  // Swipe with friends: everyone's yeses, one 12-bit mask each
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
        if (q.get('v')) group = q.get('v').split('.').map(h => parseInt(h, 16)).filter(n => Number.isFinite(n));
        openDeckOnLoad = q.has('deck');
    })();
    if (openDeckOnLoad) openSwipe();  // a friend sent their deck: straight to swiping

    // a long day scrolls inside the card: say so, until you reach the end
    const dayScroll = document.querySelector('.day .scroll'), more = document.querySelector('.day .more');
    const moreCue = () => { more.hidden = dayScroll.scrollHeight - dayScroll.scrollTop - dayScroll.clientHeight < 8; };
    dayScroll.addEventListener('scroll', moreCue, { passive: true });
    window.addEventListener('resize', moreCue);
    new MutationObserver(moreCue).observe(dayScroll, { childList: true, subtree: true });
    more.addEventListener('click', () => dayScroll.scrollBy({ top: dayScroll.clientHeight * 0.8, behavior: 'smooth' }));
    // on a phone the day is above the settings; once it scrolls away, a pill brings you back to it
    const seeDay = document.querySelector('.see-day');
    seeDay.addEventListener('click', () => day.scrollIntoView({ behavior: 'smooth' }));
    let dayVisible = true;
    const pill = () => {
        const show = !dayVisible && innerWidth <= 1000 && !document.getElementById('screen-plan').hidden && !!lastPlan;
        seeDay.classList.toggle('show', show);
        seeDay.setAttribute('aria-hidden', String(!show));
        seeDay.tabIndex = show ? 0 : -1;
    };
    new IntersectionObserver(([e]) => { dayVisible = e.isIntersecting; pill(); }, { threshold: 0.05 }).observe(day);

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
        const room = [0, 1, 2].map(() => Math.max(fit, natural));  // and every row is the same size
        for (let r = 0; r * 3 < card.length && r < 3; r++) {
            const extra = room[r] - card[r * 3].getBoundingClientRect().height;
            if (extra > 0) tracks[r * per] += extra;
        }
        cards.style.gridTemplateRows = tracks.map((x, i) => i % per === 0 ? x + 'px' : 'auto').join(' ');  // only the picture rows are pinned
    }
    const refit = new ResizeObserver(() => fillCards());
    [method, method.querySelector('.numbers')].forEach(e => e && refit.observe(e));
    window.addEventListener('resize', fillCards);
    method.addEventListener('refit', fillCards);
    document.fonts?.ready.then(fillCards);

    // the editor's own ideal Saturday
    const ideal = document.getElementById('ideal');
    document.querySelector('.ideal-open').addEventListener('click', () => ideal.showModal());
    ideal.querySelector('.close-ideal').addEventListener('click', () => ideal.close());
    ideal.addEventListener('click', e => { if (e.target === ideal) ideal.close(); });

    // ------------------------------------------------------------ Austin, right now (free, no key)
    const WEATHER = { 0: 'clear', 1: 'mostly clear', 2: 'partly cloudy', 3: 'cloudy', 45: 'foggy', 48: 'foggy',
                      51: 'drizzle', 53: 'drizzle', 55: 'drizzle', 61: 'rain', 63: 'rain', 65: 'heavy rain',
                      80: 'showers', 81: 'showers', 82: 'heavy showers', 95: 'thunderstorms', 96: 'thunderstorms', 99: 'thunderstorms' };
    const RAINY = new Set([51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82, 95, 96, 99]);
    const wx = (key, text) => document.querySelectorAll(`[data-wx="${key}"]`).forEach(e => { e.textContent = text; });
    const clockOf = iso => { const [h, m] = iso.split('T')[1].split(':').map(Number); return `${h % 12 || 12}:${String(m).padStart(2, '0')}`; };
    const untilSaturday = (6 - new Date().getDay() + 7) % 7;
    wx('days-n', untilSaturday === 0 ? 'Today' : String(untilSaturday));
    wx('days-label', untilSaturday === 0 ? 'is Saturday' : untilSaturday === 1 ? 'day to Saturday' : 'days to Saturday');
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
            wx('src', `Weather: Open-Meteo, ${now} CT`);
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
                body.textContent = 'See its places and drives.';
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
                // ESPN puts a placeholder time on games whose kickoff isn't set yet: keep the date, drop the time
                const timed = c.timeValid !== false, date = new Date(e.date);
                const day = timed ? date.toLocaleDateString('en-CA', { timeZone: 'America/Chicago' }) : e.date.slice(0, 10);
                return { done: c.status.type.completed, date, day, timed, home: us.homeAway === 'home', them: them.team.shortDisplayName,
                         us: us.score?.displayValue, they: them.score?.displayValue, won: us.winner,
                         sec: SEC.has(them.team.id) && e.seasonType?.type === 2 };
            });
            // game day: a home game on the coming Saturday, Austin time
            const now = new Date(new Date().toLocaleString('en-US', { timeZone: 'America/Chicago' }));
            const sat = new Date(now); sat.setDate(now.getDate() + (6 - now.getDay() + 7) % 7);
            const satDay = `${sat.getFullYear()}-${String(sat.getMonth() + 1).padStart(2, '0')}-${String(sat.getDate()).padStart(2, '0')}`;
            const home = games.find(g => g.home && !g.done && g.day === satDay);
            if (home && !gameDay) {
                gameDay = { them: home.them, time: home.timed ? home.date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago' }) : '' };
                run();
            }
            const away = games.find(g => !g.home && !g.done && g.day === satDay);
            if (away && !awayDay) { awayDay = { them: away.them }; run(); }
            longhorns = games.filter(g => !g.done);
            drawCalendar();
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

    // What's on: the big Austin dates, plus every Longhorns home game from ESPN
    // closes: places the city takes over that Saturday; heads: what the Plan page says about it
    const EVENTS = [
        { from: '2026-10-02', to: '2026-10-04', name: 'ACL Fest, Weekend One', where: 'Zilker Park', link: 'https://www.aclfestival.com',
          note: 'Charli xcx, Lorde, RÜFÜS DU SOL, Twenty One Pilots, The xx, and Skrillex, this weekend only.',
          closes: ['Zilker Park'], heads: 'Zilker Park is the festival, so I kept you out of it. Barton Springs Pool stays open through its south gate.' },
        { from: '2026-10-07', to: '2026-10-08', name: 'Kacey Musgraves', where: 'Moody Center', link: 'https://moodycenteratx.com' },
        { from: '2026-10-09', to: '2026-10-11', name: 'ACL Fest, Weekend Two', where: 'Zilker Park', link: 'https://www.aclfestival.com',
          note: 'The same lineup, with Kings of Leon instead of Skrillex.',
          closes: ['Zilker Park'], heads: 'Zilker Park is the festival, so I kept you out of it. Barton Springs Pool stays open through its south gate.' },
        { from: '2026-10-13', name: 'Bryson Tiller', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'With Majid Jordan and Ty Dolla $ign.' },
        { from: '2026-10-15', name: 'Gorillaz', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'The cartoon band, in person.' },
        { from: '2026-10-16', name: 'Phoebe Bridgers', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'Bring tissues.' },
        { from: '2026-10-18', name: 'Weezer', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'Say it ain’t so: they’re here.' },
        { from: '2026-10-23', to: '2026-10-25', name: 'Formula 1 U.S. Grand Prix', where: 'Circuit of the Americas', link: 'https://www.circuitoftheamericas.com',
          note: 'Maroon 5 on Friday, Post Malone on Saturday, Alesso after Sunday’s race.',
          heads: 'The city is full of F1 fans: expect traffic and pricier Ubers, especially toward the east side.' },
        { from: '2026-10-24', name: 'Viva la Vida Fest', where: '4th and Congress', link: 'https://mexic-artemuseum.org',
          note: 'Mexic-Arte’s Día de los Muertos parade and festival, downtown.', heads: 'Viva la Vida is downtown today: the parade and festival are on 4th and Congress.' },
        { from: '2026-10-26', to: '2026-10-27', name: 'Dave Chappelle', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'Two nights. Your phone gets locked in a pouch.' },
        { from: '2026-10-29', to: '2026-11-05', name: 'Austin Film Festival', where: 'Around town', link: 'https://austinfilmfestival.com' },
        { from: '2026-10-31', name: 'Halloween, on a Saturday', where: 'Sixth Street', note: 'Costumes required. Patience recommended.',
          heads: 'Halloween on a Saturday: Sixth Street will be packed, so costume accordingly.' },
        { from: '2026-11-03', name: 'Doja Cat', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'A Tuesday worth skipping homework for.' },
        { from: '2026-11-06', name: 'John Summit', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'House music, arena-sized.' },
        { from: '2026-11-10', name: 'KATSEYE', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'The Wildworld Tour.' },
        { from: '2026-11-13', to: '2026-11-15', name: 'Seismic 9.0', where: 'The Concourse Project', link: 'https://concourseproject.com',
          note: 'Indoor and outdoor stages of house, techno and bass at Austin’s electronic music hall.' },
        { from: '2026-11-13', name: 'Jonas Brothers', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'The Burning Up Tour All Over Again.' },
        { from: '2026-11-14', to: '2026-11-15', name: 'Texas Book Festival', where: 'Around the Capitol', link: 'https://texasbookfestival.org',
          heads: 'The Texas Book Festival is around the Capitol this weekend.' },
        { from: '2026-11-29', to: '2027-01-01', name: 'Zilker Holiday Tree', where: 'Zilker Park', note: 'The lights come on at the ceremony on the 29th.' },
        { from: '2026-12-01', name: 'Trail of Lights', where: 'Zilker Park', tba: 'Dec', note: 'Every December. This year’s dates come out in October.' },
        { from: '2026-12-11', name: 'Tyla', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'Bring your dancing shoes.' },
        { from: '2026-12-12', name: 'Billy Strings', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'Bluegrass jams that run long, in the good way.' },
        { from: '2026-12-31', name: 'New Year’s Eve', where: 'Vic Mathias Shores', note: 'The city’s party on the water. Fireworks over Lady Bird Lake at midnight.' },
        { from: '2027-02-04', name: 'Andrea Bocelli', where: 'Moody Center', link: 'https://moodycenteratx.com', note: 'Bring a grandparent.' },
        { from: '2027-02-14', name: 'Austin Marathon', where: 'Downtown', link: 'https://youraustinmarathon.com', note: '26.2 miles on Valentine’s Day. Cheering counts as cardio.' },
        { from: '2027-03-12', to: '2027-03-27', name: 'Rodeo Austin', where: 'Expo Center', link: 'https://www.rodeoaustin.com', note: 'Rodeo, carnival rides and turkey legs. It overlaps SXSW.' },
        { from: '2027-03-13', to: '2027-03-21', name: 'SXSW', where: 'Downtown', link: 'https://www.sxsw.com',
          note: 'SXSW EDU March 13–16, then music, film, tech and comedy March 15–21.', heads: 'SXSW week: downtown is packed and badges are everywhere.' },
    ];
    // the traditions that come back on the same schedule every year
    const EVERY_YEAR = [
        { when: 'Every week', name: 'The Concourse Project', where: '8509 Burleson Rd', note: 'Austin’s electronic music hall. DJs most weekends, until late.', link: 'https://concourseproject.com' },
        { when: 'Thursdays', name: 'College night at Mavs', where: 'Mavericks Dance Hall, Buda', note: 'Two-stepping, five bars and a big patio, 25 minutes south. Check the age rule first.', link: 'https://buda.mavericksdancehall.com' },
        { when: 'Game days', name: 'Victory Lap', where: '504 W 24th St', note: 'The Longhorns sports bar by campus. Opens early on game days; trivia every Tuesday.' },
        { when: 'Mar–Oct', name: 'The bats', where: 'Congress Avenue Bridge', note: 'About 1.5 million of them fly out at sunset.' },
        { when: 'Spring', name: 'ABC Kite Fest', where: 'Zilker Park', note: 'A Saturday in late March or April. The sky fills with kites.' },
        { when: 'Late Apr', name: 'Eeyore’s Birthday Party', where: 'Pease Park', note: 'Usually the last Saturday in April, since 1963. Costumes, drum circles, very Austin.' },
        { when: 'Jul 4', name: 'Symphony and fireworks', where: 'Vic Mathias Shores', note: 'The Austin Symphony plays, then fireworks over the skyline. Free.' },
        { when: 'Summer', name: 'Blues on the Green', where: 'ACL Radio', note: 'Free outdoor concerts on summer evenings.' },
        { when: 'Sep', name: 'Levitation', where: 'Venues around town', note: 'Psych rock, punk and more, over four days.' },
    ];
    let longhorns = [];
    const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
    const day0 = iso => { const [y, m, d] = iso.split('-').map(Number); return new Date(y, m - 1, d); };
    // What's on: a real month, one at a time; today circled; the month's events in the sidebar
    const MONTHS = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December'];
    const ymd = d => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`;
    let calMonth = (() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); })();
    let calPick = null;      // a day someone tapped: the sidebar shows just that day
    let calSide = 'month';   // or 'yearly'
    const kindOf = e => e.where === 'DKR' || e.where === 'Watch at Victory Lap' ? 'game' : e.closes || /Fest|SXSW|Grand Prix|Festival|Seismic/.test(e.name) ? 'big' : 'other';
    function allEvents() {
        const kickoff = g => g.timed ? `Kickoff ${g.date.toLocaleTimeString('en-US', { hour: 'numeric', minute: '2-digit', timeZone: 'America/Chicago' })}.` : 'Kickoff time TBA.';
        const games = longhorns.map(g => g.home
            ? { from: g.day, name: `Texas vs. ${g.them}`, where: 'DKR', link: 'https://texassports.com/sports/football/schedule', note: `${kickoff(g)} Hook ’em.` }
            : { from: g.day, name: `Texas at ${g.them}`, where: 'Watch at Victory Lap', link: 'https://texassports.com/sports/football/schedule', note: `${kickoff(g)} Away game: the TVs on 24th.` });
        return [...EVENTS, ...games].sort((a, b) => day0(a.from) - day0(b.from));
    }
    function eventRow(e) {
        const sat = new Date(); sat.setHours(0, 0, 0, 0); sat.setDate(sat.getDate() + (6 - sat.getDay() + 7) % 7);
        const from = day0(e.from), to = day0(e.to || e.from), now = !e.tba && from <= sat && sat <= to;
        const row = el('article', 'ev ' + kindOf(e) + (now ? ' now' : ''));
        const date = el('div', 'ev-date', e.tba || String(from.getDate()));
        date.appendChild(el('small', null, e.tba ? 'dates tba' : e.to && e.to !== e.from
            ? `to ${to.getMonth() !== from.getMonth() ? MON[to.getMonth()] + ' ' : ''}${to.getDate()}` : from.toLocaleDateString('en-US', { weekday: 'short' })));
        const body = el('div'), title = el('h4');
        if (e.link) title.appendChild(Object.assign(el('a', null, e.name), { href: e.link, target: '_blank', rel: 'noopener' }));
        else title.textContent = e.name;
        if (now) title.appendChild(el('span', 'tag', 'This Saturday'));
        const where = el('p', 'ev-where', e.where);
        body.append(title, where);
        if (e.note) body.appendChild(el('p', null, e.note));
        if (!e.tba) {
            const add = el('button', 'ev-add', '+ Calendar');
            add.type = 'button';
            const after = new Date(to); after.setDate(after.getDate() + 1);  // all-day events end the morning after
            add.addEventListener('click', () => saveIcs(e.name.replace(/[^a-z0-9]+/gi, '-').toLowerCase(),
                [{ allDay: true, start: ymd(from), end: ymd(after), title: e.name, where: e.where, notes: e.note, url: e.link }]));
            where.appendChild(add);
        }
        row.append(date, body);
        return row;
    }
    function drawCalendar() {
        const grid = document.querySelector('[data-cal-grid]');
        if (!grid) return;
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const y = calMonth.getFullYear(), m = calMonth.getMonth();
        document.querySelector('[data-cal-title]').replaceChildren(MONTHS[m] + ' ', el('em', null, String(y)));
        const events = allEvents().filter(e => !e.tba);
        const on = d => events.filter(e => day0(e.from) <= d && d <= day0(e.to || e.from));
        const first = new Date(y, m, 1), start = new Date(y, m, 1 - first.getDay());
        const weeks = Math.ceil((first.getDay() + new Date(y, m + 1, 0).getDate()) / 7);
        grid.style.setProperty('--weeks', weeks);
        const cells = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map(d => el('div', 'cal-dow' + (d === 'Sat' ? ' sat' : ''), d));
        for (let i = 0; i < weeks * 7; i++) {
            const d = new Date(start); d.setDate(start.getDate() + i);
            const cell = el('button', 'cal-day');
            cell.type = 'button';
            if (d.getMonth() !== m) cell.classList.add('out');
            if (d.getDay() === 6) cell.classList.add('sat');
            if (+d === +today) cell.classList.add('today');
            if (calPick && +d === +calPick) cell.classList.add('picked');
            cell.appendChild(el('span', 'num', String(d.getDate())));
            const list = on(d);
            list.slice(0, 2).forEach(e => cell.appendChild(el('span', 'chip ' + kindOf(e), e.name)));
            if (list.length > 2) cell.appendChild(el('span', 'more-ev', `+${list.length - 2} more`));
            cell.setAttribute('aria-label', `${d.toDateString()}${list.length ? ': ' + list.map(e => e.name).join(', ') : ''}`);
            cell.addEventListener('click', () => { calPick = calPick && +calPick === +d ? null : d; calSide = 'month'; drawCalendar(); });
            cells.push(cell);
        }
        grid.replaceChildren(...cells);
        // the sidebar: a picked day, this month's events, or the yearly traditions
        document.querySelectorAll('[data-cal-tab]').forEach(t => t.setAttribute('aria-selected', String(t.dataset.calTab === calSide)));
        const side = document.querySelector('[data-cal-list]');
        if (calSide === 'yearly') {
            side.replaceChildren(...EVERY_YEAR.map(e => {
                const row = el('article', 'ev yearly'), body = el('div'), title = el('h4');
                if (e.link) title.appendChild(Object.assign(el('a', null, e.name), { href: e.link, target: '_blank', rel: 'noopener' }));
                else title.textContent = e.name;
                body.append(title, el('p', 'ev-where', e.where), el('p', null, e.note));
                row.append(el('div', 'ev-when', e.when), body);
                return row;
            }));
            return;
        }
        const monthEnd = new Date(y, m + 1, 0), thisMonth = y === today.getFullYear() && m === today.getMonth();
        // this month: what's coming up from today; any other month: that month's highlights
        const shown = calPick ? on(calPick) : thisMonth ? allEvents().filter(e => day0(e.to || e.from) >= today).slice(0, 8)
            : allEvents().filter(e => (e.tba ? day0(e.from).getMonth() === m && day0(e.from).getFullYear() === y
                : day0(e.from) <= monthEnd && day0(e.to || e.from) >= first));
        const head = el('p', 'cal-side-head', calPick ? calPick.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
            : thisMonth ? 'Coming up' : `${MONTHS[m]} highlights`);
        side.replaceChildren(head, ...(shown.length ? shown.map(eventRow) : [el('p', 'cal-empty', calPick ? 'Nothing big that day. A normal Saturday, then.' : 'A quiet month. More soon.')]));
    }
    document.querySelectorAll('[data-cal-go]').forEach(b => b.addEventListener('click', () => {
        const go = b.dataset.calGo;
        if (go === 'today') { const d = new Date(); calMonth = new Date(d.getFullYear(), d.getMonth(), 1); }
        else calMonth = new Date(calMonth.getFullYear(), calMonth.getMonth() + Number(go), 1);
        calPick = null;
        drawCalendar();
    }));
    document.querySelectorAll('[data-cal-tab]').forEach(b => b.addEventListener('click', () => { calSide = b.dataset.calTab; calPick = null; drawCalendar(); }));
    // what's happening this Saturday, for the Plan page and the planner
    function thisSaturday() {
        const today = new Date(); today.setHours(0, 0, 0, 0);
        const sat = new Date(today); sat.setDate(today.getDate() + (6 - today.getDay() + 7) % 7);
        return EVENTS.filter(e => !e.tba && day0(e.from) <= sat && sat <= day0(e.to || e.from));
    }
    drawCalendar();
    // preview a game day without waiting for one: ?game=Florida
    const preview = new URLSearchParams(location.search).get('game');
    if (preview) gameDay = { them: preview, time: '' };
    const previewAway = new URLSearchParams(location.search).get('away');  // ?away=Oklahoma
    if (previewAway) awayDay = { them: previewAway };

    // The Column: tap a cover to read it
    const storyBox = document.getElementById('story'), storyBody = storyBox.querySelector('.story-body');
    const openStory = key => {
        const tpl = document.getElementById('story-' + key);
        if (!tpl) return;
        storyBody.replaceChildren(tpl.content.cloneNode(true));
        storyBox.showModal();
        storyBox.querySelector('.story-paper').scrollTop = 0;
    };
    document.querySelectorAll('.pin[data-story]').forEach(c => {
        c.addEventListener('click', () => openStory(c.dataset.story));
        c.addEventListener('keydown', e => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openStory(c.dataset.story); } });
    });
    storyBox.querySelector('.close-story').addEventListener('click', () => storyBox.close());
    // shareable links: #four-days opens the four-day plan (and the header link does the same)
    const HASHES = { 'four-days': 'four', 'make-something': 'make', 'nightlife': 'bars', 'live-music': 'music', 'austin-decoded': 'symbols',
                     'vegan-edit': 'vegan', 'neighborhoods': 'hoods', 'college-town': 'college', 'worth-a-follow': 'follow',
                     'texas-football': 'football', 'austin-history': 'history',
                     'best-coffee': 'coffee', 'best-mexican': 'mexican', 'best-indian': 'indian', 'capmetro': 'bus',
                     'best-brunch': 'brunch', 'study-spots': 'study', 'first-dates': 'date', 'zero-dollar-saturday': 'free', 'cowboy-boots': 'boots', 'college-night': 'thursday', 'austin-words': 'words' };
    document.querySelectorAll('[data-open-story]').forEach(a => a.addEventListener('click', e => {
        e.preventDefault();
        history.replaceState(null, '', '#' + Object.keys(HASHES).find(k => HASHES[k] === a.dataset.openStory));
        openStory(a.dataset.openStory);
    }));
    storyBox.addEventListener('close', () => { if (location.hash) history.replaceState(null, '', location.pathname + location.search); });
    if (HASHES[location.hash.slice(1)]) openStory(HASHES[location.hash.slice(1)]);
    storyBox.addEventListener('click', e => {
        if (e.target === storyBox) storyBox.close();
        const travel = e.target.closest('[data-plan-travel]');
        if (travel) {  // the bus article: same day, by bus
            storyBox.close();
            form.elements.travel.value = travel.dataset.planTravel;
            show('plan');
            form.dispatchEvent(new Event('change'));
        }
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


    // Add to calendar: an .ics file that Apple Calendar, Google Calendar and Outlook all open
    const icsEscape = t => String(t).replace(/[\\,;]/g, m => '\\' + m).replace(/\n/g, '\\n');
    const stamp = d => `${d.getFullYear()}${String(d.getMonth() + 1).padStart(2, '0')}${String(d.getDate()).padStart(2, '0')}`
        + `T${String(d.getHours()).padStart(2, '0')}${String(d.getMinutes()).padStart(2, '0')}00`;
    function saveIcs(name, events) {
        const now = stamp(new Date());
        const lines = ['BEGIN:VCALENDAR', 'VERSION:2.0', 'PRODID:-//Saturday in Austin//EN', 'CALSCALE:GREGORIAN'];
        events.forEach((e, i) => lines.push('BEGIN:VEVENT', `UID:${now}-${i}-${Math.random().toString(36).slice(2)}@saturday-in-austin`, `DTSTAMP:${now}`,
            e.allDay ? `DTSTART;VALUE=DATE:${e.start}` : `DTSTART:${stamp(e.start)}`, e.allDay ? `DTEND;VALUE=DATE:${e.end}` : `DTEND:${stamp(e.end)}`,
            `SUMMARY:${icsEscape(e.title)}`, ...(e.where ? [`LOCATION:${icsEscape(e.where)}`] : []),
            ...(e.notes ? [`DESCRIPTION:${icsEscape(e.notes)}`] : []), ...(e.url ? [`URL:${e.url}`] : []), 'END:VEVENT'));
        lines.push('END:VCALENDAR');
        const a = Object.assign(document.createElement('a'), { href: URL.createObjectURL(new Blob([lines.join('\r\n')], { type: 'text/calendar' })), download: name + '.ics' });
        document.body.append(a); a.click(); a.remove();
    }
    const comingSaturday = () => { const d = new Date(); d.setHours(0, 0, 0, 0); d.setDate(d.getDate() + (6 - d.getDay() + 7) % 7); return d; };
    document.querySelector('.cal-it').addEventListener('click', () => {
        const plan = lastPlan, day = comingSaturday();
        let last = -1, extra = 0;
        const events = plan.stops.filter(s => s.type !== 'free').map(s => {
            const [t, ampm] = s.time.split(' '), [h, m] = t.split(':').map(Number);
            let at = (h % 12 + (ampm === 'PM' ? 12 : 0)) * 60 + m;
            if (at < last) extra += 24 * 60;  // past midnight: it's Sunday now
            last = at;
            const start = new Date(day.getTime() + (at + extra) * 60000), end = new Date(start.getTime() + s.minutes * 60000);
            return s.type === 'reset'
                ? { start, end, title: `Home: ${s.note}` }
                : { start, end, title: s.name, where: `${s.name.replace(/[()]/g, '')}, Austin, TX`, notes: [s.label, s.note, s.why].filter(Boolean).join(' · '),
                    url: directions(s.name, plan.mode) };
        });
        saveIcs(`saturday-${plan.seed}`, events);
    });

    // PDFs, set like the page: gold kicker, Bodoni-ish headline, typewriter dek, burnt-orange italic heads
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
            const INK = [10, 10, 10], PINK = [154, 70, 0], GOLD = [191, 87, 0], GREY = [110, 110, 110];
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

    // a first visit shows a baked Saturday right away; Python replans the very same day once it's awake
    if (!form.dataset.shared && window.SAMPLES?.length && !thisSaturday().some(e => e.closes)) {
        const sample = window.SAMPLES[Math.floor(Math.random() * window.SAMPLES.length)];
        seed = sample.seed;
        draw(sample);
    }
    run();
})();
