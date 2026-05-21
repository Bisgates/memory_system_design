"""
Dedup — similarity detection and restart-protocol conflict resolution.

Design choices:
- similarity() combines two signals:
    1. Text similarity on :body field via difflib.SequenceMatcher (0..1).
    2. Structural agreement: how many of (subj, pred, obj) match between the two cards.
       Each matching slot adds 1/3 to structural score.
  Final score = 0.6 * text_sim + 0.4 * struct_sim (tunable constants).
  If either card has no :body, text_sim = 0 (only structural contributes).
- find_near_dupes() scans the store for cards with similarity >= threshold.
- Restart protocol: new_card.kvs[:on-dedup-conflict] is a list of restart options.
  resolve_conflict() picks the first option and executes it:
    keep-both     → add :see-also links on both cards (no deletion)
    merge-prefer-newer → old card gets :status='superseded', :superseded-by=new_id;
                         new card gets :supersedes=[old_ids]
    supersede     → same as merge-prefer-newer
- This is a demo/kernel implementation; production would surface choices to an agent.
"""

from __future__ import annotations
import difflib
from typing import Optional
from wiki.lib.cardstore import Card, CardStore


# Weight constants for similarity score
_WEIGHT_TEXT = 0.6
_WEIGHT_STRUCT = 0.4


# ---------------------------------------------------------------------------
# Similarity
# ---------------------------------------------------------------------------

def similarity(card_a: Card, card_b: Card) -> float:
    """Compute similarity score [0,1] between two cards."""
    # Text similarity on :body
    body_a = str(card_a.kvs.get("body", "") or "")
    body_b = str(card_b.kvs.get("body", "") or "")

    if body_a and body_b:
        text_sim = difflib.SequenceMatcher(None, body_a, body_b).ratio()
    else:
        text_sim = 0.0

    # Structural agreement on (subj, pred, obj)
    slots = ("subj", "pred", "obj")
    struct_matches = sum(
        1 for s in slots
        if card_a.kvs.get(s) is not None
        and card_a.kvs.get(s) == card_b.kvs.get(s)
    )
    struct_sim = struct_matches / 3.0

    return _WEIGHT_TEXT * text_sim + _WEIGHT_STRUCT * struct_sim


def find_near_dupes(
    card: Card,
    store: CardStore,
    threshold: float = 0.80,
) -> list[tuple[Card, float]]:
    """
    Find all cards in store (excluding card itself) with similarity >= threshold.
    Returns list of (other_card, score) sorted descending by score.
    """
    results = []
    for other in store.all_cards():
        if other.id == card.id:
            continue
        score = similarity(card, other)
        if score >= threshold:
            results.append((other, score))
    results.sort(key=lambda x: x[1], reverse=True)
    return results


# ---------------------------------------------------------------------------
# Conflict resolution (restart protocol)
# ---------------------------------------------------------------------------

def resolve_conflict(
    new_card: Card,
    dupes: list[tuple[Card, float]],
    store: CardStore,
) -> str:
    """
    Execute the first restart in new_card.kvs['on-dedup-conflict'].
    Returns the action string that was taken.
    Modifies store in-place.
    """
    if not dupes:
        return "no-conflict"

    restart_options = new_card.kvs.get("on-dedup-conflict", ["keep-both"])
    if isinstance(restart_options, str):
        restart_options = [restart_options]
    action = restart_options[0] if restart_options else "keep-both"

    dupe_cards = [d[0] for d in dupes]

    if action == "keep-both":
        _action_keep_both(new_card, dupe_cards, store)
    elif action in ("merge-prefer-newer", "supersede"):
        _action_supersede(new_card, dupe_cards, store)
    else:
        # Unknown restart — default to keep-both
        _action_keep_both(new_card, dupe_cards, store)
        action = f"keep-both(fallback from {action})"

    return action


def _action_keep_both(new_card: Card, dupe_cards: list[Card], store: CardStore) -> None:
    """keep-both: add :see-also links on new_card and each dupe."""
    dupe_ids = [d.id for d in dupe_cards]
    # Update new_card's see-also
    existing_see_also = list(new_card.kvs.get("see-also", []) or [])
    new_see_also = list(set(existing_see_also + dupe_ids))
    # new_card may not yet be in store; handle both cases
    if store.get(new_card.id) is not None:
        store.update(new_card.id, **{"see-also": new_see_also})
    else:
        new_card.kvs["see-also"] = new_see_also

    # Update each dupe's see-also
    for dupe in dupe_cards:
        dupe_see_also = list(dupe.kvs.get("see-also", []) or [])
        if new_card.id not in dupe_see_also:
            dupe_see_also.append(new_card.id)
        store.update(dupe.id, **{"see-also": dupe_see_also})


def _action_supersede(new_card: Card, dupe_cards: list[Card], store: CardStore) -> None:
    """supersede: old cards get :status=superseded, new_card gets :supersedes=[ids]."""
    dupe_ids = [d.id for d in dupe_cards]
    for dupe in dupe_cards:
        store.update(dupe.id, status="superseded", **{"superseded-by": new_card.id})
    # Update new_card
    if store.get(new_card.id) is not None:
        store.update(new_card.id, supersedes=dupe_ids)
    else:
        new_card.kvs["supersedes"] = dupe_ids
