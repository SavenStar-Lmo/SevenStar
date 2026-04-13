/**
 * SevenStar Limo & Chauffeur — booking_form.js
 * Booking form interactions:
 *   - Vehicle card selection + hidden input sync
 *   - Passenger & bag dropdowns (built from data-* on cards)
 *   - Auto-upgrade vehicle when passenger/bag count exceeds capacity
 *   - Toggle switch add-ons (baby seat, return ride)
 *   - Baby seat panel: count selector + dynamic age input fields
 *     with client-side validation (≤ 3 years / 36 months)
 *   - Google Places autocomplete (pickup, destination, extra stop)
 *   - Date min = today
 *   - Submit loading state
 *
 * Depends on globals injected by booking_form.html:
 *   BF_TYPE, BF_RATES, BF_IS_HOURLY,
 *   BF_BABY_SEAT_ON, BF_NUM_BABIES, BF_BABY_AGES_PREFILL
 */

/* ── Init ───────────────────────────────────────────────────── */
(function bfInit() {
    'use strict';

    if (!window.BF_RATES || !BF_RATES.length) return;

    var vehicleInput = document.getElementById('bfVehicleInput');
    if (vehicleInput && !vehicleInput.value && BF_RATES.length) {
        vehicleInput.value = BF_RATES[0].name;
    }
    if (vehicleInput) {
        window.bfCurrent = vehicleInput.value || BF_RATES[0].name;
    }

    bfBuildDropdowns();

    var dateEl = document.getElementById('bfDate');
    if (dateEl) {
        var today = new Date().toISOString().split('T')[0];
        dateEl.min = today;
        if (!dateEl.value) dateEl.value = today;
    }

    // Restore baby panel state after a validation error redirect
    if (window.BF_BABY_SEAT_ON && window.BF_NUM_BABIES > 0) {
        // The panel is already visible (Django rendered it so).
        // Rebuild age fields and restore prefill values.
        bfRenderBabyAges(window.BF_NUM_BABIES, _parsePrefillAges(window.BF_BABY_AGES_PREFILL));
    }
})();

/* ── Parse comma-separated pre-fill ages from server ─────── */
function _parsePrefillAges(str) {
    if (!str) return [];
    return str.split(',').map(function (s) { return s.trim(); });
}

/* ── Vehicle card selection ─────────────────────────────────── */
window.bfPick = function (card) {
    document.querySelectorAll('.bf__vc').forEach(function (c) { c.classList.remove('sel'); });
    card.classList.add('sel');
    window.bfCurrent = card.dataset.name;
    var inp = document.getElementById('bfVehicleInput');
    if (inp) inp.value = window.bfCurrent;
    bfBuildDropdowns();
};

/* ── Get current rate object ─────────────────────────────────── */
function bfCurrentRate() {
    for (var i = 0; i < BF_RATES.length; i++) {
        if (BF_RATES[i].name === window.bfCurrent) return BF_RATES[i];
    }
    return BF_RATES[0];
}

/* ── Passenger & bag dropdowns ──────────────────────────────── */
function bfBuildDropdowns() {
    var rate = bfCurrentRate();
    if (!rate) return;

    var pSel = document.getElementById('bfPassSel');
    var bSel = document.getElementById('bfBagSel');
    if (!pSel || !bSel) return;

    var curP = parseInt(pSel.value, 10) || window.BF_DEFAULT_PASS || 2;
    var curB = parseInt(bSel.value, 10) || window.BF_DEFAULT_BAGS || 2;

    pSel.innerHTML = '';
    bSel.innerHTML = '';

    for (var p = 1; p <= rate.maxP; p++) {
        var op = document.createElement('option');
        op.value = p;
        op.textContent = p === 1 ? '1 Passenger' : p + ' Passengers';
        if (p === Math.min(curP, rate.maxP)) op.selected = true;
        pSel.appendChild(op);
    }
    for (var b = 0; b <= rate.maxB; b++) {
        var ob = document.createElement('option');
        ob.value = b;
        ob.textContent = b === 0 ? '0 Bags' : b === 1 ? '1 Bag' : b + ' Bags';
        if (b === Math.min(curB, rate.maxB)) ob.selected = true;
        bSel.appendChild(ob);
    }
}

