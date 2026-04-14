/* panther_cloud_air_shared.js — Shared utilities for Panther Cloud Air
   ======================================================================
   Loaded by every page (airports, schedule, book, employee, admin).
   Provides:
     - Global mutable state (AIRPORTS, CITY, HUBS, FLEET_DATA)
     - API base URL resolution (works both as file:// and http://)
     - Page / tab navigation helpers (showBookingStep, navigateTo, switchTab)
     - Authentication guards (checkAuth, initNavBar, _saveSessionAndRedirect, logout)
     - Theme toggle (applyTheme, setTheme)
     - Fare calculation (getCentsPerNm, calcBaseFare)
     - Dropdown population (fillRouteDropdowns)
     - Modal and side-panel helpers (showModal, hideModal, showAircraftPanel, hideAircraftPanel)
     - Async data loaders (fetchAirports, fetchAircraft, fetchPricing)

   DATA FLOW
   ─────────
   aircraft_schedule.js is always loaded BEFORE this file.
   It defines the global constants that this file reads:
     FLIGHTS      — array of all scheduled flights (used by fillRouteDropdowns, calcBaseFare, etc.)
     AIRPORTS     — static airport list (overwritten by fetchAirports when DB is live)
     TOO_CLOSE    — Set of "IATA1-IATA2" pairs with no service between them
     HUBS         — array of hub airport IATA codes (ATL, DFW, DEN, ORD, JFK)
     DEMAND       — object mapping origin → destination → expected daily pax
     ROUTE_STATUS — object mapping "from-to" → "direct"|"connect"|"unmet"
   ====================================================================== */

'use strict';

// ── Global mutable state ──────────────────────────────────────────────────────
// These arrays are written by the async loaders below and read by page scripts.

var AIRPORTS   = [];   // Full airport objects loaded from /api/airports (or static fallback)
var CITY       = {};   // IATA → city name lookup; populated by fetchAirports
var HUBS       = [];   // Hub IATA codes; populated by fetchAirports
var FLEET_DATA = [];   // Aircraft + model records from /api/aircraft; used by admin Fleet tab

// ── API base URL ──────────────────────────────────────────────────────────────
// When opened as a local file (file://) the browser cannot make same-origin
// requests, so we point explicitly at the Flask dev server on port 5001.
// When served from Flask itself (http://localhost:5000), the base is empty
// and all fetch() calls use relative paths (e.g. "/api/airports").
var API_BASE = (location.protocol === 'file:') ? 'http://localhost:5001' : '';

// ── Page navigation helpers ───────────────────────────────────────────────────

/* showBookingStep(stepId)
   Hides every element with class "pg" then shows the one whose id matches "pg-<stepId>".
   Used inside book.html to swap between booking wizard steps (search, class, confirm, done)
   without a full page reload, preserving all in-memory booking state. */
function showBookingStep(stepId) {
  document.querySelectorAll('.pg').forEach(function(p){ p.style.display = 'none'; });
  var el = document.getElementById('pg-' + stepId);
  if (el) el.style.display = 'block';
}

/* navigateTo(pageId)
   ──────────────────
   Universal navigation function called by nav buttons and in-page links.

   Special case — booking sub-pages ('book', 'class', 'confirm', 'done'):
     If already on book.html: swap the visible step panel via showBookingStep() (no full reload).
     If on any other page:    navigate to book.html (which shows the search panel).
     Optionally triggers renderConfirmStep() or renderDoneStep() after the swap so those panels
     are always rendered with fresh data.

   All other IDs: redirect to <pageId>.html in the same directory. */
function navigateTo(pageId) {
  var bookingSteps = ['book', 'class', 'confirm', 'done'];
  var currentPage  = window.location.pathname.split('/').pop().replace('.html', '');

  if (bookingSteps.indexOf(pageId) >= 0) {
    if (currentPage === 'book') {
      showBookingStep(pageId);
      // Keep the "Book Flight" nav button highlighted on all booking sub-steps
      document.querySelectorAll('.nb').forEach(function(n){ n.classList.remove('on'); });
      var navBtn = document.getElementById('nb-book');
      if (navBtn) navBtn.classList.add('on');
      // Trigger step renderers so content is always up-to-date
      if (pageId === 'confirm' && typeof renderConfirmStep === 'function') renderConfirmStep();
      if (pageId === 'done'    && typeof renderDoneStep    === 'function') renderDoneStep();
    } else {
      window.location.href = 'book.html';
    }
    return;
  }

  window.location.href = pageId + '.html';
}

