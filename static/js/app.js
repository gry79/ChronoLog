/**
 * ChronoLog client helpers: flexible time formatting and dynamic table rows.
 */

(function () {
  "use strict";

  // Admin dropdown: click toggle + close on outside click / Escape
  document.addEventListener("click", function (e) {
    var dropdown = e.target.closest(".admin-dropdown");
    var btn = e.target.closest(".admin-dropdown-btn");
    document.querySelectorAll(".admin-dropdown.is-open").forEach(function (el) {
      if (el !== dropdown) {
        el.classList.remove("is-open");
        var b = el.querySelector(".admin-dropdown-btn");
        if (b) b.setAttribute("aria-expanded", "false");
      }
    });
    if (btn && dropdown) {
      e.preventDefault();
      var open = dropdown.classList.toggle("is-open");
      btn.setAttribute("aria-expanded", open ? "true" : "false");
    }
  });

  document.addEventListener("keydown", function (e) {
    if (e.key !== "Escape") return;
    document.querySelectorAll(".admin-dropdown.is-open").forEach(function (el) {
      el.classList.remove("is-open");
      var b = el.querySelector(".admin-dropdown-btn");
      if (b) b.setAttribute("aria-expanded", "false");
    });
  });

  /**
   * Normalize flexible time input to hh:mm.
   * Accepts: 8, 800, 8:00, 08:00, 8.00
   */
  function normalizeTime(value) {
    if (value == null) return "";
    var raw = String(value).trim();
    if (raw === "") return "";

    raw = raw.replace(".", ":").replace(",", ":");

    if (/^\d{3,4}$/.test(raw)) {
      var h, m;
      if (raw.length === 3) {
        h = parseInt(raw[0], 10);
        m = parseInt(raw.slice(1), 10);
      } else {
        h = parseInt(raw.slice(0, 2), 10);
        m = parseInt(raw.slice(2), 10);
      }
      if (h > 23 || m > 59) return value;
      return (h < 10 ? "0" + h : "" + h) + ":" + (m < 10 ? "0" + m : "" + m);
    }

    if (/^\d{1,2}$/.test(raw)) {
      h = parseInt(raw, 10);
      if (h > 23) return value;
      return (h < 10 ? "0" + h : "" + h) + ":00";
    }

    var match = raw.match(/^(\d{1,2}):(\d{2})$/);
    if (!match) return value;
    h = parseInt(match[1], 10);
    m = parseInt(match[2], 10);
    if (h > 23 || m > 59) return value;
    return (h < 10 ? "0" + h : "" + h) + ":" + (m < 10 ? "0" + m : "" + m);
  }

  function minutes(hhmm) {
    if (!hhmm || hhmm.indexOf(":") < 0) return null;
    var p = hhmm.split(":");
    return parseInt(p[0], 10) * 60 + parseInt(p[1], 10);
  }

  function formatHours(h) {
    return (Math.round(h * 10) / 10).toFixed(1);
  }

  function recomputeDayTotals(tbody) {
    var rows = tbody.querySelectorAll("tr[data-date]");
    var byDate = {};
    rows.forEach(function (tr) {
      var d = tr.getAttribute("data-date");
      if (!byDate[d]) byDate[d] = [];
      byDate[d].push(tr);
    });
    Object.keys(byDate).forEach(function (d) {
      var running = 0;
      byDate[d].forEach(function (tr) {
        var fromEl = tr.querySelector('input[name="time_from"]');
        var toEl = tr.querySelector('input[name="time_to"]');
        var totalEl = tr.querySelector(".day-total");
        var f = fromEl ? normalizeTime(fromEl.value) : "";
        var t = toEl ? normalizeTime(toEl.value) : "";
        var fm = minutes(f);
        var tm = minutes(t);
        if (fm != null && tm != null && tm > fm) {
          running += (tm - fm) / 60;
        }
        if (totalEl) totalEl.textContent = formatHours(running) + " h";
      });
    });
  }

  document.addEventListener("focusout", function (e) {
    if (e.target && e.target.classList.contains("time-input")) {
      e.target.value = normalizeTime(e.target.value);
      var tbody = e.target.closest("tbody");
      if (tbody) recomputeDayTotals(tbody);
    }
  });

  document.addEventListener("input", function (e) {
    if (e.target && e.target.classList.contains("time-input")) {
      var tbody = e.target.closest("tbody");
      if (tbody) recomputeDayTotals(tbody);
    }
  });

  // Add entry row for same day (+)
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='add-row']");
    if (!btn) return;
    e.preventDefault();
    var tr = btn.closest("tr");
    if (!tr) return;
    var date = tr.getAttribute("data-date");
    var tbody = tr.parentElement;
    var clone = tr.cloneNode(true);
    clone.querySelectorAll("input").forEach(function (inp) {
      if (inp.name === "entry_date") {
        inp.value = date;
      } else if (inp.name === "time_from" || inp.name === "time_to" || inp.name === "description") {
        inp.value = "";
      } else if (inp.name === "sort_order") {
        inp.value = "99";
      }
    });
    var totalEl = clone.querySelector(".day-total");
    if (totalEl) totalEl.textContent = "0.0 h";
    // New mid-day rows never get expand arrows – keep spacers for alignment
    clone.querySelectorAll("[data-action='expand-up'], [data-action='expand-down']").forEach(function (b) {
      var spacer = document.createElement("span");
      spacer.className = "btn-icon btn-icon-spacer";
      spacer.setAttribute("aria-hidden", "true");
      spacer.setAttribute("data-action", b.getAttribute("data-action"));
      spacer.textContent = b.textContent.trim() || (b.getAttribute("data-action") === "expand-up" ? "↑" : "↓");
      b.replaceWith(spacer);
    });
    var del = clone.querySelector("[data-action='delete-row']");
    if (del) del.disabled = false;
    tr.after(clone);
    recomputeDayTotals(tbody);
  });

  // Delete row
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='delete-row']");
    if (!btn || btn.disabled) return;
    e.preventDefault();
    var tr = btn.closest("tr");
    var tbody = tr.parentElement;
    var date = tr.getAttribute("data-date");
    var siblings = tbody.querySelectorAll('tr[data-date="' + date + '"]');
    if (siblings.length <= 1 && btn.getAttribute("data-required") === "1") {
      return;
    }
    tr.remove();
    recomputeDayTotals(tbody);
  });

  // Absence: add row
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='add-absence']");
    if (!btn) return;
    e.preventDefault();
    var tbody = document.getElementById("absence-body");
    if (!tbody) return;
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td class="px-2 py-1"><input type="date" name="date_from" class="w-full border rounded px-2 py-1 text-sm"></td>' +
      '<td class="px-2 py-1"><input type="date" name="date_to" class="w-full border rounded px-2 py-1 text-sm"></td>' +
      '<td class="px-2 py-1"><input type="text" name="hours" class="w-20 border rounded px-2 py-1 text-sm" placeholder="h"></td>' +
      '<td class="px-2 py-1"><input type="text" name="description" maxlength="256" class="w-full border rounded px-2 py-1 text-sm"></td>' +
      '<td class="px-2 py-1 text-center"><button type="button" data-action="delete-absence" class="btn-icon danger" title="Löschen">✕</button></td>';
    tbody.appendChild(tr);
  });

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='delete-absence']");
    if (!btn) return;
    e.preventDefault();
    var tr = btn.closest("tr");
    if (tr) tr.remove();
  });

  // Special day add row (admin)
  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='add-special-day']");
    if (!btn) return;
    e.preventDefault();
    var tbody = document.getElementById("special-days-body");
    if (!tbody) return;
    var tr = document.createElement("tr");
    tr.innerHTML =
      '<td class="px-2 py-1"><input type="number" name="sd_day" min="1" max="31" class="w-16 border rounded px-2 py-1 text-sm" placeholder="TT"></td>' +
      '<td class="px-2 py-1"><input type="number" name="sd_month" min="1" max="12" class="w-16 border rounded px-2 py-1 text-sm" placeholder="MM"></td>' +
      '<td class="px-2 py-1"><input type="number" name="sd_year" min="2000" max="2100" class="w-20 border rounded px-2 py-1 text-sm" placeholder="opt."></td>' +
      '<td class="px-2 py-1"><input type="text" name="sd_target" class="w-20 border rounded px-2 py-1 text-sm" placeholder="0.0"></td>' +
      '<td class="px-2 py-1"><input type="text" name="sd_description" maxlength="256" class="w-full border rounded px-2 py-1 text-sm"></td>' +
      '<td class="px-2 py-1 text-center"><button type="button" data-action="delete-special-day" class="btn-icon danger">✕</button></td>';
    tbody.appendChild(tr);
  });

  document.addEventListener("click", function (e) {
    var btn = e.target.closest("[data-action='delete-special-day']");
    if (!btn) return;
    e.preventDefault();
    var tr = btn.closest("tr");
    if (tr) tr.remove();
  });
})();