window.bfPassChange = function () {
    var p       = parseInt(document.getElementById('bfPassSel').value, 10);
    var curIdx  = BF_RATES.findIndex(function (r) { return r.name === window.bfCurrent; });
    var needed  = BF_RATES.find(function (r) { return r.maxP >= p; });
    if (needed && BF_RATES.indexOf(needed) > curIdx) {
        bfUpgrade(needed, p + ' passengers require a larger vehicle.');
    }
};

window.bfBagChange = function () {
    var b       = parseInt(document.getElementById('bfBagSel').value, 10);
    var curIdx  = BF_RATES.findIndex(function (r) { return r.name === window.bfCurrent; });
    var needed  = BF_RATES.find(function (r) { return r.maxB >= b; });
    if (needed && BF_RATES.indexOf(needed) > curIdx) {
        bfUpgrade(needed, b + ' bags require a larger vehicle.');
    }
};

function bfUpgrade(rate, msg) {
    document.querySelectorAll('.bf__vc').forEach(function (c) {
        c.classList.toggle('sel', c.dataset.name === rate.name);
    });
    window.bfCurrent = rate.name;
    var inp = document.getElementById('bfVehicleInput');
    if (inp) inp.value = window.bfCurrent;

    var noteEl = document.getElementById('bfUpNote');
    var textEl = document.getElementById('bfUpText');
    if (textEl) textEl.textContent = msg;
    if (noteEl) {
        noteEl.classList.add('show');
        setTimeout(function () { noteEl.classList.remove('show'); }, 4000);
    }
    bfBuildDropdowns();
}

/* ── Generic toggle switch ───────────────────────────────────── */
window.bfToggle = function (divId, cbId) {
    var div = document.getElementById(divId);
    var cb  = document.getElementById(cbId);
    if (!div || !cb) return;
    div.classList.toggle('on');
    cb.checked = div.classList.contains('on');
    div.setAttribute('aria-checked', cb.checked ? 'true' : 'false');
};

/* ── Baby seat toggle (extended — also controls panel) ──────── */
window.bfToggleBabySeat = function () {
    var toggle = document.getElementById('bfBabySeatToggle');
    var cb     = document.getElementById('bfBabySeatCb');
    var panel  = document.getElementById('bfBabyPanel');
    if (!toggle || !cb || !panel) return;

    toggle.classList.toggle('on');
    cb.checked = toggle.classList.contains('on');
    toggle.setAttribute('aria-checked', cb.checked ? 'true' : 'false');

    if (cb.checked) {
        panel.style.display = 'block';
    } else {
        panel.style.display = 'none';
        // Reset state when toggled off
        var numSel = document.getElementById('bfNumBabies');
        if (numSel) numSel.value = '0';
        bfRenderBabyAges(0, []);
    }
};

/* ── Baby count changed → rebuild age fields ────────────────── */
window.bfRenderBabyAges = function (n, prefill) {
    // Allow calling as bfRenderBabyAges() from the onchange attr (reads select value)
    if (n === undefined) {
        var sel = document.getElementById('bfNumBabies');
        n = sel ? parseInt(sel.value, 10) || 0 : 0;
    }
    prefill = prefill || [];

    var col = document.getElementById('bfBabyAgesCol');
    if (!col) return;

    col.innerHTML = '';

    for (var i = 0; i < n; i++) {
        (function (idx) {
            var row = document.createElement('div');
            row.className = 'bf__baby-age-row';

            var label = document.createElement('label');
            label.htmlFor = 'bfBabyAge' + idx;
            label.innerHTML =
                'Baby ' + (idx + 1) + ' Age ' +
                '<span class="bf__req" aria-hidden="true">*</span>';

            var input = document.createElement('input');
            input.type        = 'text';
            input.id          = 'bfBabyAge' + idx;
            input.name        = 'baby_age_' + idx;
            input.placeholder = 'e.g. 7 months or 2 years';
            input.required    = true;
            input.autocomplete = 'off';
            input.setAttribute('aria-required', 'true');
            input.setAttribute('aria-describedby', 'bfBabyAgeErr' + idx);

            // Restore pre-fill if available (server sent form back after error)
            if (prefill[idx]) {
                input.value = prefill[idx];
            }

            var errMsg = document.createElement('span');
            errMsg.className = 'bf__baby-age-errmsg';
            errMsg.id        = 'bfBabyAgeErr' + idx;
            errMsg.setAttribute('role', 'alert');
            errMsg.innerHTML =
                '<svg width="11" height="11" viewBox="0 0 12 12" fill="none" aria-hidden="true">' +
                '<circle cx="6" cy="6" r="5" stroke="#b83232" stroke-width="1.2"/>' +
                '<path d="M6 3.5v3M6 8v.5" stroke="#b83232" stroke-width="1.2" stroke-linecap="round"/>' +
                '</svg>' +
                'Age must be 3 years (36 months) or under.';

            // Live validation on input
            input.addEventListener('input', function () {
                _validateAgeField(input, errMsg);
            });
            // Also validate on blur for UX
            input.addEventListener('blur', function () {
                _validateAgeField(input, errMsg);
            });

            row.appendChild(label);
            row.appendChild(input);
            row.appendChild(errMsg);
            col.appendChild(row);

            // Validate immediately if pre-filled
            if (prefill[idx]) {
                _validateAgeField(input, errMsg);
            }
        })(i);
    }
};