/* switchTab(portalGroup, panelId, clickedBtn)
   ─────────────────────────────────────────────
   Switches the active tab within the Employee ('emp') or Admin ('adm') portal.
   Removes the 'on' class from every tab button, adds it to the clicked button,
   then hides all .pan panels inside the portal page and shows the target one.

   portalGroup: 'emp' (employee portal) or 'adm' (admin portal) — controls which
                tab bar and page container are targeted.
   panelId:     the id of the .pan <div> to reveal.
   clickedBtn:  the <button> element that was clicked (receives the 'on' class). */
function switchTab(portalGroup, panelId, clickedBtn) {
  var tabsId  = portalGroup === 'emp' ? 'emp-tabs' : 'adm-tabs';
  var pageId  = portalGroup === 'emp' ? 'pg-employee' : 'pg-admin';
  var tabBar  = document.getElementById(tabsId);
  if (tabBar) tabBar.querySelectorAll('.tab').forEach(function(t){ t.classList.remove('on'); });
  clickedBtn.classList.add('on');
  var page = document.getElementById(pageId);
  if (page) page.querySelectorAll('.pan').forEach(function(p){ p.classList.remove('on'); });
  var panel = document.getElementById(panelId);
  if (panel) panel.classList.add('on');
}

// ── Authentication helpers ────────────────────────────────────────────────────
// All protected pages call checkAuth() at the top of their init() function.
// Login state is stored in sessionStorage (cleared when the browser tab closes).

/* checkAuth()
   ────────────
   Reads the session from sessionStorage.
   If no session exists, immediately redirects to login.html and returns null
   (the calling init() function should `return` on null to stop further execution).
   Returns { username, role } on success. */
function checkAuth() {
  var user = sessionStorage.getItem('pca_username');
  var role = sessionStorage.getItem('pca_role');
  if (!user) { window.location.href = 'login.html'; return null; }
  return { username: user, role: role };
}

/* initNavBar(auth)
   ──────────────────
   Configures the navigation bar after login:
     - Shows #nav (hidden by default so it never flashes unauthenticated)
     - Writes the username and role badge into the nav-right area
     - Reveals the Employee nav button for all logged-in users
     - Reveals the Admin nav button ONLY for Admin-role users
     - Highlights the nav button matching the current page filename
     - Restores the theme switch state from localStorage

   Role visibility rules:
     Employee → Employee button visible; Admin button stays hidden
     Admin    → Both Employee AND Admin buttons visible */
function initNavBar(auth) {
  if (!auth) return;
  var nav = document.getElementById('nav');
  if (nav) nav.style.display = 'flex';
  var nameEl = document.getElementById('nav-name');
  var roleEl = document.getElementById('nav-role');
  if (nameEl) nameEl.textContent = auth.username;
  if (roleEl) roleEl.textContent = auth.role === 'Admin' ? 'Admin' : 'Staff';
  var empBtn = document.getElementById('nb-employee');
  var admBtn = document.getElementById('nb-admin');
  if (empBtn) empBtn.style.display = 'inline-flex';
  if (auth.role === 'Admin' && admBtn) admBtn.style.display = 'inline-flex';
  // Highlight the nav button whose id matches the current page
  var currentPage = window.location.pathname.split('/').pop().replace('.html', '');
  var activeNavBtn = document.getElementById('nb-' + currentPage);
  if (activeNavBtn) activeNavBtn.classList.add('on');
  // Sync theme checkbox with the stored preference
  var themeChk = document.getElementById('theme-chk');
  if (themeChk) themeChk.checked = (localStorage.getItem('pca_theme') === 'light');
}

/* _saveSessionAndRedirect(username, role)
   ──────────────────────────────────────
   Called by login.html after a successful /api/login response.
   Saves the session to sessionStorage then redirects to the appropriate portal:
     Admin    → admin.html   (can also navigate to employee.html manually)
     Employee → employee.html */
function _saveSessionAndRedirect(username, role) {
  sessionStorage.setItem('pca_username', username);
  sessionStorage.setItem('pca_role', role);
  window.location.href = (role === 'Admin') ? 'admin.html' : 'employee.html';
}

