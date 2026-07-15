/**
 * Koronet OS — Freshness Badge
 *
 * Reads _meta from embedded JSON and renders a data-provenance banner.
 * - Green:  data is within its freshness window
 * - Amber:  data is stale (past freshness window)
 * - Red:    data is blocked or missing
 *
 * Usage (in a dashboard):
 *   <div id="freshness"></div>
 *   <script>
 *     // window.DATA must have a _meta key (provenance envelope)
 *     renderFreshnessBadge('freshness', window.DATA._meta);
 *   </script>
 *
 * Or if you have multiple data sources on one page:
 *   renderFreshnessBadge('freshness-fees', feeData._meta);
 *   renderFreshnessBadge('freshness-accounts', accountData._meta);
 */

/* exported renderFreshnessBadge */

function renderFreshnessBadge(containerId, metaObject) {
  var container = document.getElementById(containerId);
  if (!container) return;

  // ── Handle missing/null meta ──────────────────────────────────────────
  if (!metaObject) {
    container.innerHTML = _freshnessBadgeHTML({
      color: 'red',
      icon: '\u26A0',  // warning sign
      headline: 'No provenance metadata',
      detail: 'This dashboard has no _meta envelope. Data trust is unknown.',
    });
    return;
  }

  var meta = metaObject;

  // ── Parse pulled_at ───────────────────────────────────────────────────
  var pulledAt = null;
  var ageHours = null;
  var ageText = '';

  if (meta.pulled_at && meta.pulled_at !== 'unknown') {
    try {
      // Handle ISO 8601 with or without timezone
      pulledAt = new Date(meta.pulled_at);
      if (isNaN(pulledAt.getTime())) pulledAt = null;
    } catch (e) {
      pulledAt = null;
    }
  }

  if (pulledAt) {
    var nowMs = Date.now();
    ageHours = (nowMs - pulledAt.getTime()) / (1000 * 60 * 60);
    ageText = _formatAge(ageHours);
  }

  // ── Determine freshness state ─────────────────────────────────────────
  var windowHours = meta.freshness_window_hours || 24;
  var trust = meta.trust_level || 'unknown';
  var state; // 'green' | 'amber' | 'red'

  if (trust === 'blocked') {
    state = 'red';
  } else if (!pulledAt) {
    state = 'red';
  } else if (ageHours > windowHours) {
    state = 'amber';
  } else {
    state = 'green';
  }

  // ── Build display strings ─────────────────────────────────────────────
  var refreshedStr = pulledAt
    ? pulledAt.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
      + ' ' + pulledAt.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' })
    : 'unknown';

  var trustDisplay = _trustLabel(trust);

  var gapsDisplay = '';
  if (meta.known_gaps && meta.known_gaps.length > 0) {
    gapsDisplay = meta.known_gaps.join(' | ');
  }

  var sourceDisplay = meta.source || '';

  // ── Headline per state ────────────────────────────────────────────────
  var icon, headline, detail;

  if (state === 'green') {
    icon = '\u2713';  // checkmark
    headline = 'Data is fresh';
    detail = 'Last refreshed: ' + refreshedStr + ' (' + ageText + ')';
  } else if (state === 'amber') {
    icon = '\u26A0';  // warning
    headline = 'Data is stale';
    var overBy = Math.round(ageHours - windowHours);
    detail = 'Last refreshed: ' + refreshedStr + ' (' + ageText + ') \u2014 '
           + overBy + 'h past the ' + windowHours + 'h freshness window';
  } else {
    icon = '\u2716';  // X mark
    headline = trust === 'blocked' ? 'Data source is blocked' : 'Data timestamp missing';
    detail = 'Last refreshed: ' + refreshedStr;
  }

  // ── Render ────────────────────────────────────────────────────────────
  container.innerHTML = _freshnessBadgeHTML({
    color: state,
    icon: icon,
    headline: headline,
    detail: detail,
    trust: trustDisplay,
    gaps: gapsDisplay,
    source: sourceDisplay,
  });
}


// ── Internal helpers ──────────────────────────────────────────────────────

function _formatAge(hours) {
  if (hours < 1) {
    var mins = Math.round(hours * 60);
    return mins + ' min ago';
  }
  if (hours < 24) {
    return Math.round(hours) + 'h ago';
  }
  var days = Math.round(hours / 24);
  return days + 'd ago';
}

function _trustLabel(level) {
  var labels = {
    'trusted':           'Trusted',
    'needs_validation':  'Needs validation',
    'partial':           'Partial',
    'blocked':           'Blocked',
    // Aliases from the architecture doc
    'verified':          'Verified',
    'operational':       'Operational',
    'estimated':         'Estimated',
    'draft':             'Draft',
  };
  return labels[level] || level;
}

function _freshnessBadgeHTML(opts) {
  var colors = {
    green:  { bg: '#0d2818', border: '#36d399', text: '#36d399' },
    amber:  { bg: '#2d2000', border: '#fbbd23', text: '#fbbd23' },
    red:    { bg: '#2d0a0a', border: '#f87272', text: '#f87272' },
  };
  var c = colors[opts.color] || colors.red;

  var html = ''
    + '<div style="'
    +   'background:' + c.bg + ';'
    +   'border:1px solid ' + c.border + ';'
    +   'border-radius:10px;'
    +   'padding:12px 16px;'
    +   'margin-bottom:16px;'
    +   'font-family:-apple-system,Segoe UI,Roboto,sans-serif;'
    +   'font-size:13px;'
    +   'line-height:1.6;'
    +   'color:#e6edf3;'
    + '">'
    + '<div style="display:flex;align-items:center;gap:8px;margin-bottom:4px">'
    +   '<span style="color:' + c.text + ';font-size:16px;font-weight:700">' + opts.icon + '</span>'
    +   '<span style="color:' + c.text + ';font-weight:600;font-size:14px">' + opts.headline + '</span>'
    + '</div>'
    + '<div style="color:#8b98a9">' + opts.detail + '</div>';

  // Trust + gaps line
  var metaLine = '';
  if (opts.trust) {
    metaLine += 'Trust: ' + opts.trust;
  }
  if (opts.gaps) {
    metaLine += (metaLine ? ' \u00B7 ' : '') + 'Gaps: ' + opts.gaps;
  }
  if (metaLine) {
    html += '<div style="color:#8b98a9;margin-top:2px">' + metaLine + '</div>';
  }

  // Source line
  if (opts.source) {
    html += '<div style="color:#6b7685;font-size:11px;margin-top:4px">Source: ' + opts.source + '</div>';
  }

  html += '</div>';
  return html;
}