/* ── Age field client-side validation ───────────────────────── */
function _validateAgeField(input, errEl) {
    var val     = input.value.trim().toLowerCase();
    var invalid = false;

    if (val.length > 0) {
        if (val.indexOf('month') !== -1) {
            var m = parseInt(val, 10);
            if (isNaN(m) || m <= 0) {
                invalid = true; // e.g. "months" with no number
            } else if (m > 36) {
                invalid = true;
            }
        } else if (val.indexOf('year') !== -1) {
            var y = parseInt(val, 10);
            if (isNaN(y) || y < 0) {
                invalid = true;
            } else if (y > 3) {
                invalid = true;
            }
        } else if (val.length > 0) {
            // Has content but no recognised unit — flag as invalid format
            // (server will catch this too, but give immediate feedback)
            invalid = true;
            // Override error message for format issue
            var spans = errEl.querySelectorAll('svg ~ *');
            // Just keep the generic "must be 3 years or under" message —
            // server will return a clear format error anyway.
        }
    }

    if (invalid) {
        input.classList.add('bf__age-err');
        errEl.classList.add('show');
        input.setCustomValidity('Age must be 3 years (36 months) or under.');
    } else {
        input.classList.remove('bf__age-err');
        errEl.classList.remove('show');
        input.setCustomValidity('');
    }

    return !invalid;
}

/* ── Pre-submit: validate all visible age fields ─────────────── */
function _validateAllAgeFields() {
    var panel = document.getElementById('bfBabyPanel');
    if (!panel || panel.style.display === 'none') return true;

    var cb = document.getElementById('bfBabySeatCb');
    if (!cb || !cb.checked) return true;

    var numSel = document.getElementById('bfNumBabies');
    var n = numSel ? parseInt(numSel.value, 10) || 0 : 0;

    if (n === 0) {
        // No count selected — block submit with a custom message
        if (numSel) {
            numSel.setCustomValidity('Please select how many babies require a seat.');
            numSel.reportValidity();
            numSel.setCustomValidity(''); // reset so it doesn't block again
        }
        return false;
    }

    var allOk = true;
    for (var i = 0; i < n; i++) {
        var inp    = document.getElementById('bfBabyAge' + i);
        var errEl  = document.getElementById('bfBabyAgeErr' + i);
        if (!inp) { allOk = false; continue; }
        var ok = _validateAgeField(inp, errEl);
        if (!ok) allOk = false;
        // Also check not empty
        if (!inp.value.trim()) {
            inp.setCustomValidity('Please enter the age for baby ' + (i + 1) + '.');
            inp.classList.add('bf__age-err');
            allOk = false;
        }
    }

    if (!allOk) {
        // Scroll to first invalid age field
        var firstErr = document.querySelector('.bf__age-err');
        if (firstErr) firstErr.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }

    return allOk;
}