/* logout()
   ─────────
   Clears the session from sessionStorage and returns to the login page.
   Called by the "Sign out" button present in every page's nav bar. */
function logout() {
  sessionStorage.removeItem('pca_username');
  sessionStorage.removeItem('pca_role');
  window.location.href = 'login.html';
}

// ── Theme helpers ─────────────────────────────────────────────────────────────

/* applyTheme()
   ─────────────
   Called at the top of every page's init() to apply the persisted color theme
   before any content renders (prevents a light-flash on dark-mode pages).
   Reads 'pca_theme' from localStorage; 'light' enables the light CSS class,
   anything else (including absence) keeps the default dark theme. */
function applyTheme() {
  var isLight = localStorage.getItem('pca_theme') === 'light';
  document.body.classList.toggle('light', isLight);
  var themeChk = document.getElementById('theme-chk');
  if (themeChk) themeChk.checked = isLight;
}

/* setTheme(isLight)
   ──────────────────
   Called by the theme switch checkbox's onchange handler.
   Adds/removes the 'light' class on <body> and saves the choice to localStorage
   so it persists across all pages and browser sessions. */
function setTheme(isLight) {
  document.body.classList.toggle('light', isLight);
  localStorage.setItem('pca_theme', isLight ? 'light' : 'dark');
}

// ── Fare calculation ──────────────────────────────────────────────────────────
// These functions compute the base economy fare for any flight or itinerary.
// The result is used by book.html (booking wizard) and admin.html (P&L tables).

/* getCentsPerNm()
   ────────────────
   Returns the current cents-per-nautical-mile rate set by the Admin Pricing slider.
   Reads 'pca_cpm' from localStorage; defaults to 65 ¢/nm when no value is stored.
   Valid range: 5–150 ¢/nm.
   65 ¢/nm is the break-even+ default: at baseline margins the fleet runs a profit.

   Why nautical miles (nm)?
     Aviation uses nm universally (altimeters, speed, ATC).
     block_minutes × 6 ≈ nm  (based on a ~450-kt average ground speed proxy for
     a mix of short-haul jets and wide-body international flights). */
function getCentsPerNm() {
  var rate = parseFloat(localStorage.getItem('pca_cpm'));
  return (rate >= 5 && rate <= 150) ? rate : 65;
}

/* calcBaseFare(legs)
   ───────────────────
   Computes the total economy base fare for an itinerary (array of leg objects).
   Each leg contributes block minutes; total block time × 6 estimates nautical miles.
   Formula: max($49, round(total_block_minutes × 6 × getCentsPerNm() / 100))

   The $49 floor prevents the formula from producing absurdly cheap short hops.
   The margin multiplier (getMarginMultiplier / calcMarginMultiplier) is NOT applied here;
   callers in book.html and admin.html apply it separately so the underlying base
   fare stays reusable across different margin contexts. */
function calcBaseFare(legs) {
  var totalBlockMinutes = 0;
  legs.forEach(function(leg) {
    var depMinutes = timeToMinutes(leg.dep);
    var arrMinutes = timeToMinutes(leg.arr);
    // Handle overnight legs where arrival is past midnight (arr < dep in minutes)
    totalBlockMinutes += arrMinutes > depMinutes ? arrMinutes - depMinutes : (1440 - depMinutes + arrMinutes);
  });
  return Math.max(49, Math.round(totalBlockMinutes * 6 * getCentsPerNm() / 100));
}

/* areTooClose(airportA, airportB)
   ────────────────────────────────
   Returns true if the two IATA codes are within 150 miles of each other
   (i.e., the pair appears in the TOO_CLOSE Set defined in aircraft_schedule.js).
   Checks both orderings ("ATL-BOS" and "BOS-ATL") since TOO_CLOSE stores them
   in canonical sorted order. Used by searchFlights() in book.html to block
   same-metro searches and skip short-haul legs during DFS itinerary building. */
function areTooClose(airportA, airportB) {
  if (typeof TOO_CLOSE === 'undefined') return false;
  return TOO_CLOSE.has(airportA + '-' + airportB) || TOO_CLOSE.has(airportB + '-' + airportA);
}

// ── Select dropdown population ────────────────────────────────────────────────

