"""Conservative deal-based trade review; flags are heuristics, not diagnoses."""
from collections import defaultdict
from datetime import datetime, timezone
from statistics import median

# MT5 DEAL_ENTRY: IN=0, OUT=1, INOUT=2, OUT_BY=3.
ENTRY_IN = 0
EXIT_TYPES = {1, 2, 3}


def analyze_deals(deals):
    """Reconstruct completed position episodes using exits and entries.

    Netting reversals (INOUT), partial exits and positions spanning the lookback
    window require more history for full P&L; such cases are excluded from
    definitive previous-loss flags. Position IDs prevent cross-position confusion.
    """
    normalized = [d._asdict() if hasattr(d, '_asdict') else dict(d) for d in deals]
    normalized.sort(key=lambda d: (int(d.get('time_msc') or int(d['time']) * 1000), int(d.get('ticket', 0))))
    positions = defaultdict(list)
    entries = []
    for d in normalized:
        position_id = int(d.get('position_id') or 0)
        if not position_id:
            continue
        positions[position_id].append(d)
        if int(d.get('entry', -1)) == ENTRY_IN:
            entries.append(d)
    # Mark a losing closed position only when an explicit exit was observed;
    # aggregate all observed deal costs; partial histories are flagged as provisional.
    closures = []
    for position_id, group in positions.items():
        exits = [d for d in group if int(d.get('entry', -1)) in EXIT_TYPES]
        if not exits:
            continue
        total_net = sum(float(d.get('profit') or 0) + float(d.get('commission') or 0)
                        + float(d.get('swap') or 0) + float(d.get('fee') or 0) for d in group)
        final_exit = max(exits, key=lambda d: int(d['time']))
        closures.append({'position_id': position_id, 'symbol': final_exit.get('symbol', ''),
                         'time': int(final_exit['time']), 'net': total_net,
                         'provisional': not any(int(d.get('entry', -1)) == ENTRY_IN for d in group)
                         or any(int(d.get('entry', -1)) == 2 for d in group)})
    revenge_flags = []
    for entry in entries:
        t, symbol = int(entry['time']), entry.get('symbol', '')
        preceding = [c for c in closures if c['symbol'] == symbol and
                     c['position_id'] != int(entry.get('position_id') or 0) and
                     not c['provisional'] and c['net'] < 0 and 0 < t - c['time'] <= 900]
        if preceding:
            revenge_flags.append({'type':'possible_revenge','entry_ticket': int(entry.get('ticket',0)),
                                  'symbol':symbol,'time_utc':datetime.fromtimestamp(t, timezone.utc).isoformat(),
                                  'reason':'Entry within 15 minutes of observed losing position closure'})
    volumes = [float(d.get('volume') or 0) for d in entries]
    sizing_flags = []
    for i, d in enumerate(entries):
        # Historical median of at least 5 PREVIOUS entries on same symbol.
        history = [float(x.get('volume') or 0) for x in entries[:i] if x.get('symbol') == d.get('symbol') and float(x.get('volume') or 0) > 0]
        if len(history) >= 5 and float(d.get('volume') or 0) >= 2 * median(history):
            sizing_flags.append({'type':'volume_anomaly','entry_ticket':int(d.get('ticket',0)),
                                 'symbol':d.get('symbol',''), 'reason':'Entry volume >= 2x prior median; not a monetary-risk determination'})
    flags = revenge_flags + sizing_flags
    return {'status':'Success', 'total_deals_analyzed': len(normalized),
            'total_entry_deals': len(entries), 'completed_positions_with_observed_exits':len(closures),
            'revenge_count':len(revenge_flags),'tilt_count':len(sizing_flags),
            'flags_detected':[f['reason'] + ' (' + f['symbol'] + ')' for f in flags],
            'flags':flags,'limitations':'Heuristic classification; partial history, reversal, costs and missing entry data can affect results. Volume anomalies are not risk estimates.'}