/* ── Google Places autocomplete ─────────────────────────────── */
function bfSetupAC(inputEl, listEl) {
    if (!inputEl || !listEl) return;
    var svc = null, items = [], hi = -1;

    function getService() {
        if (!svc && window.google && window.google.maps && window.google.maps.places) {
            svc = new window.google.maps.places.AutocompleteService();
        }
        return svc;
    }

    inputEl.addEventListener('input', function () {
        var v = inputEl.value.trim();
        if (v.length < 3) { listEl.classList.remove('open'); return; }
        var s = getService();
        if (!s) return;
        s.getPlacePredictions(
            { input: v, componentRestrictions: { country: 'au' } },
            function (preds, status) {
                if (status !== window.google.maps.places.PlacesServiceStatus.OK || !preds) {
                    listEl.classList.remove('open'); return;
                }
                items = preds; hi = -1;
                listEl.innerHTML = preds.map(function (p, i) {
                    return '<div class="bf__aci" data-i="' + i + '">' +
                        '<svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">' +
                        '<path d="M7 1C4.791 1 3 2.791 3 5c0 3 4 8 4 8s4-5 4-8c0-2.209-1.791-4-4-4z"' +
                        ' stroke="#b8902e" stroke-width="1.2" fill="none"/>' +
                        '<circle cx="7" cy="5" r="1.3" fill="#b8902e"/></svg>' +
                        '<span>' + p.description + '</span></div>';
                }).join('');
                listEl.classList.add('open');
            }
        );
    });

    listEl.addEventListener('click', function (e) {
        var it = e.target.closest('.bf__aci');
        if (!it) return;
        inputEl.value = items[parseInt(it.dataset.i, 10)].description;
        listEl.classList.remove('open');
    });

    inputEl.addEventListener('keydown', function (e) {
        var rows = listEl.querySelectorAll('.bf__aci');
        if (e.key === 'ArrowDown') {
            hi = Math.min(hi + 1, rows.length - 1); bfHL(rows); e.preventDefault();
        } else if (e.key === 'ArrowUp') {
            hi = Math.max(hi - 1, -1); bfHL(rows); e.preventDefault();
        } else if (e.key === 'Enter' && hi >= 0) {
            inputEl.value = items[hi].description;
            listEl.classList.remove('open'); e.preventDefault();
        } else if (e.key === 'Escape') {
            listEl.classList.remove('open');
        }
    });

    document.addEventListener('click', function (e) {
        if (!inputEl.contains(e.target) && !listEl.contains(e.target)) {
            listEl.classList.remove('open');
        }
    });

    function bfHL(rows) {
        rows.forEach(function (r, i) { r.classList.toggle('hi', i === hi); });
    }
}

/* Called by Google Maps script callback */
window.bfMapsReady = function () {
    if (!window.BF_LOCK_PICKUP) {
        bfSetupAC(document.getElementById('bfPickup'), document.getElementById('bfPickupList'));
    }
    // Destination & stop only for non-hourly service types
    if (!window.BF_IS_HOURLY) {
        if (!window.BF_LOCK_DEST) {
            bfSetupAC(document.getElementById('bfDest'), document.getElementById('bfDestList'));
        }
        bfSetupAC(document.getElementById('bfStop'), document.getElementById('bfStopList'));
    }
};

/* ── Submit: validate + loading state ───────────────────────── */
(function () {
    var form = document.getElementById('bfForm');
    if (!form) return;

    form.addEventListener('submit', function (e) {
        // Run client-side baby age validation before submitting
        if (!_validateAllAgeFields()) {
            e.preventDefault();
            return;
        }

        var btn     = document.getElementById('bfSubmit');
        var spinner = document.getElementById('bfSpin');
        var arrow   = document.getElementById('bfBtnArrow');
        var txtEl   = document.getElementById('bfBtnTxt');
        if (btn) btn.disabled = true;
        if (spinner) spinner.style.display = 'block';
        if (arrow)   arrow.style.display   = 'none';
        if (window.BF_IS_HOURLY) {
            if (txtEl) txtEl.innerHTML = 'Opening WhatsApp\u2026';
        } else {
            if (txtEl) txtEl.textContent = 'Calculating route\u2026';
        }
    });
})();