/* fillRouteDropdowns()
   ─────────────────────
   Fills all airport-picker <select> elements from the FLIGHTS array.
   Collects every unique IATA code that appears as an origin OR destination
   in any scheduled flight, sorts them alphabetically, then appends city names
   from the CITY lookup map.

   Target element IDs:
     b-from, b-to   — booking wizard origin/destination (book.html)
     e-from, e-to   — employee portal search (employee.html)
     mf-from, mf-to — "Add New Flight" modal (admin.html)

   "sf-from" and "sf-to" (schedule filter dropdowns) get a leading "All" option
   so the user can filter by just one end of a route. */
function fillRouteDropdowns() {
  // Collect every IATA code that appears as an origin or destination, deduplicate with Set, sort A-Z
  var codes = Array.from(new Set(FLIGHTS.flatMap(function(f){ return [f.from, f.to]; }))).sort();

  // Build one <option> per airport; append city name from CITY map if available (e.g. "ATL - Atlanta")
  var opts = codes.map(function(code) {
    return '<option value="' + code + '">' + code + (CITY[code] ? ' - ' + CITY[code] : '') + '</option>';
  }).join('');

  // Inject the same option list into booking, employee, and admin dropdowns
  ['b-from', 'b-to', 'e-from', 'e-to', 'mf-from', 'mf-to'].forEach(function(id) {
    var el = document.getElementById(id); if (el) el.innerHTML = opts;
  });

  // Schedule filter dropdowns get a leading "All" option so users can filter by one airport only
  var schedOpts = '<option value="">All</option>' + opts;
  ['sf-from', 'sf-to'].forEach(function(id) {
    var el = document.getElementById(id); if (el) el.innerHTML = schedOpts;
  });

  // Default b-to to the second airport so origin and destination are different on page load
  var destSelect = document.getElementById('b-to');
  if (destSelect && destSelect.options.length > 1) destSelect.selectedIndex = 1;
}

// ── Modal & side-panel helpers ────────────────────────────────────────────────

/* showModal(modalId) / hideModal(modalId)
   ──────────────────────────────────────
   Toggle visibility of a modal overlay by adding/removing the 'on' class.
   The modal backdrop (.mbg) is always present in the DOM but invisible;
   'on' makes it visible and blocks pointer events on the page behind it.
   Used by: admin.html "Add New Flight" modal (#m-flt). */
function showModal(modalId)  { var el = document.getElementById(modalId); if (el) el.classList.add('on'); }
function hideModal(modalId) { var el = document.getElementById(modalId); if (el) el.classList.remove('on'); }

/* showAircraftPanel(tailNumber, aircraftType)
   ─────────────────────────────────────────
   Opens the slide-in aircraft detail panel (#side) in admin.html.
   Populates the panel with the tail number, aircraft type, and the first 4
   scheduled legs for that aircraft drawn from the AIRCRAFT array in aircraft_schedule.js.
   Each leg is rendered as a timeline item; the first is marked "done" and the
   second "now" to simulate an in-progress daily schedule. */
function showAircraftPanel(tailNumber, aircraftType) {
  document.getElementById('side-tail').textContent = tailNumber;
  document.getElementById('side-type').textContent = aircraftType;
  // Find the matching aircraft entry in the static AIRCRAFT array
  var matchedAircraft = null;
  for (var i = 0; i < AIRCRAFT.length; i++) {
    if (AIRCRAFT[i].tail === tailNumber) { matchedAircraft = AIRCRAFT[i]; break; }
  }
  var todaysLegs = matchedAircraft ? matchedAircraft.legs.slice(0, 4) : [];
  var html = '<div style="font-size:11px;color:var(--dim);margin-bottom:8px">Flights Today</div><div class="tl">';
  todaysLegs.forEach(function(leg, idx) {
    // idx 0 = completed (done), idx 1 = current (now), idx 2+ = upcoming (no class)
    html += '<div class="ti"><div class="td ' + (idx === 0 ? 'done' : idx === 1 ? 'now' : '') + '"></div>';
    html += '<div style="font-size:10px;color:var(--dim)">' + leg.dep + '</div>';
    html += '<div style="font-size:12px;font-weight:500">' + leg.fn + ' - ' + leg.fr + ' to ' + leg.to + '</div></div>';
  });
  html += '</div>';
  document.getElementById('side-legs').innerHTML = html;
  document.getElementById('side').classList.add('on');
}

/* hideAircraftPanel()
   ────────────────────
   Hides the aircraft detail side panel by removing the 'on' class. */
function hideAircraftPanel() { document.getElementById('side').classList.remove('on'); }

// Click on the backdrop (outside the modal content box) closes the modal.
// This uses event delegation: the backdrop itself is the target when you click
// the dark area, but not when you click a child element inside the modal card.
document.querySelectorAll('.mbg').forEach(function(backdrop) {
  backdrop.addEventListener('click', function(e) { if (e.target === backdrop) backdrop.classList.remove('on'); });
});

// ── Helper: time string conversion ────────────────────────────────────────────

/* timeToMinutes(timeString)
   ──────────────────────────
   Converts a "HH:MM" time string to total minutes past midnight.
   Used throughout the codebase whenever block time or connection gaps are computed.
   Example: timeToMinutes("14:35") → 875 */
function timeToMinutes(timeString) {
  var parts = timeString.split(':');
  return parseInt(parts[0]) * 60 + parseInt(parts[1]);
}

// ── Async data loaders ────────────────────────────────────────────────────────
// Each loader is awaited in every page's init(). On network failure, the loader
// falls back gracefully to static data from aircraft_schedule.js so the page
// still renders correctly when the Flask/DB stack is offline.

/* fetchAirports()
   ────────────────
   Fetches the full airport list from /api/airports (Flask → MariaDB Airports table).
   Transforms each row into a lightweight object and populates:
     AIRPORTS — sorted by metro population descending (already ordered by the SQL query)
     CITY     — IATA → city name lookup used by fillRouteDropdowns() and renderSchedule()
     HUBS     — filtered list of hub IATA codes used by route profitability logic

   Fallback: if the API is unreachable, CITY is built from the FLIGHTS array
   (origin/destination codes with empty city names) and HUBS is hard-coded to the
   five main hub airports. */
async function fetchAirports() {
  try {
    var res  = await fetch(API_BASE + '/api/airports');
    var data = await res.json();
    AIRPORTS = data.map(function(airport, index) {
      return { rank: index + 1, iata: airport.iata_code, city: airport.city,
               name: airport.airport_name, pop: airport.metro_pop / 1e6,
               hub: !!airport.is_hub, intl: airport.iata_code === 'CDG' };
    });
    CITY = {};
    AIRPORTS.forEach(function(airport) { CITY[airport.iata] = airport.city; });
    HUBS = AIRPORTS.filter(function(airport) { return airport.hub; })
                   .map(function(airport) { return airport.iata; });
  } catch (e) {
    console.warn('Airports API offline — using fallback.');
    // Build minimal CITY map from flight origin/destination codes
    FLIGHTS.forEach(function(flight) {
      if (!CITY[flight.from]) CITY[flight.from] = '';
      if (!CITY[flight.to])   CITY[flight.to]   = '';
    });
    HUBS = ['ATL', 'DFW', 'DEN', 'ORD', 'JFK'];
  }
}

/* fetchAircraft()
   ─────────────────
   Fetches the aircraft fleet from /api/aircraft (Flask → Aircraft JOIN Aircraft_models).
   Stores the result in FLEET_DATA which is used by admin.html's Fleet tab to show
   aggregate model statistics (total seats, daily lease cost per model, etc.).
   Silent failure: logs a warning and leaves FLEET_DATA empty. */
async function fetchAircraft() {
  try {
    var res   = await fetch(API_BASE + '/api/aircraft');
    FLEET_DATA = await res.json();
  } catch (e) { console.warn('Aircraft API offline.'); }
}

/* fetchPricing()
   ───────────────
   Fetches cabin pricing rules from /api/pricing and updates the #pricing-loaded
   status label in admin.html's Pricing tab.
   The actual fare calculation uses getCentsPerNm() + calcMarginMultiplier() from localStorage,
   not the DB pricing rules directly — this call is informational only. */
async function fetchPricing() {
  try {
    var res     = await fetch(API_BASE + '/api/pricing');
    var pricing = await res.json();
    var el = document.getElementById('pricing-loaded');
    if (el) el.textContent = pricing.length + ' rules loaded';
  } catch (e) {
    var el = document.getElementById('pricing-loaded');
    if (el) el.textContent = 'DB offline';
  }
}
